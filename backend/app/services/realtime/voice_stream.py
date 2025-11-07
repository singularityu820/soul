"""
实时语音流处理服务

使用 WebSocket 实现低延迟的语音对话:
- 接收实时音频流
- 流式 ASR 转录
- 流式 LLM 生成
- 流式 TTS 合成
"""

from __future__ import annotations

import asyncio
import logging
import json
from typing import Optional, Callable, Awaitable
from collections import deque

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class VoiceStreamSession:
    """
    实时语音流会话
    
    处理流程:
    1. 接收音频块 → 缓冲
    2. 检测语音活动 (VAD)
    3. 当检测到完整语句 → ASR
    4. ASR 结果 → LLM
    5. LLM 响应 → TTS
    6. TTS 音频 → 发送给客户端
    """
    
    def __init__(
        self,
        websocket: WebSocket,
        session_id: str,
        on_transcript: Optional[Callable[[str], Awaitable[str]]] = None,
        on_audio_chunk: Optional[Callable[[bytes], Awaitable[None]]] = None,
    ):
        self.websocket = websocket
        self.session_id = session_id
        self._on_transcript = on_transcript
        self._on_audio_chunk = on_audio_chunk
        
        # 音频缓冲
        self._audio_buffer = bytearray()
        self._buffer_lock = asyncio.Lock()
        
        # 语音活动检测
        self._is_speaking = False
        self._silence_counter = 0
        self._silence_threshold = 30  # 约 1 秒静音 (30 * 32ms)
        
        # 处理任务
        self._processing = False
        self._closed = False
        
        logger.info(f"Voice stream session created: {session_id}")
    
    async def handle_audio_data(self, audio_data: bytes) -> None:
        """
        处理接收的音频数据
        
        Args:
            audio_data: 原始音频数据 (PCM 16bit 16kHz mono)
        """
        if self._closed:
            return
        
        async with self._buffer_lock:
            self._audio_buffer.extend(audio_data)
        
        # 简单的能量检测 VAD
        is_voice = self._detect_voice_activity(audio_data)
        
        if is_voice:
            self._is_speaking = True
            self._silence_counter = 0
        else:
            self._silence_counter += 1
        
        # 检测到完整语句 (说话结束 + 1秒静音)
        if self._is_speaking and self._silence_counter >= self._silence_threshold:
            await self._process_audio_buffer()
            self._is_speaking = False
            self._silence_counter = 0
    
    def _detect_voice_activity(self, audio_data: bytes) -> bool:
        """
        简单的语音活动检测 (能量阈值法)
        
        Args:
            audio_data: 音频数据
            
        Returns:
            是否检测到语音
        """
        if len(audio_data) < 2:
            return False
        
        # 计算平均能量
        samples = []
        for i in range(0, len(audio_data) - 1, 2):
            sample = int.from_bytes(audio_data[i:i+2], byteorder='little', signed=True)
            samples.append(abs(sample))
        
        avg_energy = sum(samples) / len(samples) if samples else 0
        
        # 阈值可以根据实际情况调整
        energy_threshold = 500
        return avg_energy > energy_threshold
    
    async def _process_audio_buffer(self) -> None:
        """
        处理缓冲的音频数据
        
        工作流程:
        1. 从缓冲区获取音频
        2. ASR 转录
        3. LLM 生成响应
        4. TTS 合成
        5. 发送音频响应
        """
        if self._processing or self._closed:
            return
        
        self._processing = True
        
        try:
            async with self._buffer_lock:
                if len(self._audio_buffer) < 16000:  # 少于 1 秒的音频,忽略
                    self._audio_buffer.clear()
                    self._processing = False
                    return
                
                audio_data = bytes(self._audio_buffer)
                self._audio_buffer.clear()
            
            logger.info(f"Processing audio buffer: {len(audio_data)} bytes")
            
            # 发送状态: 正在转录
            await self.send_status("transcribing")
            
            # 这里会在外部注入实际的处理逻辑
            if self._on_transcript:
                # 回调会处理 ASR → LLM → TTS 流程
                response_text = await self._on_transcript(audio_data)
                logger.info(f"Generated response: {response_text[:100]}...")
            
        except Exception as e:
            logger.error(f"Error processing audio buffer: {e}", exc_info=True)
            await self.send_error(str(e))
        finally:
            self._processing = False
    
    async def send_message(self, message_type: str, data: dict) -> None:
        """发送消息给客户端"""
        if self._closed:
            return
        
        try:
            await self.websocket.send_json({
                "type": message_type,
                "session_id": self.session_id,
                **data
            })
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    async def send_transcript(self, text: str, is_final: bool = True) -> None:
        """发送转录结果"""
        await self.send_message("transcript", {
            "text": text,
            "is_final": is_final
        })
    
    async def send_response(self, text: str) -> None:
        """发送 LLM 响应文本"""
        await self.send_message("response", {"text": text})
    
    async def send_audio(self, audio_data: bytes) -> None:
        """发送音频数据"""
        try:
            await self.websocket.send_bytes(audio_data)
        except Exception as e:
            logger.error(f"Error sending audio: {e}")
    
    async def send_status(self, status: str) -> None:
        """发送状态更新"""
        await self.send_message("status", {"status": status})
    
    async def send_error(self, error: str) -> None:
        """发送错误信息"""
        await self.send_message("error", {"message": error})
    
    async def close(self) -> None:
        """关闭会话"""
        if self._closed:
            return
        
        self._closed = True
        logger.info(f"Voice stream session closed: {self.session_id}")
        
        # 清理缓冲
        async with self._buffer_lock:
            self._audio_buffer.clear()


class VoiceStreamHub:
    """
    语音流会话管理中心
    """
    
    def __init__(self):
        self._sessions: dict[str, VoiceStreamSession] = {}
        self._session_lock = asyncio.Lock()
    
    async def create_session(
        self,
        websocket: WebSocket,
        session_id: str,
        on_transcript: Optional[Callable[[str], Awaitable[str]]] = None,
    ) -> VoiceStreamSession:
        """创建新会话"""
        async with self._session_lock:
            if session_id in self._sessions:
                await self._sessions[session_id].close()
            
            session = VoiceStreamSession(
                websocket=websocket,
                session_id=session_id,
                on_transcript=on_transcript,
            )
            self._sessions[session_id] = session
            
            logger.info(f"Created voice stream session: {session_id}")
            return session
    
    async def remove_session(self, session_id: str) -> None:
        """移除会话"""
        async with self._session_lock:
            if session_id in self._sessions:
                await self._sessions[session_id].close()
                del self._sessions[session_id]
                logger.info(f"Removed voice stream session: {session_id}")
    
    def get_session(self, session_id: str) -> Optional[VoiceStreamSession]:
        """获取会话"""
        return self._sessions.get(session_id)
    
    async def close_all(self) -> None:
        """关闭所有会话"""
        async with self._session_lock:
            for session in self._sessions.values():
                await session.close()
            self._sessions.clear()
            logger.info("All voice stream sessions closed")
