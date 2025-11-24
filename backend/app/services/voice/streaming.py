"""Voice streaming services for real-time audio processing."""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


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
        """中断当前播放"""
        async with self.lock:
            self.interrupted = True
            logger.info("Audio playback interrupted")
    
    async def clear_queue(self) -> None:
        """清空队列"""
        async with self.lock:
            self.queue.clear()
            self.interrupted = True
            logger.info("Audio queue cleared")
    
    async def get_next(self) -> Optional[Dict[str, Any]]:
        """获取下一个音频片段"""
        async with self.lock:
            if self.interrupted:
                self.queue.clear()
                self.interrupted = False
                return None
                
            if self.queue:
                return self.queue.pop(0)
            return None
    
    async def get_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        async with self.lock:
            return {
                "queue_size": len(self.queue),
                "is_playing": self.is_playing,
                "current_segment_id": self.current.get("segment_id") if self.current else None,
                "interrupted": self.interrupted
            }


class VoiceStreamSession:
    """实时语音流会话"""
    
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
            # Import here to avoid circular dependency
            from ...dependencies import get_asr_service
            asr_service = get_asr_service()
            
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
    """实时语音流中心，管理多个语音流会话"""
    
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
