import math
from typing import Dict, Iterable

from ...config import FusionConfig
from ...schemas import ChannelEmotion, EmotionState


class EmotionFusionService:
    """
    Combines EEG, face, speech signals into a unified affective state.
    权重可配置，默认 EEG:0.5, Face:0.3, Speech:0.2。
    新增：标签一致性加权（支持次数越多，共识系数越大）
    """

    def __init__(self, config: FusionConfig | None = None) -> None:
        self.config = config or FusionConfig()
        # 1. 定义共识系数规则：支持次数→共识系数（可根据需求调整梯度）
        self.consensus_coeff = {
            1: 1.0,   # 1个通道支持：无额外奖励
            2: 1.2,   # 2个通道支持：额外20%奖励
            3: 1.5,   # 3个通道支持：额外50%奖励
        }

    def fuse(self, channels: Iterable[ChannelEmotion]) -> EmotionState:
        channel_list = list(channels)
        if not channel_list:
            neutral = ChannelEmotion(
                source="fusion",
                label="neutral",
                confidence=0.1,
                mood_score=0.0,
                metadata={"notes": "No channels provided."},
            )
            return EmotionState(
                label=neutral.label,
                confidence=neutral.confidence,
                mood_score=neutral.mood_score,
                components=[neutral],
            )

        # --------------------------
        # 2. 第一步：统计每个标签的“支持次数”（被多少个通道输出）
        # --------------------------
        label_support_count: Dict[str, int] = {}
        # 规范化标签后再统计支持次数，避免同义词导致投票分裂
        for channel in channel_list:
            norm_label = self._normalize_label(channel.label)
            label_support_count[norm_label] = label_support_count.get(norm_label, 0) + 1

        # --------------------------
        # 3. 第二步：标签加权得分计算（叠加共识系数）
        # --------------------------
        label_scores: Dict[str, float] = {}
        total_weight = 0.0  # 总权重（用于后续归一化）
        for channel in channel_list:
            channel_source = channel.source
            raw_label = channel.label
            channel_label = self._normalize_label(raw_label)
            channel_confidence = channel.confidence
            channel_weight = self.config.channel_weights.get(channel_source, 0.1)
            # 3.3 计算共识系数（根据该标签的支持次数）
            support_count = label_support_count.get(channel_label, 1)
            # 如果支持次数超出定义，使用最大的系数以避免 KeyError
            max_defined = max(self.consensus_coeff.keys())
            coeff = self.consensus_coeff.get(support_count, self.consensus_coeff[max_defined])
            weighted_score = channel_weight * channel_confidence * coeff
            label_scores[channel_label] = label_scores.get(channel_label, 0.0) + weighted_score
            total_weight += channel_weight  # 总权重仍用基础权重（避免共识系数影响归一化）
        # 处理总权重为0的极端情况（原有逻辑）
        if total_weight <= 0:
            total_weight = 1.0


        best_label = max(label_scores, key=label_scores.get)

        fuse_confidence = min(1.0, label_scores[best_label] / total_weight)

        mood_score = sum(
            self.config.channel_weights.get(channel.source, 0.0) * channel.mood_score
            for channel in channel_list
        )
        mood_score = math.tanh(mood_score + self.config.neutral_bias)

        fused = ChannelEmotion(
            source="fusion",
            label=best_label,
            confidence=fuse_confidence,
            mood_score=mood_score,
            metadata={
                "notes": "Weighted fusion with label consensus (more supported labels get bonus).",
                "channel_weights": self.config.channel_weights.copy(),
                "sources": [ch.source for ch in channel_list],
                "label_support_counts": label_support_count,  # 新增：标签支持次数
                "consensus_coeff_rule": self.consensus_coeff  # 新增：共识系数规则
            },
        )

        return EmotionState(
            label=fused.label,
            confidence=fused.confidence,
            mood_score=fused.mood_score,
            components=channel_list + [fused],
        )

    def _normalize_label(self, label: str) -> str:
        """
        Normalize variants/synonyms into a canonical label set:
        ["neutral","happy","surprised","sad","angry","disgust","fear"].
        """
        if not label:
            return "neutral"
        s = label.strip().lower()
        synonym_map = {
            "surprise": "surprised",
            "surprised": "surprised",
            "joyful": "happy",      # 映射joyful到happy
            "happy": "happy",
            "neutral": "neutral",
            "calm": "neutral",      # 映射calm到neutral
            "relaxed": "neutral",   # 映射relaxed到neutral
            "sad": "sad",
            "angry": "angry",
            "disgust": "disgust",
            "fear": "fear",
            "anxious": "angry",     # 映射anxious到angry
            "stressed": "angry",    # 映射stressed到angry
            "excited": "happy",     # 映射excited到happy
            "afraid": "fear",       # 映射afraid到fear
            "scared": "fear",       # 映射scared到fear
            "disgusted": "disgust", # 映射disgusted到disgust
            "contempt": "disgust",  # 映射contempt到disgust
        }
        return synonym_map.get(s, s)