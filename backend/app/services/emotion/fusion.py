from __future__ import annotations

import math
from typing import Dict, Iterable

from ...config import FusionConfig
from ...schemas import ChannelEmotion, EmotionState


class EmotionFusionService:
    """Combines modality-specific signals into a unified affective state."""

    def __init__(self, config: FusionConfig | None = None) -> None:
        self.config = config or FusionConfig()

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

        label_scores: Dict[str, float] = {}
        total_weight = 0.0
        for channel in channel_list:
            weight = self.config.channel_weights.get(channel.source, 0.1)
            total_weight += weight
            label_scores[channel.label] = label_scores.get(channel.label, 0.0) + (
                weight * channel.confidence
            )

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
            metadata={"notes": "Weighted fusion of EEG and face signals."},
        )

        return EmotionState(
            label=fused.label,
            confidence=fused.confidence,
            mood_score=fused.mood_score,
            components=channel_list + [fused],
        )
