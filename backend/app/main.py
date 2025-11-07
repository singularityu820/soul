from __future__ import annotations

import asyncio
<<<<<<< HEAD
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState

=======
import json
import logging
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional
import uuid

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.websockets import WebSocketState

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")

>>>>>>> origin/main
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
from .schemas import (
    ChatEvent,
    ChatMessage,
    ChatMessageIn,
    ChatThreadCreateIn,
    ChatThreadOut,
    FaceObservationIn,
    MemorySnapshotOut,
    PipelineEvent,
    WebRTCAnswer,
    WebRTCCandidate,
    WebRTCOffer,
    WebRTCStateOut,
    UserMessageIn,
)
<<<<<<< HEAD
from .services.agent import ConversationalAgent
from .services.avatar import AvatarOrchestrator
from .services.eeg import EEGEmotionClassifier, EEGStreamTool
from .services.face import FaceEmotionTool
from .services.fusion import EmotionFusionService
from .services.memory import AgentMemory
from .services.pipeline import EmotionPipeline
from .services.llm import LLMService
from .services.tts import TTSService
from .services.chat import ChatService
from .services.webrtc import WebRTCSignalHub
from .services.speech import SpeechEmotionTool  # <-- 1. 已添加导入
=======
from .services.agent import AgentMemory, ConversationalAgent, LLMService, TTSService
from .services.agent.asr import ASRService
from .services.chat.service import ChatService
from .services.emotion import (
    AvatarOrchestrator,
    EmotionFusionService,
    EmotionPipeline,
    EEGEmotionClassifier,
    EEGStreamTool,
    FaceEmotionTool,
)
from .services.realtime.webrtc import WebRTCSignalHub
from .services.realtime.session import AgentWebRTCSession
from .services.realtime.voice_stream import VoiceStreamHub, VoiceStreamSession
>>>>>>> origin/main

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        await pipeline.start()
        yield
    finally:
        await pipeline.stop()


app = FastAPI(title="Soul Emotion Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global singletons for demonstration; replace with DI container in production.
eeg_stream = EEGStreamTool(EEGStreamConfig())
eeg_classifier = EEGEmotionClassifier(EEGClassifierConfig())
face_tool = FaceEmotionTool(FaceEmotionConfig())
<<<<<<< HEAD
speech_tool = SpeechEmotionTool()  # <-- 2. 已实例化 speech_tool
=======
>>>>>>> origin/main
fusion_service = EmotionFusionService(FusionConfig())
avatar = AvatarOrchestrator(AvatarConfig())
memory = AgentMemory(AgentConfig())
llm_service = LLMService(LLMServiceConfig())
tts_service = TTSService(TTSServiceConfig())
<<<<<<< HEAD
=======
asr_service = ASRService()
>>>>>>> origin/main
agent = ConversationalAgent(
    memory,
    AgentConfig(),
    llm_service=llm_service,
    tts_service=tts_service,
)
pipeline = EmotionPipeline(
    eeg_stream=eeg_stream,
    eeg_classifier=eeg_classifier,
    face_tool=face_tool,
<<<<<<< HEAD
    speech_tool=speech_tool,  # <-- 3. 已将 speech_tool 注入 pipeline
=======
>>>>>>> origin/main
    fusion=fusion_service,
    avatar=avatar,
    agent=agent,
)
chat_service = ChatService(agent=agent, pipeline=pipeline)
webrtc_hub = WebRTCSignalHub()
<<<<<<< HEAD
=======
voice_stream_hub = VoiceStreamHub()

# WebRTC 会话管理
webrtc_sessions: dict[str, AgentWebRTCSession] = {}
active_webrtc_sessions = 0

# 跟踪客户端与房间 ID 的映射，兼容前端传入 null 等占位值
_client_room_map: dict[str, str] = {}
_client_room_lock = asyncio.Lock()
_INVALID_ROOM_TOKENS = {"", "null", "undefined"}


def _client_key(host: str | None) -> str:
    return host or "unknown"


async def _resolve_room_id(
    room_id: str,
    *,
    request: Request | None = None,
    websocket: WebSocket | None = None,
    allow_create: bool = False,
) -> str:
    raw = (room_id or "").strip()
    client = None
    if request and request.client:
        client = request.client
    elif websocket and websocket.client:
        client = websocket.client

    host = client.host if client else None
    key = _client_key(host)

    if raw and raw.lower() not in _INVALID_ROOM_TOKENS:
        if host:
            async with _client_room_lock:
                _client_room_map[key] = raw
        return raw

    if host:
        async with _client_room_lock:
            existing = _client_room_map.get(key)
            if existing:
                return existing
            if allow_create:
                new_room = uuid.uuid4().hex
                _client_room_map[key] = new_room
                logger.warning(
                    "Received invalid room id from %s. Generated new room: %s",
                    key,
                    new_room,
                )
                return new_room

    if allow_create:
        new_room = uuid.uuid4().hex
        logger.warning("Received invalid room id. Generated new room: %s", new_room)
        return new_room

    raise HTTPException(status_code=400, detail="Invalid WebRTC room id")


async def _release_room_id(room_id: str) -> None:
    async with _client_room_lock:
        stale_keys = [k for k, v in _client_room_map.items() if v == room_id]
        for key in stale_keys:
            _client_room_map.pop(key, None)


async def _release_client_mapping(request: Request | None = None) -> None:
    if not request or not request.client:
        return
    host = request.client.host
    key = _client_key(host)
    async with _client_room_lock:
        _client_room_map.pop(key, None)
>>>>>>> origin/main

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
<<<<<<< HEAD
=======
logger.info(
    "ASR provider detected: %s",
    asr_service.provider.value,
)
>>>>>>> origin/main


async def get_pipeline() -> EmotionPipeline:
    return pipeline


async def get_memory() -> AgentMemory:
    return memory


async def get_agent() -> ConversationalAgent:
    return agent


async def get_chat_service() -> ChatService:
    return chat_service


async def get_webrtc_hub() -> WebRTCSignalHub:
    return webrtc_hub


<<<<<<< HEAD
=======
async def fetch_audio_from_url(url: str) -> bytes | None:
    """
    从 URL 下载音频数据并转换为 PCM 格式。
    
    Args:
        url: 音频文件 URL (可能是 WAV, MP3 等)
    
    Returns:
        PCM 16-bit 音频数据，如果失败返回 None
    """
    try:
        # 跳过占位 URL
        if url.startswith(("sandbox://", "empty://", "error://", "missing-key://")):
            logger.debug("Skipping placeholder audio URL: %s", url)
            return None
        
        # 下载音频文件
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if not response.is_success:
                logger.error("Failed to download audio from %s: %s", url, response.status_code)
                return None
            
            audio_data = response.content
            
        # TODO: 如果需要格式转换（WAV → PCM），可以使用 av 库
        # 当前假设 TTS 返回的是 WAV 格式，直接返回
        # 实际使用中可能需要解析 WAV header 并提取 PCM 数据
        
        logger.info("Downloaded %d bytes of audio from %s", len(audio_data), url)
        return audio_data
        
    except Exception as e:
        logger.exception("Error fetching audio from %s: %s", url, e)
        return None


>>>>>>> origin/main
@app.get("/health")
async def health(pipeline: EmotionPipeline = Depends(get_pipeline)) -> dict[str, str | None]:
    state = pipeline.latest_state
    return {
        "status": "ok",
        "emotion": state.label if state else None,
        "confidence": f"{state.confidence:.2f}" if state else None,
    }


@app.post("/ingest/face")
async def ingest_face(
    payload: FaceObservationIn,
    pipeline: EmotionPipeline = Depends(get_pipeline),
) -> dict[str, str]:
    await pipeline.update_face_observation(
        label=payload.label,
        confidence=payload.confidence,
        intensity=payload.intensity,
        faces_detected=payload.faces_detected,
    )
    return {"status": "accepted"}


@app.post("/agent/user-message")
async def user_message(
    payload: UserMessageIn,
    agent: ConversationalAgent = Depends(get_agent),
) -> dict[str, str]:
    await agent.ingest_user_message(payload.text)
    return {"status": "recorded"}


@app.get("/memory/snapshot", response_model=MemorySnapshotOut)
async def memory_snapshot(memory: AgentMemory = Depends(get_memory)) -> MemorySnapshotOut:
    records = memory.snapshot()
    return MemorySnapshotOut(recent_events=records, size=memory.count())


@app.get("/chat/threads", response_model=list[ChatThreadOut])
async def list_threads(chat: ChatService = Depends(get_chat_service)) -> list[ChatThreadOut]:
    return await chat.list_threads()


@app.post("/chat/threads", response_model=ChatThreadOut, status_code=201)
async def create_thread(
    payload: ChatThreadCreateIn,
    chat: ChatService = Depends(get_chat_service),
) -> ChatThreadOut:
    return await chat.create_thread(payload.title, payload.participants)


@app.get("/chat/threads/{thread_id}", response_model=ChatThreadOut)
async def get_thread(
    thread_id: str,
    chat: ChatService = Depends(get_chat_service),
) -> ChatThreadOut:
    thread = await chat.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@app.get("/chat/threads/{thread_id}/messages", response_model=list[ChatMessage])
async def get_messages(
    thread_id: str,
    limit: int = 100,
    chat: ChatService = Depends(get_chat_service),
) -> list[ChatMessage]:
    thread = await chat.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return await chat.history(thread_id, limit=limit)


@app.post("/chat/threads/{thread_id}/messages", response_model=ChatMessage, status_code=201)
async def post_message(
    thread_id: str,
    payload: ChatMessageIn,
    chat: ChatService = Depends(get_chat_service),
) -> ChatMessage:
    thread = await chat.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
<<<<<<< HEAD
    return await chat.add_user_message(thread_id, payload.text, payload.language)
=======
    message = await chat.add_user_message(thread_id, payload.text, payload.language)
    
    # 如果存在对应的 WebRTC 会话，推送 TTS 音频
    room_id = f"{thread_id}-voice"
    if room_id in webrtc_sessions:
        session = webrtc_sessions[room_id]
        # TODO: 从 agent 响应中获取 TTS 音频并推送
        # agent_response = await agent.respond_with_context(...)
        # if agent_response.audio_segments:
        #     for segment_url in agent_response.audio_segments:
        #         audio_data = await fetch_audio(segment_url)
        #         await session.push_tts_audio(audio_data)
        logger.info("WebRTC session active for room %s, ready for TTS push", room_id)
    
    return message
>>>>>>> origin/main


@app.websocket("/ws/pipeline")
async def pipeline_stream(
    websocket: WebSocket,
    pipeline: EmotionPipeline = Depends(get_pipeline),
) -> None:
    await websocket.accept()
    queue = pipeline.subscribe()

    try:
        if pipeline.latest_state:
            initial_event = PipelineEvent(
                emotion=pipeline.latest_state,
                avatar=pipeline.avatar.translate(pipeline.latest_state),
                agent_message=pipeline.latest_message,
            )
            await websocket.send_json(jsonable_encoder(initial_event))

        while True:
            event = await queue.get()
            await websocket.send_json(jsonable_encoder(event))
    except WebSocketDisconnect:
        logger.debug("Pipeline websocket disconnected")
    except Exception:
        logger.exception("Pipeline websocket encountered an error")
    finally:
        pipeline.unsubscribe(queue)
        if websocket.application_state != WebSocketState.DISCONNECTED:
            await websocket.close()


@app.websocket("/ws/chat")
async def chat_stream(
    websocket: WebSocket,
    chat: ChatService = Depends(get_chat_service),
) -> None:
    await websocket.accept()
    thread_id = websocket.query_params.get("thread_id")
    queue = await chat.subscribe()

    try:
        if thread_id:
            history = await chat.history(thread_id)
            for message in history:
                await websocket.send_json(
                    jsonable_encoder(ChatEvent(thread_id=thread_id, message=message))
                )

        while True:
            event = await queue.get()
            if thread_id and event.thread_id != thread_id:
                continue
            await websocket.send_json(jsonable_encoder(event))
    except WebSocketDisconnect:
        logger.debug("Chat websocket disconnected")
    except Exception:
        logger.exception("Chat websocket encountered an error")
    finally:
        chat.unsubscribe(queue)
        if websocket.application_state != WebSocketState.DISCONNECTED:
            await websocket.close()


<<<<<<< HEAD
@app.post("/webrtc/{room_id}/offer", response_model=WebRTCStateOut, status_code=202)
async def publish_offer(
    room_id: str,
    payload: WebRTCOffer,
    hub: WebRTCSignalHub = Depends(get_webrtc_hub),
) -> WebRTCStateOut:
    state = await hub.publish_offer(room_id, payload)
    return WebRTCStateOut(
        room_id=state.room_id,
        offer=state.offer,
        answer=state.answer,
        candidates=state.candidates,
        updated_at=state.updated_at,
    )
=======
@app.post("/webrtc/{room_id}/offer", status_code=200)
async def publish_offer(
    room_id: str,
    payload: WebRTCOffer,
    request: Request,
    hub: WebRTCSignalHub = Depends(get_webrtc_hub),
    agent_service: ConversationalAgent = Depends(get_agent),
) -> dict:
    """
    处理来自客户端的 WebRTC offer，创建 aiortc 会话并返回 answer。
    集成完整的语音对话流程: 麦克风 → ASR → LLM → TTS → WebRTC
    """
    room_id = await _resolve_room_id(room_id, request=request, allow_create=True)
    mode = (payload.metadata or {}).get("mode", "voice") if payload.metadata else "voice"
    mode = str(mode).lower() if mode else "voice"
    if mode not in {"voice", "video"}:
        logger.warning("Unsupported WebRTC mode '%s', falling back to voice", mode)
        mode = "voice"

    try:
        # 音频接收回调：完整的语音对话链路
        async def on_audio_received(audio_bytes: bytes) -> None:
            try:
                logger.info("Processing audio chunk: %d bytes from room %s", len(audio_bytes), room_id)
                
                # 1. ASR: 语音转文字
                text = await asr_service.transcribe(audio_bytes, language="zh", sample_rate=16000)
                if not text or text.startswith("[沙盒模式]"):
                    logger.info("ASR returned empty or sandbox result: %s", text)
                    return
                
                logger.info("ASR transcript: %s", text)
                
                # 2. 存储用户消息到 memory
                await agent_service.ingest_user_message(text)
                
                # 3. LLM: 获取 agent 回复
                emotion = pipeline.latest_state
                agent_response = await agent_service.respond_with_context(
                    emotion,
                    user_text=text,
                )
                logger.info("Agent response: %s", agent_response.text)
                
                # 4. TTS: 将回复转换为语音
                if agent_response.audio_segments:
                    # 使用分段音频（GPT-SoVITs）
                    for segment_url in agent_response.audio_segments:
                        # 下载音频数据
                        audio_data = await fetch_audio_from_url(segment_url)
                        if audio_data:
                            # 推送到 WebRTC
                            session = webrtc_sessions.get(room_id)
                            if session:
                                await session.push_tts_audio(audio_data)
                elif agent_response.audio_reference:
                    # 使用单个音频引用
                    audio_data = await fetch_audio_from_url(agent_response.audio_reference)
                    if audio_data:
                        session = webrtc_sessions.get(room_id)
                        if session:
                            await session.push_tts_audio(audio_data)
                else:
                    logger.warning("No TTS audio generated for response")
                    
            except Exception as e:
                logger.exception("Error processing audio in room %s: %s", room_id, e)

        # 创建或获取会话
        global active_webrtc_sessions
        newly_created = room_id not in webrtc_sessions

        if room_id in webrtc_sessions:
            session = webrtc_sessions[room_id]
            await session.close()

        async def on_local_candidate(candidate: Optional[WebRTCCandidate]) -> None:
            if candidate is None:
                logger.info("Local ICE candidate gathering finished for room: %s", room_id)
                return
            await hub.add_candidate(room_id, candidate)

        session = AgentWebRTCSession(
            room_id=room_id,
            on_audio_received=on_audio_received,
            on_local_candidate=on_local_candidate,
            mode=mode,
        )
        webrtc_sessions[room_id] = session

        if newly_created:
            active_webrtc_sessions += 1
            if active_webrtc_sessions == 1:
                pipeline.enable_proactive()

        # 处理 offer 并生成 answer
        answer_sdp = await session.handle_offer(payload.sdp)
        answer_model = WebRTCAnswer(sdp=answer_sdp, metadata={"mode": mode})

        # 同时更新信令 hub（保持向后兼容）
        state = await hub.publish_offer(room_id, payload)
        await hub.publish_answer(room_id, answer_model)

        logger.info("WebRTC offer processed for room: %s", room_id)

        return {
            "type": "answer",
            "sdp": answer_sdp,
            "room_id": room_id,
            "mode": mode,
        }

    except Exception as e:
        session = webrtc_sessions.pop(room_id, None)
        if session:
            with contextlib.suppress(Exception):
                await session.close()
        await _release_room_id(room_id)
        if newly_created:
            active_webrtc_sessions = max(0, active_webrtc_sessions - 1)
            if active_webrtc_sessions == 0:
                pipeline.disable_proactive()
        logger.exception("Failed to process WebRTC offer for room: %s", room_id)
        raise HTTPException(status_code=500, detail=f"Failed to process offer: {str(e)}")
>>>>>>> origin/main


@app.post("/webrtc/{room_id}/answer", response_model=WebRTCStateOut, status_code=202)
async def publish_answer(
    room_id: str,
    payload: WebRTCAnswer,
<<<<<<< HEAD
    hub: WebRTCSignalHub = Depends(get_webrtc_hub),
) -> WebRTCStateOut:
=======
    request: Request,
    hub: WebRTCSignalHub = Depends(get_webrtc_hub),
) -> WebRTCStateOut:
    room_id = await _resolve_room_id(room_id, request=request, allow_create=False)
>>>>>>> origin/main
    state = await hub.publish_answer(room_id, payload)
    return WebRTCStateOut(
        room_id=state.room_id,
        offer=state.offer,
        answer=state.answer,
        candidates=state.candidates,
        updated_at=state.updated_at,
    )


@app.post("/webrtc/{room_id}/candidate", response_model=WebRTCStateOut, status_code=202)
async def publish_candidate(
    room_id: str,
    payload: WebRTCCandidate,
<<<<<<< HEAD
    hub: WebRTCSignalHub = Depends(get_webrtc_hub),
) -> WebRTCStateOut:
    state = await hub.add_candidate(room_id, payload)
=======
    request: Request,
    hub: WebRTCSignalHub = Depends(get_webrtc_hub),
) -> WebRTCStateOut:
    room_id = await _resolve_room_id(room_id, request=request, allow_create=False)
    state = await hub.add_candidate(room_id, payload)

    session = webrtc_sessions.get(room_id)
    if session:
        await session.add_remote_candidate(payload)
    else:
        logger.warning("Received ICE candidate for inactive room: %s", room_id)

>>>>>>> origin/main
    return WebRTCStateOut(
        room_id=state.room_id,
        offer=state.offer,
        answer=state.answer,
        candidates=state.candidates,
        updated_at=state.updated_at,
    )


@app.get("/webrtc/{room_id}", response_model=WebRTCStateOut)
async def get_webrtc_state(
    room_id: str,
<<<<<<< HEAD
    hub: WebRTCSignalHub = Depends(get_webrtc_hub),
) -> WebRTCStateOut:
=======
    request: Request,
    hub: WebRTCSignalHub = Depends(get_webrtc_hub),
) -> WebRTCStateOut:
    room_id = await _resolve_room_id(room_id, request=request, allow_create=False)
>>>>>>> origin/main
    state = await hub.get_state(room_id)
    if not state:
        raise HTTPException(status_code=404, detail="Room not found")
    return WebRTCStateOut(
        room_id=state.room_id,
        offer=state.offer,
        answer=state.answer,
        candidates=state.candidates,
        updated_at=state.updated_at,
    )


@app.websocket("/ws/webrtc/{room_id}")
async def webrtc_signaling(
    websocket: WebSocket,
    room_id: str,
    hub: WebRTCSignalHub = Depends(get_webrtc_hub),
) -> None:
<<<<<<< HEAD
=======
    try:
        room_id = await _resolve_room_id(room_id, websocket=websocket, allow_create=False)
    except HTTPException:
        await websocket.close(code=1008, reason="Invalid room id")
        return
>>>>>>> origin/main
    await websocket.accept()
    queue = await hub.subscribe(room_id)

    try:
        state = await hub.get_state(room_id)
        if state:
            await websocket.send_json(
                jsonable_encoder(
                    WebRTCStateOut(
                        room_id=state.room_id,
                        offer=state.offer,
                        answer=state.answer,
                        candidates=state.candidates,
                        updated_at=state.updated_at,
                    )
                )
            )

        while True:
            message = await queue.get()
            await websocket.send_json(jsonable_encoder(message))
    except WebSocketDisconnect:
        logger.debug("WebRTC websocket disconnected")
    except Exception:
        logger.exception("WebRTC websocket encountered an error")
    finally:
        hub.unsubscribe(room_id, queue)
        if websocket.application_state != WebSocketState.DISCONNECTED:
            await websocket.close()


<<<<<<< HEAD
if __name__ == "__main__":
    # When running as a module (python -m app.main) this block will execute
    # and start a development server. Avoid running the file directly via
    # Two-way data binding in Vue.js (v-model)    # `python path/to/main.py` because relative imports will fail; instead
    # run from the `backend` directory with:
    #   python -m app.main
    # or use uvicorn directly:
    #   python -m uvicorn app.main:app --reload --port 8000
    try:
        import uvicorn

        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
    except Exception:
        # If uvicorn isn't available, fall back to a helpful message.
        print("Start the app with: python -m uvicorn app.main:app --reload --port 8000")
=======
@app.delete("/webrtc/{room_id}")
async def close_webrtc_session(room_id: str, request: Request) -> dict:
    """关闭 WebRTC 会话并释放资源"""
    resolved_id: str | None = None
    try:
        room_id = await _resolve_room_id(room_id, request=request, allow_create=False)
        resolved_id = room_id
    except HTTPException:
        logger.info("Received delete for invalid room id; ignoring")

    if room_id in webrtc_sessions:
        session = webrtc_sessions[room_id]
        await session.close()
        del webrtc_sessions[room_id]
        global active_webrtc_sessions
        if active_webrtc_sessions > 0:
            active_webrtc_sessions -= 1
            if active_webrtc_sessions == 0:
                pipeline.disable_proactive()
        logger.info("Closed WebRTC session for room: %s", room_id)
        await _release_room_id(room_id)
        await _release_client_mapping(request)
        return {"status": "closed", "room_id": room_id}

    if resolved_id:
        await _release_room_id(resolved_id)

    await _release_client_mapping(request)
    return {"status": "missing", "room_id": room_id}


# ============================================================================
# HTTP 音频上传接口 (WebRTC 替代方案)
# ============================================================================

@app.post("/audio/conversation")
async def audio_conversation(
    audio: UploadFile = File(...),
    thread_id: Optional[str] = Form(None),
    voice: str = Form("zhichu_emo"),
    locale: str = Form("zh-CN"),
) -> dict:
    """
    音频对话接口 - WebRTC 的替代方案
    
    上传音频文件,执行 ASR → LLM → TTS 流程,返回响应音频
    
    Args:
        audio: 音频文件 (WAV, MP3, OGG 等)
        thread_id: 对话线程 ID (可选,用于保持上下文)
        voice: TTS 语音 (默认: zhichu_emo)
        locale: 语音地区 (默认: zh-CN)
    
    Returns:
        {
            "transcript": "用户说的话",
            "response_text": "AI 回复文本",
            "audio_url": "响应音频的 URL 或 base64"
        }
    """
    try:
        # 1. 读取音频数据
        audio_data = await audio.read()
        logger.info(f"Received audio upload: {len(audio_data)} bytes, content_type={audio.content_type}")
        
        # 2. ASR 转录
        logger.info("Starting ASR transcription...")
        transcript = await asr_service.transcribe(audio_data)
        logger.info(f"ASR transcript: {transcript}")
        
        if not transcript or not transcript.strip():
            raise HTTPException(status_code=400, detail="无法识别语音内容")
        
        # 3. LLM 生成响应
        logger.info("Generating LLM response...")
        
        # 简单对话(不使用 agent 的复杂流程)
        # 构建对话上下文
        if thread_id:
            # 获取最近几条消息作为上下文
            try:
                history_response = await httpx.AsyncClient().get(
                    f"http://localhost:8000/chat/threads/{thread_id}/messages",
                    timeout=5.0
                )
                if history_response.status_code == 200:
                    history = history_response.json()
                    context_messages = history[-5:] if len(history) > 5 else history
                    context = "\n".join([
                        f"{'用户' if msg.get('role') == 'user' else 'AI'}: {msg.get('content', '')}"
                        for msg in context_messages
                    ])
                    prompt = f"{context}\n用户: {transcript}\nAI:"
                else:
                    prompt = f"用户: {transcript}\nAI:"
            except:
                prompt = f"用户: {transcript}\nAI:"
        else:
            prompt = f"用户: {transcript}\nAI:"
        
        response_text = await llm_service.generate(prompt=prompt, temperature=0.7)
        logger.info(f"LLM response: {response_text}")
        
        # 4. TTS 合成
        logger.info("Synthesizing TTS audio...")
        tts_result = await tts_service.synthesize(
            text=response_text,
            voice=voice,
            locale=locale,
        )
        
        # 5. 返回结果
        return {
            "transcript": transcript,
            "response_text": response_text,
            "audio_reference": tts_result.audio_reference,
            "tts_provider": tts_result.provider.value,
            "voice": tts_result.voice,
            "locale": tts_result.locale,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audio conversation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理音频失败: {str(e)}")


@app.get("/audio/download")
async def download_audio(reference: str) -> Response:
    """
    下载音频文件
    
    Args:
        reference: 音频引用 (URL 或文件路径)
    
    Returns:
        音频文件内容
    """
    try:
        # 如果是 HTTP URL,下载它
        if reference.startswith("http://") or reference.startswith("https://"):
            async with httpx.AsyncClient() as client:
                response = await client.get(reference)
                response.raise_for_status()
                return Response(
                    content=response.content,
                    media_type="audio/wav",
                    headers={
                        "Content-Disposition": f'attachment; filename="response.wav"'
                    }
                )
        
        # 如果是本地文件路径
        file_path = Path(reference)
        if file_path.exists():
            with open(file_path, "rb") as f:
                content = f.read()
            return Response(
                content=content,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": f'attachment; filename="{file_path.name}"'
                }
            )
        
        raise HTTPException(status_code=404, detail="音频文件不存在")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audio download failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"下载音频失败: {str(e)}")


# ============================================================================
# WebSocket 实时语音流接口
# ============================================================================

@app.websocket("/ws/voice-stream")
async def voice_stream_endpoint(websocket: WebSocket):
    """
    实时语音流 WebSocket 端点
    
    客户端消息格式:
    - JSON: {"type": "start", "session_id": "xxx", "thread_id": "xxx"}
    - JSON: {"type": "stop"}
    - Binary: 原始音频数据 (PCM 16bit 16kHz mono)
    
    服务端消息格式:
    - JSON: {"type": "transcript", "text": "...", "is_final": true}
    - JSON: {"type": "response", "text": "..."}
    - JSON: {"type": "status", "status": "transcribing|generating|synthesizing"}
    - JSON: {"type": "error", "message": "..."}
    - Binary: TTS 音频数据
    """
    await websocket.accept()
    session_id = None
    session: Optional[VoiceStreamSession] = None
    
    try:
        logger.info("Voice stream WebSocket connected")
        
        # 等待客户端发送 start 消息
        data = await websocket.receive_json()
        if data.get("type") != "start":
            await websocket.send_json({"type": "error", "message": "Expected 'start' message"})
            await websocket.close()
            return
        
        session_id = data.get("session_id") or str(uuid.uuid4())
        thread_id = data.get("thread_id")
        
        logger.info(f"Starting voice stream session: {session_id}, thread_id: {thread_id}")
        
        # 定义音频处理回调
        async def on_transcript(audio_data: bytes) -> str:
            """处理音频数据: ASR → LLM → TTS"""
            try:
                # 1. ASR 转录
                transcript = await asr_service.transcribe(audio_data)
                logger.info(f"Transcript: {transcript}")
                
                if not transcript or not transcript.strip():
                    return ""
                
                # 发送转录结果
                await session.send_transcript(transcript, is_final=True)
                
                # 2. LLM 生成响应 (流式)
                await session.send_status("generating")
                
                # 使用语音聊天专用的 system prompt
                voice_system_prompt = llm_service.config.voice_chat_system_prompt
                
                # 构建消息列表
                messages = [
                    {"role": "system", "content": voice_system_prompt}
                ]
                
                # 添加历史上下文（可选）
                if thread_id:
                    try:
                        history_response = await httpx.AsyncClient().get(
                            f"http://localhost:8000/chat/threads/{thread_id}/messages",
                            timeout=5.0
                        )
                        if history_response.status_code == 200:
                            history = history_response.json()
                            # 只取最近3轮对话作为上下文
                            context_messages = history[-6:] if len(history) > 6 else history
                            for msg in context_messages:
                                role = "user" if msg.get('role') == 'user' else "assistant"
                                content = msg.get('content', '')
                                if content:
                                    messages.append({"role": role, "content": content})
                    except Exception as e:
                        logger.warning(f"Failed to load history: {e}")
                
                # 添加当前用户输入
                messages.append({"role": "user", "content": transcript})
                
                # 2. LLM 流式生成 + 智能断句 + 立即 TTS
                await session.send_status("generating")
                
                # 断句缓冲区
                sentence_buffer = []
                full_response = ""
                segment_count = 0
                
                # 断句标点符号
                BREAK_PUNCTUATION = {"。", "！", "？", "!", "?", "；", ";", "\n"}
                MIN_SENTENCE_LENGTH = 12  # 最小断句长度
                MAX_SENTENCE_LENGTH = 100  # 最大长度，超过强制断句
                
                def should_break_sentence(text: str) -> bool:
                    """判断是否应该断句"""
                    if len(text) < MIN_SENTENCE_LENGTH:
                        return False
                    
                    # 检查是否以断句标点结尾
                    if text and text[-1] in BREAK_PUNCTUATION:
                        return True
                    
                    # 检查特殊标记（语气、语言切换）
                    if "<emotion:" in text or "<lang:" in text or "<voice:" in text:
                        return True
                    
                    # 超长强制断句
                    if len(text) >= MAX_SENTENCE_LENGTH:
                        # 找最近的标点
                        for i in range(len(text) - 1, max(0, len(text) - 20), -1):
                            if text[i] in BREAK_PUNCTUATION:
                                return True
                        return True  # 实在没有标点就强制断
                    
                    return False
                
                async def process_sentence(sentence: str, seg_id: int):
                    """处理一个句子：TTS + 发送"""
                    try:
                        logger.info(f"[Sentence {seg_id}] Processing: {sentence[:50]}...")
                        
                        # TTS 合成
                        async for audio_url in tts_service.synthesize_stream(
                            text=sentence,
                            voice="zhichu_emo",
                            locale="zh-CN",
                        ):
                            logger.info(f"[Sentence {seg_id}] TTS generated: {audio_url}")
                            
                            # 发送音频 URL（不是二进制数据）
                            await session.send_message("tts_audio", {
                                "url": audio_url,
                                "segment_id": seg_id,
                                "text": sentence
                            })
                            
                    except Exception as e:
                        logger.error(f"[Sentence {seg_id}] TTS failed: {e}", exc_info=True)
                
                # 创建 keepalive 任务
                keepalive_task = None
                keepalive_running = True
                keepalive_count = 0
                
                async def send_keepalive():
                    """保持连接活跃"""
                    nonlocal keepalive_count
                    while keepalive_running:
                        await asyncio.sleep(2)
                        if keepalive_running:
                            try:
                                keepalive_count += 1
                                await session.send_status("generating")
                            except Exception as e:
                                logger.warning(f"Keepalive failed: {e}")
                                break
                
                try:
                    keepalive_task = asyncio.create_task(send_keepalive())
                    logger.info("[Voice Stream] Started LLM streaming with smart sentence breaking")
                    
                    # 流式接收 LLM 输出
                    async for chunk in llm_service.generate_stream(
                        prompt="",
                        messages=messages,
                        temperature=0.7
                    ):
                        sentence_buffer.append(chunk)
                        full_response += chunk
                        
                        # 发送 LLM chunk 给前端（用于实时显示）
                        await session.send_message("response_chunk", {"text": chunk})
                        
                        # 检查是否需要断句
                        current_text = "".join(sentence_buffer)
                        if should_break_sentence(current_text):
                            segment_count += 1
                            logger.info(f"[Voice Stream] Breaking sentence #{segment_count}: {current_text[:30]}...")
                            
                            # 立即处理这个句子（TTS + 发送）
                            await process_sentence(current_text.strip(), segment_count)
                            
                            # 清空缓冲区
                            sentence_buffer.clear()
                    
                    # 处理剩余的文本
                    remaining_text = "".join(sentence_buffer).strip()
                    if remaining_text:
                        segment_count += 1
                        logger.info(f"[Voice Stream] Processing remaining text as segment #{segment_count}")
                        await process_sentence(remaining_text, segment_count)
                    
                    logger.info(f"[Voice Stream] LLM complete. Generated {segment_count} segments. Full response: {full_response[:100]}...")
                    
                    # 发送完整响应
                    await session.send_response(full_response)
                    
                    # 发送完成标记
                    await session.send_message("generation_complete", {
                        "segments": segment_count,
                        "total_text": full_response
                    })
                    
                except Exception as e:
                    logger.error(f"[Voice Stream] Error in LLM streaming: {e}", exc_info=True)
                    await session.send_error(str(e))
                finally:
                    # 停止 keepalive
                    keepalive_running = False
                    if keepalive_task:
                        keepalive_task.cancel()
                        try:
                            await keepalive_task
                        except asyncio.CancelledError:
                            pass
                    logger.info(f"[Voice Stream] Stopped keepalive (sent {keepalive_count} pings)")
                
                await session.send_status("idle")
                return full_response
                
            except Exception as e:
                logger.error(f"Error in transcript callback: {e}", exc_info=True)
                await session.send_error(str(e))
                return ""
        
        # 创建会话
        session = await voice_stream_hub.create_session(
            websocket=websocket,
            session_id=session_id,
            on_transcript=on_transcript,
        )
        
        # 发送就绪消息
        await session.send_message("ready", {"session_id": session_id})
        
        # 接收音频流
        while not session._closed:
            message = await websocket.receive()
            
            # 检查断开连接消息
            if message.get("type") == "websocket.disconnect":
                logger.info(f"Client disconnected: {session_id}")
                break
            
            if "bytes" in message:
                # 二进制音频数据
                audio_data = message["bytes"]
                await session.handle_audio_data(audio_data)
                
            elif "text" in message:
                # JSON 控制消息
                data = json.loads(message["text"])
                
                if data.get("type") == "stop":
                    logger.info("Received stop signal")
                    break
                    
            else:
                logger.warning(f"Unknown message type: {message}")
        
    except WebSocketDisconnect:
        logger.info(f"Voice stream WebSocket disconnected: {session_id}")
    except RuntimeError as e:
        # 处理 "Cannot call receive once a disconnect message has been received" 错误
        if "disconnect" in str(e).lower():
            logger.info(f"Voice stream connection closed: {session_id}")
        else:
            logger.error(f"Voice stream runtime error: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Voice stream error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        if session_id:
            await voice_stream_hub.remove_session(session_id)
        try:
            await websocket.close()
        except:
            pass


>>>>>>> origin/main
