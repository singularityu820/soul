from __future__ import annotations

import asyncio
import time
import random
from dataclasses import dataclass
from typing import Optional, Any, Dict

from ..schemas import ChannelEmotion

@dataclass(slots=True)
class SpeechObservation:
    label: str
    confidence: float
    intensity: float
    timestamp: float

class SpeechEmotionTool:
    """
    Speech emotion tool (可扩展第三方模型, 默认模拟输出)。
    Usage:
    - 调用 update_audio(audio) 传入音频数据 (如 numpy array 或 bytes)
    - 调用 analyze() 获取 ChannelEmotion
    """
    def __init__(self) -> None:
        self._rng = random.Random()
        self._lock = asyncio.Lock()
        self._latest: Optional[SpeechObservation] = None
        self._latest_audio: Optional[Any] = None

    async def update_audio(self, audio: Any) -> None:
        async with self._lock:
            self._latest_audio = audio

    async def infer_and_update(self) -> None:
        # TODO: 可集成真实语音情绪识别模型
        # 目前为模拟输出
        label = self._rng.choice(["neutral", "happy", "surprised", "sad", "angry", "disgust", "fear"])
        intensity = self._rng.uniform(0.2, 0.8)
        confidence = self._rng.uniform(0.4, 0.9)
        observation = SpeechObservation(
            label=label,
            confidence=confidence,
            intensity=intensity,
            timestamp=time.time(),
        )
        async with self._lock:
            self._latest = observation

    async def analyze(self) -> ChannelEmotion:
        try:
            await self.infer_and_update()
        except Exception:
            pass
        async with self._lock:
            observation = self._latest
        if observation is None:
            return self._simulate_emotion()
        mood_score = self._map_label_to_mood(observation.label, observation.intensity)
        confidence = max(0.0, min(1.0, observation.confidence * 0.9 + 0.1))
        metadata = {"notes": "Speech emotion (simulated or model-based)"}
        return ChannelEmotion(
            source="speech",
            label=observation.label,
            confidence=confidence,
            mood_score=mood_score,
            metadata=metadata,
        )

    def _simulate_emotion(self) -> ChannelEmotion:
        rng = self._rng
        label = rng.choice(["neutral", "happy", "surprise", "sad", "angry", "disgust", "fear"])
        intensity = rng.uniform(0.2, 0.8)
        mood_score = self._map_label_to_mood(label, intensity)
        confidence = rng.uniform(0.4, 0.7)
        metadata = {"notes": "Simulated speech emotion."}
        return ChannelEmotion(
            source="speech",
            label=label,
            confidence=confidence,
            mood_score=mood_score,
            metadata=metadata,
        )

    def _map_label_to_mood(self, label: str, intensity: float) -> float:
        label = label.lower()
        mapping = {
            "happy": 0.8,
            "joyful": 0.9,
            "surprise": 0.3,
            "neutral": 0.0,
            "sad": -0.6,
            "angry": -0.8,
            "disgust": -0.5,
            "fear": -0.7,
            "calm": 0.2,
            "stressed": -0.4,
            "anxious": -0.6,
        }
        base = mapping.get(label, 0.0)
        return max(-1.0, min(1.0, base * intensity))
