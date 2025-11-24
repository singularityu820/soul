"""Dependency injection and service initialization."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from .config import (
    AgentConfig,
    AvatarConfig,
    EEGClassifierConfig,
    EEGStreamConfig,
    FaceEmotionConfig,
    FusionConfig,
    LLMServiceConfig,
    TTSServiceConfig,
)
from .services.agent import AgentMemory, ConversationalAgent, LLMService, TTSService
from .services.agent.asr import ASRService
from .services.chat.service import ChatService
from .services.chat.storage import ChatStorage
from .services.emotion import (
    AvatarOrchestrator,
    EmotionFusionService,
    EmotionPipeline,
    EEGEmotionClassifier,
    EEGStreamTool,
    FaceEmotionTool,
    create_eeg_processor,
)
from .services.emotion.eeg_waveform import EEGWaveformService
from .services.voice import VoiceStreamHub

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")
load_dotenv(Path(__file__).parent.parent / "baidu_api_config.env")

# ============================================================================
# Global Service Instances (Singletons)
# ============================================================================

# EEG components
eeg_stream = EEGStreamTool(EEGStreamConfig())
eeg_classifier = EEGEmotionClassifier(EEGClassifierConfig())

# Face emotion with Baidu API
baidu_api_key = os.getenv("BAIDU_API_KEY")
baidu_secret_key = os.getenv("BAIDU_SECRET_KEY")
face_tool = FaceEmotionTool(
    FaceEmotionConfig(), 
    use_deepface=True,
    use_baidu_api=True,
    baidu_api_key=baidu_api_key,
    baidu_secret_key=baidu_secret_key
)

# Emotion processing
fusion_service = EmotionFusionService(FusionConfig())
avatar = AvatarOrchestrator(AvatarConfig())

# Agent and LLM
memory = AgentMemory(AgentConfig())
llm_service = LLMService(LLMServiceConfig())
tts_service = TTSService(TTSServiceConfig())
asr_service = ASRService()
agent = ConversationalAgent(
    memory,
    AgentConfig(),
    llm_service=llm_service,
    tts_service=tts_service,
)

# Pipeline
pipeline = EmotionPipeline(
    eeg_stream=eeg_stream,
    eeg_classifier=eeg_classifier,
    face_tool=face_tool,
    fusion=fusion_service,
    avatar=avatar,
    agent=agent,
)

# Chat services
chat_service = ChatService(agent=agent, pipeline=pipeline)
chat_storage = ChatStorage()

# EEG waveform service
eeg_waveform_service = EEGWaveformService()

# Real EEG processor
real_eeg_processor = create_eeg_processor()

# Voice stream hub
voice_stream_hub = VoiceStreamHub()

# Log service initialization
logger.info(
    "LLM provider detected: %s (%s)",
    llm_service.provider.value,
    llm_service.detection_reason(),
)
logger.info(
    "TTS provider detected: %s (%s)",
    tts_service.provider.value,
    tts_service.detection_reason(),
)
logger.info(
    "ASR provider detected: %s",
    asr_service.provider.value,
)


# ============================================================================
# Dependency Getters
# ============================================================================

async def get_pipeline() -> EmotionPipeline:
    return pipeline


async def get_memory() -> AgentMemory:
    return memory


async def get_agent() -> ConversationalAgent:
    return agent


async def get_chat_service() -> ChatService:
    return chat_service


def get_chat_storage() -> ChatStorage:
    return chat_storage


def get_eeg_waveform_service() -> EEGWaveformService:
    return eeg_waveform_service


def get_real_eeg_processor():
    return real_eeg_processor


def get_voice_stream_hub() -> VoiceStreamHub:
    return voice_stream_hub


def get_llm_service() -> LLMService:
    return llm_service


def get_tts_service() -> TTSService:
    return tts_service


def get_asr_service() -> ASRService:
    return asr_service


def get_face_tool() -> FaceEmotionTool:
    return face_tool
