from __future__ import annotations

import asyncio
import logging
import time
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional, Dict, List, Callable, Any
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
# Load Baidu API configuration
load_dotenv(Path(__file__).parent.parent / "baidu_api_config.env")

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
    UserMessageIn,
    InfoRequest,
    InfoResponse,
)
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
    RealEEGProcessor,
    create_eeg_processor,
)
from .services.emotion.eeg_waveform import EEGWaveformService
from .services.info_store import read_info, write_info

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# 音频队列Hook和实时语音流相关类
# ============================================================================

class AudioQueueHook:
    """
    音频队列Hook，实现音频片段的顺序播放和打断机制
    """
    
    def __init__(self):
        self.queue: List[Dict[str, Any]] = []  # 音频队列
        self.current: Optional[Dict[str, Any]] = None  # 当前播放的音频
        self.is_playing: bool = False  # 是否正在播放
        self.interrupted: bool = False  # 是否被中断
        self.lock = asyncio.Lock()  # 异步锁
        
    async def add_audio(self, audio_data: bytes, segment_id: int, text: str = "") -> None:
        """
        添加音频到队列
        
        Args:
            audio_data: 音频数据
            segment_id: 音频片段ID
            text: 对应的文本
        """
        async with self.lock:
            self.queue.append({
                "audio_data": audio_data,
                "segment_id": segment_id,
                "text": text,
                "timestamp": time.time()
            })
            logger.info(f"Added audio segment {segment_id} to queue, queue size: {len(self.queue)}")
    
    async def interrupt(self) -> None:
        """
        中断当前播放
        """
        async with self.lock:
            self.interrupted = True
            logger.info("Audio playback interrupted")
    
    async def clear_queue(self) -> None:
        """
        清空队列
        """
        async with self.lock:
            self.queue.clear()
            self.interrupted = True
            logger.info("Audio queue cleared")
    
    async def get_next(self) -> Optional[Dict[str, Any]]:
        """
        获取下一个音频片段
        """
        async with self.lock:
            if self.interrupted:
                self.queue.clear()
                self.interrupted = False
                return None
                
            if self.queue:
                return self.queue.pop(0)
            return None
    
    async def get_status(self) -> Dict[str, Any]:
        """
        获取队列状态
        """
        async with self.lock:
            return {
                "queue_size": len(self.queue),
                "is_playing": self.is_playing,
                "current_segment_id": self.current.get("segment_id") if self.current else None,
                "interrupted": self.interrupted
            }


class VoiceStreamSession:
    """
    实时语音流会话
    """
    
    def __init__(self, session_id: str, websocket: WebSocket, on_transcript: Callable):
        self.session_id = session_id
        self.websocket = websocket
        self.on_transcript = on_transcript
        self.audio_queue_hook = AudioQueueHook()
        self._closed = False
        self._last_audio_time = 0
        self._last_heartbeat = time.time()
        self._heartbeat_interval = 30  # 心跳间隔30秒
        self._message_queue = asyncio.Queue()  # 消息队列，确保按序发送
        self._audio_buffer: list[bytes] = []  # 原始 PCM 音频块
        self._buffered_bytes = 0
        self._sample_rate = 16000
        self._min_flush_seconds = 0.8  # 至少累积 ~0.8s 再送 ASR，避免 0.04s 空音频
        self._max_flush_seconds = 4.0  # 最多缓存 4s，防止高延迟
        self._min_flush_bytes = int(self._sample_rate * 2 * self._min_flush_seconds)
        self._max_flush_bytes = int(self._sample_rate * 2 * self._max_flush_seconds)
        self._chunks_since_last_flush = 0
        self._total_chunks = 0
        self._last_flush_time = time.time()
        self._message_sender_task = None
        self._heartbeat_task = None
        
    async def start_background_tasks(self):
        """启动后台任务"""
        self._message_sender_task = asyncio.create_task(self._message_sender())
        self._heartbeat_task = asyncio.create_task(self._heartbeat())
        
    async def stop_background_tasks(self):
        """停止后台任务"""
        if self._message_sender_task:
            self._message_sender_task.cancel()
            try:
                await self._message_sender_task
            except asyncio.CancelledError:
                pass
                
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
    
    async def _message_sender(self):
        """消息发送器，确保消息按序发送"""
        while not self._closed:
            try:
                # 等待消息，设置超时避免无限等待
                message = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
                await self.websocket.send_json(message)
                self._message_queue.task_done()
            except asyncio.TimeoutError:
                continue  # 超时继续循环
            except Exception as e:
                logger.error(f"Error sending message to {self.session_id}: {e}")
                break
    
    async def _heartbeat(self):
        """心跳机制"""
        while not self._closed:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                if not self._closed and time.time() - self._last_heartbeat > self._heartbeat_interval:
                    await self.send_message("ping", {})
                    self._last_heartbeat = time.time()
            except Exception as e:
                logger.error(f"Error sending heartbeat to {self.session_id}: {e}")
                break
    
    async def send_message(self, msg_type: str, data: Dict[str, Any]) -> None:
        """发送消息到客户端"""
        if self._closed:
            return
        try:
            # 将消息放入队列，确保按序发送
            await self._message_queue.put({
                "type": msg_type,
                "timestamp": time.time(),
                **data
            })
        except Exception as e:
            logger.error(f"Error queuing message to {self.session_id}: {e}")
    
    async def send_status(self, status: str) -> None:
        """发送状态消息"""
        await self.send_message("status", {"status": status})
    
    async def send_response(self, text: str) -> None:
        """发送完整响应"""
        await self.send_message("response", {"text": text})
    
    async def send_error(self, error: str) -> None:
        """发送错误消息"""
        await self.send_message("error", {"error": error})
    
    async def handle_audio_data(self, audio_data: bytes) -> None:
        """处理接收到的音频数据"""
        if not audio_data:
            return

        self._last_audio_time = time.time()
        chunk_bytes = len(audio_data)
        self._total_chunks += 1
        self._chunks_since_last_flush += 1
        self._audio_buffer.append(audio_data)
        self._buffered_bytes += chunk_bytes

        if self._chunks_since_last_flush % 50 == 0:
            buffered_seconds = self._buffered_bytes / (self._sample_rate * 2)
            logger.info(
                "[Voice Stream][RX] Buffered %.2fs across %d chunks (~%d bytes) since last flush",
                buffered_seconds,
                self._chunks_since_last_flush,
                self._buffered_bytes,
            )

        # 达到最小阈值时发送到 ASR，或者超过最大缓存直接强制发送
        if self._buffered_bytes >= self._max_flush_bytes:
            await self._flush_audio_buffer(reason="max-bytes", force=True)
        elif self._buffered_bytes >= self._min_flush_bytes:
            await self._flush_audio_buffer(reason="min-bytes", force=False)
    
    async def close(self) -> None:
        """关闭会话"""
        self._closed = True
        await self.stop_background_tasks()
        await self.audio_queue_hook.clear_queue()

    async def flush_pending_audio(self, reason: str = "manual") -> None:
        """强制刷新当前缓存的音频（用于 stop/断开场景）"""
        await self._flush_audio_buffer(reason=reason, force=True)

    async def _flush_audio_buffer(self, *, reason: str, force: bool) -> None:
        """将缓存音频发送到 ASR"""
        if self._buffered_bytes == 0:
            return

        if not force and self._buffered_bytes < self._min_flush_bytes:
            return

        combined_audio = b"".join(self._audio_buffer)
        self._audio_buffer.clear()
        buffered_bytes = len(combined_audio)
        self._buffered_bytes = 0
        buffered_seconds = buffered_bytes / (self._sample_rate * 2)
        chunks = self._chunks_since_last_flush or 1
        elapsed = time.time() - self._last_flush_time
        self._chunks_since_last_flush = 0
        self._last_flush_time = time.time()

        logger.info(
            "[Voice Stream][ASR] Flushing %.2fs (%d bytes) collected from %d chunks over %.2fs (reason=%s)",
            buffered_seconds,
            buffered_bytes,
            chunks,
            elapsed,
            reason,
        )

        # 调用ASR服务进行转录
        try:
            transcript = await asr_service.transcribe(
                combined_audio,
                language="zh",
                sample_rate=self._sample_rate,
            )
            if transcript and not transcript.startswith("[沙盒模式]"):
                await self.on_transcript(transcript)
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")


class VoiceStreamHub:
    """
    实时语音流中心，管理多个语音流会话
    """
    
    def __init__(self):
        self.sessions: Dict[str, VoiceStreamSession] = {}
        self.lock = asyncio.Lock()
    
    async def create_session(
        self, 
        websocket: WebSocket, 
        session_id: str, 
        on_transcript: Callable
    ) -> VoiceStreamSession:
        """创建新的语音流会话"""
        async with self.lock:
            if session_id in self.sessions:
                # 关闭现有会话
                await self.sessions[session_id].close()
            
            session = VoiceStreamSession(session_id, websocket, on_transcript)
            self.sessions[session_id] = session
            logger.info(f"Created voice stream session: {session_id}")
            return session
    
    async def remove_session(self, session_id: str) -> None:
        """移除语音流会话"""
        async with self.lock:
            if session_id in self.sessions:
                await self.sessions[session_id].close()
                del self.sessions[session_id]
                logger.info(f"Removed voice stream session: {session_id}")
    
    async def get_session(self, session_id: str) -> Optional[VoiceStreamSession]:
        """获取语音流会话"""
        async with self.lock:
            return self.sessions.get(session_id)


# 创建语音流中心实例
voice_stream_hub = VoiceStreamHub()


# ============================================================================


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

# 加载百度云API凭证
import os
baidu_api_key = os.getenv("BAIDU_API_KEY")
baidu_secret_key = os.getenv("BAIDU_SECRET_KEY")

# 初始化FaceEmotionTool，启用百度云API和DeepFace
face_tool = FaceEmotionTool(
    FaceEmotionConfig(), 
    use_deepface=True,
    use_baidu_api=True,
    baidu_api_key=baidu_api_key,
    baidu_secret_key=baidu_secret_key
)
fusion_service = EmotionFusionService(FusionConfig())
avatar = AvatarOrchestrator(AvatarConfig())
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
# 创建语音情绪工具 - 已移除
# speech_tool = SpeechEmotionTool()

pipeline = EmotionPipeline(
    eeg_stream=eeg_stream,
    eeg_classifier=eeg_classifier,
    face_tool=face_tool,
    # speech_tool=speech_tool,  # 已移除
    fusion=fusion_service,
    avatar=avatar,
    agent=agent,
)
chat_service = ChatService(agent=agent, pipeline=pipeline)
eeg_waveform_service = EEGWaveformService()
# 创建真实EEG处理器
real_eeg_processor = create_eeg_processor()

# 输出服务初始化日志
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



async def get_pipeline() -> EmotionPipeline:
    return pipeline


async def get_memory() -> AgentMemory:
    return memory


async def get_agent() -> ConversationalAgent:
    return agent


async def get_chat_service() -> ChatService:
    return chat_service


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

@app.post("/info", response_model=InfoResponse)
async def handle_info(request: InfoRequest) -> InfoResponse:
    if not request.name:
        raise HTTPException(status_code=400, detail="name is required")

    if request.type == "getInfo":
        stored = await read_info(request.name)
        return InfoResponse(code=200, data=stored)

    if request.type == "writeInfo":
        if request.data is None:
            raise HTTPException(status_code=400, detail="data is required for writeInfo")

        if isinstance(request.data, str):
            serialized = request.data
        else:
            try:
                serialized = json.dumps(request.data, ensure_ascii=True)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail="data must be JSON serializable") from exc

        await write_info(request.name, serialized)
        return InfoResponse(code=200, data=serialized)

    raise HTTPException(status_code=400, detail="Unsupported request type")


@app.post("/info", response_model=InfoResponse)
async def handle_info(request: InfoRequest) -> InfoResponse:
    if not request.name:
        raise HTTPException(status_code=400, detail="name is required")

    if request.type == "getInfo":
        stored = await read_info(request.name)
        return InfoResponse(code=200, data=stored)

    if request.type == "writeInfo":
        if request.data is None:
            raise HTTPException(status_code=400, detail="data is required for writeInfo")

        if isinstance(request.data, str):
            serialized = request.data
        else:
            try:
                serialized = json.dumps(request.data, ensure_ascii=True)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail="data must be JSON serializable") from exc

        await write_info(request.name, serialized)
        return InfoResponse(code=200, data=serialized)

    raise HTTPException(status_code=400, detail="Unsupported request type")


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


@app.delete("/chat/threads/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: str,
    chat: ChatService = Depends(get_chat_service),
) -> Response:
    success = await chat.delete_thread(thread_id)
    if not success:
        raise HTTPException(status_code=404, detail="Thread not found")
    return Response(status_code=204)


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
    message = await chat.add_user_message(thread_id, payload.text, payload.language)
    return message


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


@app.post("/video/emotion")
async def detect_video_emotion(
    frame: UploadFile = File(...),
    room_id: Optional[str] = Form(None),
) -> dict:
    """
    视频情绪检测接口
    
    接收视频帧，使用FaceEmotionTool进行情绪检测，返回检测结果
    
    Args:
        frame: 视频帧图像文件
        room_id: 可选的房间ID，用于将结果发送到特定房间
    
    Returns:
        {
            "emotion": "检测到的情绪",
            "confidence": 置信度,
            "face_position": {"x": x, "y": y, "width": w, "height": h}
        }
    """
    try:
        # 1. 读取视频帧数据
        frame_data = await frame.read()
        logger.info(f"Received video frame: {len(frame_data)} bytes, content_type={frame.content_type}")
        
        # 2. 将帧数据转换为numpy数组
        import numpy as np
        import io
        from PIL import Image
        
        # 将字节数据转换为PIL Image
        image = Image.open(io.BytesIO(frame_data))
        
        # 转换为numpy数组 (RGB格式)
        frame_array = np.array(image)
        logger.info(f"Converted frame to numpy array with shape: {frame_array.shape}")
        
        # 3. 使用FaceEmotionTool进行情绪检测
        logger.info("Calling face_tool.update_frame")
        await face_tool.update_frame(frame_array)
        logger.info("Calling face_tool.analyze")
        emotion_result = await face_tool.analyze()
        logger.info(f"Emotion analysis result: {emotion_result}")
        
        # 4. 获取最新的人脸检测结果
        face_bbox = None
        if hasattr(face_tool, '_latest_observation') and face_tool._latest_observation:
            face_bbox = face_tool._latest_observation.get('face_bbox')
            logger.info(f"Face bbox from _latest_observation: {face_bbox}")
        
        # 如果从_latest_observation获取不到，尝试从metadata获取
        if not face_bbox and hasattr(emotion_result, 'metadata') and emotion_result.metadata:
            face_bbox = emotion_result.metadata.get('face_bbox')
            logger.info(f"Face bbox from metadata: {face_bbox}")
        
        # 5. 构建返回结果
        result = {
            "emotion": emotion_result.label,
            "confidence": emotion_result.confidence,
            "mood_score": emotion_result.mood_score,
            "source": emotion_result.source,
        }
        
        if face_bbox:
            result["face_position"] = [face_bbox]
            logger.info(f"Using face_bbox in result: {face_bbox}")
        else:
            # 如果没有人脸位置信息，生成默认位置
            height, width = frame_array.shape[:2]
            default_bbox = {
                "x": int(width * 0.3),
                "y": int(height * 0.2),
                "width": int(width * 0.4),
                "height": int(height * 0.5)
            }
            result["face_position"] = [default_bbox]
            logger.info(f"Using default face bbox: {default_bbox}")
        
        # 6. 如果有房间ID，通过WebSocket发送结果到前端
        if room_id:
            try:
                # 通过pipeline的WebSocket发送情绪数据
                await pipeline.broadcast_face_emotion(room_id, {
                    "label": emotion_result.label,
                    "confidence": emotion_result.confidence,
                    "face_position": [face_bbox] if face_bbox else None,
                    "timestamp": time.time()
                })
                logger.info(f"Emotion result sent to room {room_id}")
            except Exception as e:
                logger.error(f"Failed to send emotion result to room {room_id}: {e}")
        
        logger.info(f"Final emotion detection result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Video emotion detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"情绪检测失败: {str(e)}")


@app.get("/eeg/waveform/{emotion}")
async def get_emotion_waveform(
    emotion: str,
    duration: float = 5.0,
    sample_rate: int = 250,
) -> dict:
    """
    根据情绪生成对应的脑电波形数据
    
    Args:
        emotion: 情绪类型 (happy, sad, neutral, angry, surprise, fear, disgust)
        duration: 波形持续时间(秒)
        sample_rate: 采样率(Hz)
    
    Returns:
        {
            "emotion": "情绪类型",
            "waveform": {
                "channels": {"signal": [波形数据点]},
                "sample_rate_hz": 采样率
            },
            "timestamp": "时间戳"
        }
    """
    try:
        # 根据情绪类型设置不同的脑电波特征
        emotion_configs = {
            "happy": {
                "alpha": 0.7,    # 快乐时α波增强
                "beta": 0.8,     # β波增强
                "theta": 0.4,
                "gamma": 0.6,    # γ波增强
            },
            "sad": {
                "alpha": 0.3,    # 悲伤时α波减弱
                "beta": 0.4,
                "theta": 0.7,    # θ波增强
                "gamma": 0.2,
            },
            "neutral": {
                "alpha": 0.5,
                "beta": 0.5,
                "theta": 0.5,
                "gamma": 0.5,
            },
            "angry": {
                "alpha": 0.2,    # 愤怒时α波减弱
                "beta": 0.9,     # β波增强
                "theta": 0.3,
                "gamma": 0.8,    # γ波增强
            },
            "surprise": {
                "alpha": 0.4,    # 惊讶时α波中等
                "beta": 0.8,     # β波增强
                "theta": 0.3,
                "gamma": 0.7,    # γ波增强
            },
            "fear": {
                "alpha": 0.3,    # 恐惧时α波减弱
                "beta": 0.7,     # β波增强
                "theta": 0.6,    # θ波增强
                "gamma": 0.5,
            },
            "disgust": {
                "alpha": 0.4,    # 厌恶时α波中等
                "beta": 0.6,
                "theta": 0.5,
                "gamma": 0.4,
            }
        }
        
        # 获取情绪配置，如果不存在则使用中性配置
        config = emotion_configs.get(emotion, emotion_configs["neutral"])
        
        # 生成波形数据
        import numpy as np
        import time
        import math
        import random
        
        # 计算采样点数
        num_samples = int(duration * sample_rate)
        
        # 创建时间轴
        t = np.linspace(0, duration, num_samples)
        
        # 生成不同频段的脑电波
        delta = 0.5 * np.sin(2 * np.pi * 2 * t) * config.get("delta", 0.5)    # 0.5-4Hz
        theta = 0.5 * np.sin(2 * np.pi * 6 * t) * config.get("theta", 0.5)    # 4-8Hz
        alpha = 0.5 * np.sin(2 * np.pi * 10 * t) * config.get("alpha", 0.5)   # 8-13Hz
        beta = 0.5 * np.sin(2 * np.pi * 20 * t) * config.get("beta", 0.5)    # 13-30Hz
        gamma = 0.5 * np.sin(2 * np.pi * 40 * t) * config.get("gamma", 0.5)  # 30-45Hz
        
        # 合成波形
        waveform_data = delta + theta + alpha + beta + gamma
        
        # 添加一些随机噪声
        noise = np.random.normal(0, 0.1, num_samples)
        waveform_data += noise
        
        # 归一化到[-1, 1]范围
        if np.max(np.abs(waveform_data)) > 0:
            waveform_data = waveform_data / np.max(np.abs(waveform_data))
        
        # 转换为Python列表
        waveform_list = waveform_data.tolist()
        
        # 构建返回结果
        result = {
            "emotion": emotion,
            "waveform": {
                "channels": {"signal": waveform_list},
                "sample_rate_hz": sample_rate
            },
            "timestamp": time.time(),
            "duration": duration,
            "band_powers": {
                "delta": config.get("delta", 0.5),
                "theta": config.get("theta", 0.5),
                "alpha": config.get("alpha", 0.5),
                "beta": config.get("beta", 0.5),
                "gamma": config.get("gamma", 0.5)
            }
        }
        
        logger.info(f"Generated EEG waveform for emotion: {emotion}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to generate EEG waveform for emotion {emotion}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成脑电波形失败: {str(e)}")


@app.get("/eeg/face-waveform/{emotion}")
async def get_face_emotion_waveform(
    emotion: str,
    duration: float = 5.0,
    sample_rate: int = 250,
) -> dict:
    """
    根据面部情绪生成对应的脑电波形数据，整合训练数据信息
    
    Args:
        emotion: 面部情绪类型 (happy, sad, neutral, angry, surprise, fear, disgust)
        duration: 波形持续时间(秒)
        sample_rate: 采样率(Hz)
    
    Returns:
        {
            "emotion": "情绪类型",
            "waveform": {
                "channels": {"signal": [波形数据点]},
                "sample_rate_hz": 采样率
            },
            "timestamp": "时间戳",
            "training_data": {
                "info": {
                    "status": "loaded",
                    "data_path": "backend/Training Data",
                    "classes": ["happy", "sad", "neutral", "angry", "surprise", "fear", "disgust"],
                    "feature_dimensions": 128,
                    "model_accuracy": 0.85
                },
                "recent_emotions": [最近的情绪记录]
            }
        }
    """
    try:
        # 使用EEGWaveformService生成波形数据
        result = eeg_waveform_service.get_waveform_from_face_emotion(emotion, duration, sample_rate)
        
        logger.info(f"Generated face-based EEG waveform for emotion: {emotion}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to generate face-based EEG waveform for emotion {emotion}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成面部情绪脑电波形失败: {str(e)}")


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


# 真实脑电数据API端点
@app.post("/eeg/real/connect")
async def connect_real_eeg_device(
    device_type: str = "serial",
    port: str = "COM3",
    baudrate: int = 115200,
    simulate: bool = False
) -> dict:
    """
    连接真实脑电设备
    
    Args:
        device_type: 设备类型 ("serial" 或 "bluetooth")
        port: 端口号 (如 "COM3" 或 "/dev/ttyUSB0")
        baudrate: 波特率 (默认115200)
        simulate: 是否使用模拟设备
    
    Returns:
        {
            "status": "connected" | "error",
            "device_id": "设备ID",
            "message": "连接状态消息"
        }
    """
    try:
        # 如果指定使用模拟设备，则连接模拟设备
        if simulate:
            device_id = await real_eeg_processor.connect_simulated_device()
            return {
                "status": "connected",
                "device_id": device_id,
                "message": f"已连接模拟EEG设备 (ID: {device_id})"
            }
        
        # 连接真实设备
        if device_type == "serial":
            device_id = await real_eeg_processor.connect_serial_device(port, baudrate)
        elif device_type == "bluetooth":
            device_id = await real_eeg_processor.connect_bluetooth_device(port)
        else:
            raise ValueError(f"不支持的设备类型: {device_type}")
        
        return {
            "status": "connected",
            "device_id": device_id,
            "message": f"已连接{device_type} EEG设备 (ID: {device_id})"
        }
        
    except Exception as e:
        logger.error(f"Failed to connect EEG device: {e}", exc_info=True)
        return {
            "status": "error",
            "device_id": None,
            "message": f"连接EEG设备失败: {str(e)}"
        }


@app.post("/eeg/real/disconnect")
async def disconnect_real_eeg_device(
    device_id: str = None
) -> dict:
    """
    断开脑电设备连接
    
    Args:
        device_id: 设备ID，如果为None则断开所有设备
    
    Returns:
        {
            "status": "disconnected" | "error",
            "message": "断开状态消息"
        }
    """
    try:
        if device_id:
            await real_eeg_processor.disconnect_device(device_id)
            message = f"已断开EEG设备 (ID: {device_id})"
        else:
            await real_eeg_processor.disconnect_all()
            message = "已断开所有EEG设备"
        
        return {
            "status": "disconnected",
            "message": message
        }
        
    except Exception as e:
        logger.error(f"Failed to disconnect EEG device: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"断开EEG设备失败: {str(e)}"
        }


@app.get("/eeg/real/status")
async def get_real_eeg_status() -> dict:
    """
    获取真实脑电设备状态
    
    Returns:
        {
            "connected_devices": [
                {
                    "id": "设备ID",
                    "type": "设备类型",
                    "status": "连接状态",
                    "port": "端口号",
                    "data_count": "接收数据点数"
                }
            ],
            "is_streaming": "是否正在流式传输",
            "latest_emotion": "最新情绪分析结果"
        }
    """
    try:
        devices = await real_eeg_processor.get_device_status()
        is_streaming = await real_eeg_processor.is_streaming()
        latest_emotion = await real_eeg_processor.get_latest_emotion()
        
        return {
            "connected_devices": devices,
            "is_streaming": is_streaming,
            "latest_emotion": latest_emotion
        }
        
    except Exception as e:
        logger.error(f"Failed to get EEG status: {e}", exc_info=True)
        return {
            "connected_devices": [],
            "is_streaming": False,
            "latest_emotion": None,
            "error": str(e)
        }


@app.post("/eeg/real/start")
async def start_real_eeg_stream(
    device_id: str = None,
    buffer_size: int = 1000
) -> dict:
    """
    开始从真实脑电设备接收数据流
    
    Args:
        device_id: 设备ID，如果为None则使用第一个可用设备
        buffer_size: 数据缓冲区大小
    
    Returns:
        {
            "status": "streaming" | "error",
            "device_id": "使用的设备ID",
            "sample_rate": "采样率",
            "channels": "通道数",
            "message": "状态消息"
        }
    """
    try:
        if not device_id:
            # 获取第一个可用设备
            devices = await real_eeg_processor.get_device_status()
            if not devices:
                raise ValueError("没有可用的EEG设备")
            device_id = devices[0]["id"]
        
        await real_eeg_processor.start_streaming(device_id, buffer_size)
        
        return {
            "status": "streaming",
            "device_id": device_id,
            "sample_rate": 250,  # 默认采样率
            "channels": 8,       # 默认通道数
            "message": f"已开始从设备 {device_id} 接收EEG数据流"
        }
        
    except Exception as e:
        logger.error(f"Failed to start EEG stream: {e}", exc_info=True)
        return {
            "status": "error",
            "device_id": device_id,
            "sample_rate": None,
            "channels": None,
            "message": f"开始EEG数据流失败: {str(e)}"
        }


@app.post("/eeg/real/stop")
async def stop_real_eeg_stream(
    device_id: str = None
) -> dict:
    """
    停止从真实脑电设备接收数据流
    
    Args:
        device_id: 设备ID，如果为None则停止所有设备的数据流
    
    Returns:
        {
            "status": "stopped" | "error",
            "message": "状态消息"
        }
    """
    try:
        if device_id:
            await real_eeg_processor.stop_streaming(device_id)
            message = f"已停止设备 {device_id} 的EEG数据流"
        else:
            await real_eeg_processor.stop_all_streaming()
            message = "已停止所有设备的EEG数据流"
        
        return {
            "status": "stopped",
            "message": message
        }
        
    except Exception as e:
        logger.error(f"Failed to stop EEG stream: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"停止EEG数据流失败: {str(e)}"
        }


@app.get("/eeg/real/data")
async def get_real_eeg_data(
    device_id: str = None,
    num_samples: int = 250
) -> dict:
    """
    获取真实脑电数据
    
    Args:
        device_id: 设备ID，如果为None则使用第一个可用设备
        num_samples: 获取的数据点数
    
    Returns:
        {
            "device_id": "设备ID",
            "timestamp": "时间戳",
            "sample_rate": "采样率",
            "channels": ["通道名称列表"],
            "data": {
                "channel_1": [数据点],
                "channel_2": [数据点],
                ...
            },
            "emotion": {
                "label": "情绪标签",
                "confidence": "置信度",
                "arousal": "唤醒度",
                "valence": "效价"
            }
        }
    """
    try:
        if not device_id:
            # 获取第一个可用设备
            devices = await real_eeg_processor.get_device_status()
            if not devices:
                raise ValueError("没有可用的EEG设备")
            device_id = devices[0]["id"]
        
        # 获取数据
        data = await real_eeg_processor.get_latest_data(device_id, num_samples)
        
        # 分析情绪
        emotion = await real_eeg_processor.analyze_emotion(device_id)
        
        return {
            "device_id": device_id,
            "timestamp": time.time(),
            "sample_rate": 250,  # 默认采样率
            "channels": list(data.keys()) if data else [],
            "data": data,
            "emotion": emotion
        }
        
    except Exception as e:
        logger.error(f"Failed to get EEG data: {e}", exc_info=True)
        return {
            "device_id": device_id,
            "timestamp": time.time(),
            "sample_rate": None,
            "channels": [],
            "data": {},
            "emotion": None,
            "error": str(e)
        }


@app.websocket("/eeg/real/stream/{room_id}")
async def websocket_real_eeg_stream(
    websocket: WebSocket,
    room_id: str
):
    """
    WebSocket端点，用于实时传输真实脑电数据和情绪分析结果
    
    Args:
        websocket: WebSocket连接
        room_id: 房间ID，用于将数据发送到特定房间
    """
    await websocket.accept()
    logger.info(f"WebSocket connection established for real EEG stream in room {room_id}")
    
    try:
        # 检查是否有设备连接
        devices = await real_eeg_processor.get_device_status()
        if not devices:
            await websocket.send_json({
                "type": "error",
                "message": "没有可用的EEG设备"
            })
            await websocket.close()
            return
        
        # 使用第一个可用设备
        device_id = devices[0]["id"]
        
        # 如果设备未开始流式传输，则启动它
        is_streaming = await real_eeg_processor.is_streaming(device_id)
        if not is_streaming:
            await real_eeg_processor.start_streaming(device_id)
        
        # 持续发送数据
        while True:
            try:
                # 获取最新数据
                data = await real_eeg_processor.get_latest_data(device_id, 100)
                
                # 分析情绪
                emotion = await real_eeg_processor.analyze_emotion(device_id)
                
                # 发送数据
                await websocket.send_json({
                    "type": "eeg_data",
                    "device_id": device_id,
                    "timestamp": time.time(),
                    "data": data,
                    "emotion": emotion
                })
                
                # 等待一段时间再发送下一批数据
                await asyncio.sleep(0.1)  # 10Hz更新率
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for room {room_id}")
                break
            except Exception as e:
                logger.error(f"Error sending EEG data: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "error",
                    "message": f"发送EEG数据时出错: {str(e)}"
                })
                break
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for room {room_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "message": f"WebSocket错误: {str(e)}"
        })
    finally:
        # 确保WebSocket连接关闭
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()


# ============================================================================
# 实时语音流WebSocket端点
# ============================================================================

@app.websocket("/ws/voice-stream")
async def voice_stream_websocket(
    websocket: WebSocket,
    session_id: str = None,
):
    """
    实时语音流WebSocket端点，实现智能断句和流式TTS
    
    Args:
        websocket: WebSocket连接
        session_id: 会话ID，如果不提供则自动生成
    """
    # 生成会话ID（如果未提供）
    if not session_id:
        session_id = uuid.uuid4().hex
    
    session: VoiceStreamSession | None = None

    try:
        await websocket.accept()
        logger.info(f"Voice stream WebSocket connected: {session_id}")
        
        # 定义转录回调函数
        async def on_transcript(transcript: str):
            """处理转录文本，生成响应并合成语音"""
            try:
                logger.info(f"[Voice Stream] Received transcript: {transcript}")
                
                # 发送转录文本到客户端
                await session.send_message("transcript", {"text": transcript})
                
                # 构建对话消息
                messages = [
                    {"role": "system", "content": "你是一个友好、有帮助的AI助手。请用简洁、自然的语言回答用户的问题。"},
                    {"role": "user", "content": transcript}
                ]
                
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
                            
                            # 下载音频数据
                            audio_data = await fetch_audio_from_url(audio_url)
                            if audio_data:
                                # 添加到音频队列
                                await session.audio_queue_hook.add_audio(
                                    audio_data=audio_data,
                                    segment_id=seg_id,
                                    text=sentence
                                )
                                
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
        
        # 启动后台任务
        await session.start_background_tasks()
        
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
                    await session.flush_pending_audio("stop-signal")
                    # 中断当前播放
                    await session.audio_queue_hook.interrupt()
                    break
                elif data.get("type") == "interrupt":
                    logger.info("Received interrupt signal")
                    # 中断当前播放
                    await session.audio_queue_hook.interrupt()
                elif data.get("type") == "status":
                    # 发送状态信息
                    status = await session.audio_queue_hook.get_status()
                    await session.send_message("queue_status", status)
                    
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
        if session:
            try:
                await session.flush_pending_audio("connection-closed")
            except Exception as flush_error:
                logger.warning("Failed to flush audio on shutdown: %s", flush_error)
        if session_id:
            await voice_stream_hub.remove_session(session_id)
        try:
            await websocket.close()
        except:
            pass


