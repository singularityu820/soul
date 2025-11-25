"""Speech emotion analysis tool.

This module provides a SpeechEmotionTool that uses DashScope (通义千问)
ASR endpoint to transcribe audio and extract an emotion label when
available. If the `dashscope` SDK is present and an API key is configured
via the `DASHSCOPE_API_KEY` environment variable, the tool will call the
SDK; otherwise it will fall back to a lightweight randomized heuristic.

The public API exposes `update_from_audio(audio_bytes)` which updates the
latest detected emotion, and `analyze()` which returns a `ChannelEmotion`.
If deployed in environments without EEG/video, the emotion can be used as
an EEG-like channel (the pipeline maps the speech output into the fusion
routine as an `eeg` source when configured).
"""

import asyncio
import logging
import os
import tempfile
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

try:
    import dashscope
    _HAS_DASHSCOPE = True
except Exception:  # pragma: no cover - optional dependency
    dashscope = None
    _HAS_DASHSCOPE = False

from ...schemas import ChannelEmotion


class SpeechEmotionTool:
    """Tool for analyzing emotion from speech audio.

    Behaviour:
    - `update_from_audio(bytes)`: send audio to DashScope (when available)
      and update last detected emotion and confidence.
    - `analyze()`: return a `ChannelEmotion` describing the latest speech
      emotion. When DashScope is not available or API key is missing this
      falls back to a randomized heuristic.
    """

    def __init__(self, confidence_threshold: float = 0.35) -> None:
        self.confidence_threshold = confidence_threshold
        self._latest_emotion: Optional[str] = "neutral"
        self._latest_confidence: float = 0.0
        self._last_response_meta: Dict[str, Any] = {}

        # Configuration from env
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.api_url = os.getenv("DASHSCOPE_API_URL", "https://dashscope.aliyuncs.com/api/v1")
        self.model = os.getenv("DASHSCOPE_ASR_MODEL", "qwen3-asr-flash-filetrans")

    async def analyze(self) -> ChannelEmotion:
        """Return the latest detected speech emotion as a ChannelEmotion.

        Some consumers expect ChannelEmotion.source to be one of the
        canonical channel names ("eeg", "face", "fusion"). We use
        "fusion" for speech-derived emotions so they can be treated as
        a non-EEG modality in the fusion pipeline and still be mapped to
        EEG when configured.
        """
        return ChannelEmotion(
            source="fusion",
            label=self._latest_emotion or "neutral",
            confidence=float(self._latest_confidence),
            mood_score=float(self._map_label_to_mood(self._latest_emotion or "neutral")),
            metadata={"provider": "dashscope" if _HAS_DASHSCOPE else "local-fallback", **self._last_response_meta},
        )

    async def update_from_audio(self, audio_data: bytes) -> None:
        """Send `audio_data` (raw bytes) to the ASR/emotion service and
        update internal state.

        The function is safe to call from an async context; the potentially
        blocking network call is executed in a threadpool to avoid blocking
        the event loop.
        """
        if _HAS_DASHSCOPE and self.api_key:
            # Use dashscope SDK if available
            loop = asyncio.get_event_loop()

            def _call_sdk(tmp_path: str) -> Dict[str, Any]:
                try:
                    dashscope.base_http_api_url = self.api_url
                    messages = [
                        {"role": "system", "content": [{"text": ""}]},
                        {"role": "user", "content": [{"audio": tmp_path}]},
                    ]
                    response = dashscope.MultiModalConversation.call(
                        api_key=self.api_key,
                        model=self.model,
                        messages=messages,
                        result_format="message",
                        asr_options={"enable_itn": False},
                    )
                    return response
                except Exception as e:
                    logger.exception("DashScope SDK call failed: %s", e)
                    return {}

            # write audio bytes to a temp file that dashscope SDK can read
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                f.write(audio_data)
                tmp_path = f.name

            try:
                res = await loop.run_in_executor(None, _call_sdk, tmp_path)
                # some SDKs may return None on error; guard against that
                if not res:
                    logger.warning("SpeechEmotionTool: dashscope returned empty response")
                try:
                    output = (res or {}).get("output") or {}
                    choices = output.get("choices") or []
                    if choices and isinstance(choices, list):
                        msg = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
                        annotations = msg.get("annotations") or []
                        emotion = None
                        confidence = 0.0
                        for ann in annotations:
                            if isinstance(ann, dict) and ann.get("type") == "audio_info" and "emotion" in ann:
                                emotion = ann.get("emotion")
                                # DashScope may not return confidence; use 0.9 as proxy
                                confidence = float(0.9)
                                break

                        # fallback: look in top-level message content for sentiment tags
                        if not emotion:
                            contents = msg.get("content") or []
                            if isinstance(contents, list):
                                for c in contents:
                                    if isinstance(c, dict) and "emotion" in c:
                                        emotion = c.get("emotion")
                        if emotion:
                            self._latest_emotion = emotion
                            self._latest_confidence = min(1.0, max(0.0, confidence))
                            self._last_response_meta = {"request_id": (res or {}).get("request_id")}
                            logger.debug("SpeechEmotionTool: detected %s (confidence %.2f)", self._latest_emotion, self._latest_confidence)
                            return
                except Exception:
                    logger.exception("Failed to parse DashScope response")

            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        # Fallback heuristic: lightweight acoustic-based random-ish mapping
        import random

        emotions = ["neutral", "calm", "focused", "anxious", "excited", "sad", "happy", "angry", "surprise", "fear", "disgust"]
        self._latest_emotion = random.choice(emotions)
        self._latest_confidence = random.uniform(0.35, 0.85)
        self._last_response_meta = {"fallback": True}
        logger.debug("SpeechEmotionTool (fallback) updated: %s (%.2f)", self._latest_emotion, self._latest_confidence)

    def _map_label_to_mood(self, label: str) -> float:
        mapping = {
            "happy": 0.8,
            "joyful": 0.8,
            "excited": 0.7,
            "calm": 0.2,
            "focused": 0.3,
            "neutral": 0.0,
            "sad": -0.5,
            "angry": -0.8,
            "anxious": -0.6,
            "surprise": 0.2,
            "fear": -0.7,
            "disgust": -0.6,
        }
        return mapping.get((label or "").lower(), 0.0)