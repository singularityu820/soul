from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple


@dataclass(slots=True)
class EEGStreamConfig:
    sample_rate_hz: float = 16.0
    update_interval: float = 0.5
    channels: Tuple[str, ...] = ("alpha", "beta", "theta", "delta", "gamma")
    amplitude_range: Tuple[float, float] = (-50.0, 50.0)
    waveform_buffer_seconds: float = 6.0


@dataclass(slots=True)
class EEGClassifierConfig:
    baseline_mood_bias: float = 0.0
    noise_level: float = 0.08


@dataclass(slots=True)
class FaceEmotionConfig:
    smoothing_factor: float = 0.65
    decay_per_second: float = 0.15
    fallback_emotion: str = "neutral"


@dataclass(slots=True)
class FusionConfig:
    channel_weights: Dict[str, float] = field(
        default_factory=lambda: {"eeg": 0.6, "face": 0.4}
    )
    neutral_bias: float = 0.1


@dataclass(slots=True)
class AgentConfig:
    proactive_interval_seconds: float = 25.0
    check_interval_seconds: float = 5.0
    negative_threshold: float = -0.35
    positive_threshold: float = 0.45
    memory_limit: int = 256


@dataclass(slots=True)
class AvatarConfig:
    max_pose_history: int = 60


DEFAULT_EMOTIONS: Tuple[str, ...] = (
    "calm",
    "focused",
    "excited",
    "anxious",
    "sad",
    "joyful",
    "neutral",
)


class LLMProvider(str, Enum):
    OPENAI = "openai"
    MODEL_SCOPE = "modelscope"
    ZHIPU = "zhipu"
    VLLM = "vllm"
    OLLAMA = "ollama"
    SANDBOX = "sandbox"


class TTSProvider(str, Enum):
    EDGE = "edge"
    AZURE = "azure"
    POLLY = "polly"
    COQUI = "coqui"
    OLLAMA = "ollama"
    SANDBOX = "sandbox"


@dataclass(slots=True)
class LLMServiceConfig:
    preferred_provider: Optional[LLMProvider] = None
    allow_auto_detect: bool = True
    timeout_seconds: float = 20.0
    endpoint_overrides: Dict[LLMProvider, str] = field(default_factory=dict)


@dataclass(slots=True)
class TTSServiceConfig:
    preferred_provider: Optional[TTSProvider] = None
    allow_auto_detect: bool = True
    timeout_seconds: float = 15.0
    voice_defaults: Dict[str, str] = field(default_factory=dict)
