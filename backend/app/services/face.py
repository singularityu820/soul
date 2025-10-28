from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Optional

from ..config import FaceEmotionConfig
from ..schemas import ChannelEmotion


@dataclass(slots=True)
class FaceObservation:
    label: str
    confidence: float
    intensity: float
    faces_detected: int
    timestamp: float


class FaceEmotionTool:
    """Wraps a face emotion recognizer. Currently simulated pending model hookup."""

    def __init__(self, config: FaceEmotionConfig | None = None) -> None:
        self.config = config or FaceEmotionConfig()
        self._rng = random.Random()
        self._lock = asyncio.Lock()
        self._latest: Optional[FaceObservation] = None

    async def update_observation(
        self, label: str, confidence: float, intensity: float, faces_detected: int
    ) -> None:
        observation = FaceObservation(
            label=label,
            confidence=confidence,
            intensity=intensity,
            faces_detected=faces_detected,
            timestamp=time.time(),
        )
        async with self._lock:
            self._latest = observation

    async def analyze(self) -> ChannelEmotion:
        async with self._lock:
            observation = self._latest

        if observation is None or self._is_stale(observation):
            return self._simulate_emotion()

        mood_score = self._map_label_to_mood(observation.label, observation.intensity)
        confidence = max(0.0, min(1.0, observation.confidence * 0.9 + 0.1))

        metadata = {
            "faces_detected": observation.faces_detected,
            "notes": "Real detector pending. Current values reflect last provided frame.",
        }
        return ChannelEmotion(
            source="face",
            label=observation.label,
            confidence=confidence,
            mood_score=mood_score,
            metadata=metadata,
        )

    def _simulate_emotion(self) -> ChannelEmotion:
        label = self._rng.choice(
            ["neutral", "happy", "surprised", "sad", "angry", "disgust", "fear"]
        )
        intensity = self._rng.uniform(0.2, 0.8)
        mood_score = self._map_label_to_mood(label, intensity)
        confidence = self._rng.uniform(0.4, 0.7)
        metadata = {"notes": "Simulated face emotion. Supply real detections to override."}
        return ChannelEmotion(
            source="face",
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
            "surprised": 0.3,
            "neutral": 0.0,
            "sad": -0.6,
            "angry": -0.8,
            "disgust": -0.5,
            "fear": -0.7,
        }
        base = mapping.get(label, 0.0)
        return max(-1.0, min(1.0, base * intensity))

    def _is_stale(self, observation: FaceObservation) -> bool:
        age = time.time() - observation.timestamp
        return age > max(0.5, 1.0 / self.config.decay_per_second)
