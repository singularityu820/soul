from __future__ import annotations

import asyncio
import time
import random
from dataclasses import dataclass
from typing import Optional, Any, Dict

try:
    from deepface import DeepFace
except Exception:  # pragma: no cover - DeepFace optional
    DeepFace = None  # type: ignore
 
import numpy as _np

from ..config import FaceEmotionConfig
from ..schemas import ChannelEmotion


@dataclass(slots=True)
class FaceObservation:
    label: str
    confidence: float
    intensity: float
    faces_detected: int
    timestamp: float

lightweight_deepface_kwargs = {
    "detector_backend": "yolov8",
    "model_name": "Facenet",
    "detector_params": {
        "imgsz": 480,
        "conf": 0.5,
    },
    "actions": ["emotion"],
    "enforce_detection": False
}
class FaceEmotionTool:
    """Face emotion tool with optional DeepFace integration.

    Usage patterns:
    - If you have DeepFace installed and want to use its emotion model, set
      `use_deepface=True` and optionally pass `deepface_kwargs` to control
      analyzer behaviour (e.g. detector_backend, enforce_detection).
    - Call `update_frame(frame)` with an RGB numpy array or bytes (image file
      bytes). The tool will attempt to run DeepFace.analyze on the latest
      frame inside `analyze()` (non-blocking to the event loop).

    The class is defensive: if DeepFace is not available or analysis fails,
    it falls back to a lightweight simulated output so the pipeline keeps
    operating.
    """

    def __init__(
        self,
        config: FaceEmotionConfig | None = None,
        *,
        use_deepface: bool = True,
        deepface_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.config = config or FaceEmotionConfig()
        self._rng = random.Random()
        self._lock = asyncio.Lock()
        self._latest: Optional[FaceObservation] = None

        # Frame for model inference (store RGB numpy array or raw bytes)
        self._latest_frame: Optional[Any] = None

        # DeepFace integration flags/options
        self.use_deepface = bool(use_deepface and DeepFace is not None)
        self.deepface_kwargs = deepface_kwargs or {}

        if use_deepface and DeepFace is None:
            # warn via metadata at runtime; no import at module import time
            self.use_deepface = False

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

    async def update_frame(self, frame: Any) -> None:
        """Store a recent frame for later inference.

        Expected frame: RGB numpy array (H,W,3) is preferred. If bytes are
        provided, DeepFace wrapper will attempt to decode when available.
        """
        async with self._lock:
            self._latest_frame = frame

    async def _run_deepface(self, frame: Any) -> Optional[Dict[str, Any]]:
        """Run DeepFace.analyze in a thread and return the raw result.

        Returns None if DeepFace not available or if analysis fails.
        """
        if not self.use_deepface:
            return None

        def _call():
            try:
                # DeepFace.analyze accepts numpy RGB arrays or image paths.
                # Ensure enforce_detection=False by default when we pass cropped
                # images (we may pass full frames too).
                kwargs = dict(self.deepface_kwargs)
                kwargs.setdefault("actions", ["emotion"])
                kwargs.setdefault("enforce_detection", False)
                return DeepFace.analyze(frame, **kwargs)
            except Exception:
                return None

        return await asyncio.to_thread(_call)

    async def infer_and_update(self) -> None:
        """Try to infer emotions from the latest frame using DeepFace and
        update the internal observation. Best-effort; failures are ignored so
        the system falls back to simulation.
        """
        async with self._lock:
            frame = self._latest_frame

        if frame is None:
            return

        raw = await self._run_deepface(frame)
        if not raw:
            return

        # DeepFace.analyze may return a dict for a single face, or a list for
        # multiple faces depending on version. Normalize to list of dicts.
        if isinstance(raw, dict):
            candidates = [raw]
        elif isinstance(raw, list):
            candidates = raw
        else:
            return

        # Choose the face with highest dominant emotion confidence when
        # multiple faces present.
        best = None
        best_conf = -1.0
        for c in candidates:
            # DeepFace may return an 'emotion' dict mapping names to scores
            emotion_map = c.get("emotion") or c.get("emotions") or {}
            if isinstance(emotion_map, dict) and emotion_map:
                # Scores often in 0-100; normalize to 0-1
                # pick dominant emotion if present
                dominant = c.get("dominant_emotion")
                if dominant and dominant in emotion_map:
                    conf = float(emotion_map[dominant]) / 100.0
                else:
                    # fallback to max score
                    conf = max(float(v) for v in emotion_map.values()) / 100.0
            else:
                # Some versions return a 'dominant_emotion' and 'dominant_emotion_score'
                dom = c.get("dominant_emotion")
                conf = float(c.get("dominant_emotion_score", 0.0))
                if conf > 1.0:
                    conf = conf / 100.0

            if conf > best_conf:
                best_conf = conf
                best = c

        if best is None:
            return

        emotion_map = best.get("emotion") or best.get("emotions") or {}
        dominant = best.get("dominant_emotion")
        if dominant is None and isinstance(emotion_map, dict) and emotion_map:
            dominant = max(emotion_map, key=lambda k: emotion_map[k])

        if isinstance(emotion_map, dict) and dominant in emotion_map:
            conf_val = float(emotion_map[dominant]) / 100.0
        else:
            conf_val = float(best.get("dominant_emotion_score", 0.0))
            if conf_val > 1.0:
                conf_val = conf_val / 100.0

        label = str(dominant) if dominant else str(best.get("dominant_emotion", self.config.fallback_emotion))
        confidence = max(0.0, min(1.0, conf_val or 0.0))
        intensity = confidence
        faces_detected = len(candidates)

        await self.update_observation(label=label, confidence=confidence, intensity=intensity, faces_detected=faces_detected)

    async def analyze(self) -> ChannelEmotion:
        # Attempt model inference first (best-effort). Any error falls through
        # to the simulated fallback.
        try:
            await self.infer_and_update()
        except Exception:
            # keep going to fallback behavior
            pass

        async with self._lock:
            observation = self._latest

        if observation is None or self._is_stale(observation):
            return self._simulate_emotion()

        mood_score = self._map_label_to_mood(observation.label, observation.intensity)
        confidence = max(0.0, min(1.0, observation.confidence * 0.9 + 0.1))

        metadata = {
            "faces_detected": observation.faces_detected,
            "notes": "DeepFace-backed detection if available, else last provided frame.",
            "deepface_available": bool(DeepFace is not None),
        }
        return ChannelEmotion(
            source="face",
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
        metadata = {"notes": "Simulated face emotion. Supply real detections or frame/model to override."}
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

    def _is_stale(self, observation: FaceObservation) -> bool:
        age = time.time() - observation.timestamp
        return age > max(0.5, 1.0 / self.config.decay_per_second)
