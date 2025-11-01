from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class EEGWaveform(BaseModel):
    channels: Dict[str, List[float]]
    sample_rate_hz: float = Field(ge=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChannelEmotion(BaseModel):
    source: Literal["eeg", "face", "fusion"]
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    mood_score: float = Field(ge=-1.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EmotionState(BaseModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    mood_score: float = Field(ge=-1.0, le=1.0)
    components: List[ChannelEmotion]
    waveform: Optional[EEGWaveform] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AvatarPose(BaseModel):
    expression: str
    pose: str
    energy: float = Field(ge=0.0, le=1.0)
    color_theme: str = "#ffffff"
    emphasis: Optional[str] = None


class AgentMessage(BaseModel):
    text: str
    voice_style: str
    language: str = "zh"
    emotion: str
    llm_provider: Optional[str] = None
    tts_provider: Optional[str] = None
    audio_reference: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    audio_segments: Optional[List[str]] = None


class PipelineEvent(BaseModel):
    emotion: EmotionState
    avatar: AvatarPose
    agent_message: Optional[AgentMessage] = None


class ChatThreadOut(BaseModel):
    thread_id: str
    title: str
    participants: List[str]
    last_message_at: datetime
    created_at: datetime


class ChatMessage(BaseModel):
    message_id: str
    thread_id: str
    role: Literal["user", "agent", "system"]
    text: str
    created_at: datetime
    language: str = "zh"
    emotion_label: Optional[str] = None
    emotion_score: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    voice_style: Optional[str] = None
    llm_provider: Optional[str] = None
    tts_provider: Optional[str] = None
    audio_reference: Optional[str] = None
    audio_segments: Optional[List[str]] = None


class ChatMessageIn(BaseModel):
    text: str
    language: str = "zh"


class ChatThreadCreateIn(BaseModel):
    title: str
    participants: List[str] = Field(default_factory=list)


class ChatEvent(BaseModel):
    type: Literal["message"] = "message"
    thread_id: str
    message: ChatMessage


class WebRTCOffer(BaseModel):
    type: Literal["offer"] = "offer"
    sdp: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WebRTCAnswer(BaseModel):
    type: Literal["answer"] = "answer"
    sdp: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WebRTCCandidate(BaseModel):
    candidate: str
    sdp_mid: Optional[str] = None
    sdp_mline_index: Optional[int] = None
    username_fragment: Optional[str] = None


class WebRTCStateOut(BaseModel):
    room_id: str
    offer: Optional[WebRTCOffer] = None
    answer: Optional[WebRTCAnswer] = None
    candidates: List[WebRTCCandidate] = Field(default_factory=list)
    updated_at: datetime


class FaceObservationIn(BaseModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    intensity: float = Field(ge=0.0, le=1.0)
    faces_detected: int = 1


class UserMessageIn(BaseModel):
    text: str
    language: str = "zh"


class MemoryRecordOut(BaseModel):
    text: str
    timestamp: datetime
    tags: List[str]
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class MemorySnapshotOut(BaseModel):
    recent_events: List[MemoryRecordOut]
    size: int
