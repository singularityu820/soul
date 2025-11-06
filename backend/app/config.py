from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple


@dataclass(slots=True)
class EEGStreamConfig:
    sample_rate_hz: float = 128.0
    update_interval: float = 0.5
    channels: Tuple[str, ...] = ("signal",)
    amplitude_range: Tuple[float, float] = (4.0, 18.0)
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
    SOVITS = "sovits"
    SANDBOX = "sandbox"


@dataclass(slots=True)
class LLMServiceConfig:
    preferred_provider: Optional[LLMProvider] = None
    allow_auto_detect: bool = True
    timeout_seconds: float = 20.0
    endpoint_overrides: Dict[LLMProvider, str] = field(default_factory=dict)
    
    # System prompts for different scenarios
    default_system_prompt: str = "You are a supportive companion."
    voice_chat_system_prompt: str = (
        "你是一个温暖、友好的AI伙伴，正在通过语音和用户进行自然对话。\n"
        "请注意：\n"
        "1. 使用口语化、简洁的表达方式，就像朋友间的日常对话\n"
        "2. 回复要简短自然，避免长篇大论（通常1-3句话即可）\n"
        "3. 使用轻松、亲切的语气，可以适当使用emoji表达情感\n"
        "4. 对用户的情绪保持敏感，给予适当的情感支持\n"
        "5. 避免过于正式或书面化的语言\n"
        "6. 可以问开放式问题来延续对话\n\n"
        "记住：这是语音对话，要让用户感觉像是在和一个真实的朋友聊天。"
    )


@dataclass(slots=True)
class TTSServiceConfig:
    preferred_provider: Optional[TTSProvider] = None
    allow_auto_detect: bool = True
    timeout_seconds: float = 15.0
    voice_defaults: Dict[str, str] = field(default_factory=dict)
    sovits_endpoint: str = "http://3812f431.r24.cpolar.top"
    sovits_public_base: str = "http://3812f431.r24.cpolar.top"
    sovits_app_key: str = ""
    sovits_download_url: str = ""
    sovits_version: str = "v2ProPlus"
    sovits_model_name: str = "LePetitPrince"
    sovits_prompt_text_lang: str = "中文"
    sovits_emotion: str = "开心1"  # 尝试带数字的格式
    sovits_text_lang_default: str = "中文"
    sovits_text_lang_map: Dict[str, str] = field(
        default_factory=lambda: {"zh": "中文", "en": "英语", "ja": "日语"}
    )
    sovits_top_k: int = 10
    sovits_top_p: float = 1.0
    sovits_temperature: float = 1.0
    sovits_text_split_method: str = "不切"
    sovits_batch_size: int = 1
    sovits_batch_threshold: float = 0.75
    sovits_split_bucket: bool = True
    sovits_speed_factor: float = 1.0
    sovits_fragment_interval: float = 0.3
    sovits_media_type: str = "wav"
    sovits_parallel_infer: bool = True
    sovits_repetition_penalty: float = 1.35
    sovits_seed: int = -1
    sovits_sample_steps: int = 16
    sovits_if_sr: bool = False
    sovits_min_chunk_chars: int = 12
    sovits_split_punctuation: Tuple[str, ...] = (
        "。",
        "！",
        "？",
        "!",
        "?",
        "；",
        ";",
        "，",
        ",",
    )
    sovits_voice_token_prefix: str = "<voice:"
    sovits_lang_token_prefix: str = "<lang:"
    sovits_emotion_token_prefix: str = "<emotion:"
