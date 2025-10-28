from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState

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
fusion_service = EmotionFusionService(FusionConfig())
avatar = AvatarOrchestrator(AvatarConfig())
memory = AgentMemory(AgentConfig())
llm_service = LLMService(LLMServiceConfig())
tts_service = TTSService(TTSServiceConfig())
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
    fusion=fusion_service,
    avatar=avatar,
    agent=agent,
)
chat_service = ChatService(agent=agent, pipeline=pipeline)
webrtc_hub = WebRTCSignalHub()

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
    return await chat.add_user_message(thread_id, payload.text, payload.language)


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


@app.post("/webrtc/{room_id}/answer", response_model=WebRTCStateOut, status_code=202)
async def publish_answer(
    room_id: str,
    payload: WebRTCAnswer,
    hub: WebRTCSignalHub = Depends(get_webrtc_hub),
) -> WebRTCStateOut:
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
    hub: WebRTCSignalHub = Depends(get_webrtc_hub),
) -> WebRTCStateOut:
    state = await hub.add_candidate(room_id, payload)
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
    hub: WebRTCSignalHub = Depends(get_webrtc_hub),
) -> WebRTCStateOut:
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
