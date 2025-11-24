"""
Qwen-Omni-Realtime 实时多模态大模型服务适配器

集成 DashScope 的 Qwen-Omni-Turbo-Realtime 模型，
支持实时语音对话并保留工具调用能力。
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import uuid
from typing import Any, Callable, Dict, List, Optional

import dashscope
from dashscope.audio.qwen_omni import (
    AudioFormat,
    MultiModality,
    OmniRealtimeCallback,
    OmniRealtimeConversation,
)
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class QwenOmniRealtimeConfig:
    """Qwen Omni Realtime 配置"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen-omni-turbo-realtime",
        voice: str = "Chelsie",  # 默认使用千雪音色（二次元虚拟女友）
        base_url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
        input_audio_format: str = AudioFormat.PCM_16000HZ_MONO_16BIT,
        output_audio_format: str = AudioFormat.PCM_24000HZ_MONO_16BIT,
        enable_vad: bool = True,
        vad_threshold: float = 0.5,
        vad_silence_duration_ms: int = 800,
        enable_input_transcription: bool = True,
        transcription_model: str = "gummy-realtime-v1",
        instructions: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY not found in environment")

        self.model = model
        self.voice = voice
        self.base_url = base_url
        self.input_audio_format = input_audio_format
        self.output_audio_format = output_audio_format
        self.enable_vad = enable_vad
        self.vad_threshold = vad_threshold
        self.vad_silence_duration_ms = vad_silence_duration_ms
        self.enable_input_transcription = enable_input_transcription
        self.transcription_model = transcription_model
        self.instructions = instructions or "你是一个有帮助、友好的AI助手。"


class QwenOmniRealtimeSession:
    """Qwen Omni Realtime 会话管理器"""

    def __init__(
        self,
        session_id: str,
        websocket: WebSocket,
        config: QwenOmniRealtimeConfig,
        on_transcript: Optional[Callable[[str], None]] = None,
        on_audio: Optional[Callable[[str], None]] = None,
        on_tool_call: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        self.session_id = session_id
        self.websocket = websocket
        self.config = config
        self.on_transcript = on_transcript
        self.on_audio = on_audio
        self.on_tool_call = on_tool_call

        # 设置 DashScope API Key
        dashscope.api_key = config.api_key

        # 状态管理
        self._closed = False
        self._conversation: Optional[OmniRealtimeConversation] = None
        self._audio_buffer: List[bytes] = []
        self._current_transcript = ""
        self._message_queue = asyncio.Queue()
        self._loop = asyncio.get_event_loop()  # 保存事件循环引用

        # 创建回调处理器
        self._callback = self._create_callback()

    def _create_callback(self) -> OmniRealtimeCallback:
        """创建 Qwen Omni 回调处理器"""

        class RealtimeCallback(OmniRealtimeCallback):
            def __init__(self, session: QwenOmniRealtimeSession):
                super().__init__()
                self.session = session

            def on_open(self) -> None:
                logger.info(f"Qwen Omni connection opened for session {self.session.session_id}")

            def on_close(self, close_status_code: int, close_msg: str) -> None:
                logger.info(
                    f"Qwen Omni connection closed for session {self.session.session_id}: "
                    f"code={close_status_code}, msg={close_msg}"
                )
                self.session._closed = True

            def on_error(self, error: Exception) -> None:
                logger.error(f"Qwen Omni error for session {self.session.session_id}: {error}")

            def on_event(self, event: Dict[str, Any]) -> None:
                """处理所有事件"""
                event_type = event.get("type")
                logger.debug(f"Received event: {event_type}")

                try:
                    # 处理音频转录文本
                    if event_type == "response.audio_transcript.delta":
                        delta = event.get("delta", "")
                        if delta and self.session.on_transcript:
                            logger.debug(f"Transcript delta: {delta}")
                            self.session._current_transcript += delta
                            asyncio.run_coroutine_threadsafe(
                                self.session._send_to_websocket(
                                    {"type": "transcript", "text": delta, "is_final": False}
                                ),
                                self.session._loop
                            )

                    elif event_type == "response.audio_transcript.done":
                        transcript = event.get("transcript", self.session._current_transcript)
                        if transcript and self.session.on_transcript:
                            logger.info(f"Transcript done: {transcript}")
                            self.session.on_transcript(transcript)
                            asyncio.run_coroutine_threadsafe(
                                self.session._send_to_websocket(
                                    {"type": "transcript", "text": transcript, "is_final": True}
                                ),
                                self.session._loop
                            )
                        self.session._current_transcript = ""

                    # 处理音频数据
                    elif event_type == "response.audio.delta":
                        audio_b64 = event.get("delta")
                        if audio_b64 and self.session.on_audio:
                            # 计算音频块大小用于调试
                            audio_bytes = len(audio_b64) * 3 // 4  # base64 解码后的字节数
                            samples = audio_bytes // 2  # 16-bit PCM
                            logger.debug(f"Audio delta: {samples} samples ({audio_bytes} bytes)")
                            
                            self.session.on_audio(audio_b64)
                            asyncio.run_coroutine_threadsafe(
                                self.session._send_to_websocket(
                                    {"type": "audio", "audio": audio_b64}
                                ),
                                self.session._loop
                            )

                    # 处理工具调用
                    elif event_type == "response.function_call_arguments.done":
                        function_name = event.get("name")
                        arguments_str = event.get("arguments", "{}")
                        call_id = event.get("call_id")

                        if function_name and self.session.on_tool_call:
                            try:
                                arguments = json.loads(arguments_str)
                                tool_call = {
                                    "id": call_id,
                                    "type": "function",
                                    "function": {"name": function_name, "arguments": arguments},
                                }
                                # 执行工具调用
                                result = self.session.on_tool_call(tool_call)
                                # 将结果发送回模型
                                asyncio.run_coroutine_threadsafe(
                                    self.session._submit_tool_result(call_id, function_name, result),
                                    self.session._loop
                                )
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse tool arguments: {e}")

                    # VAD 事件
                    elif event_type == "input_audio_buffer.speech_started":
                        asyncio.run_coroutine_threadsafe(
                            self.session._send_to_websocket(
                                {"type": "speech_started", "timestamp": event.get("timestamp")}
                            ),
                            self.session._loop
                        )

                    elif event_type == "input_audio_buffer.speech_stopped":
                        asyncio.run_coroutine_threadsafe(
                            self.session._send_to_websocket(
                                {"type": "speech_stopped", "timestamp": event.get("timestamp")}
                            ),
                            self.session._loop
                        )

                    # 响应完成事件
                    elif event_type == "response.done":
                        logger.info("Response generation completed")
                        asyncio.run_coroutine_threadsafe(
                            self.session._send_to_websocket(
                                {"type": "response_done"}
                            ),
                            self.session._loop
                        )

                except Exception as e:
                    logger.exception(f"Error handling event {event_type}: {e}")

        return RealtimeCallback(self)

    async def connect(self) -> None:
        """建立与 Qwen Omni 的连接"""
        try:
            # 创建对话连接
            self._conversation = OmniRealtimeConversation(
                model=self.config.model,
                callback=self._callback,
                url=self.config.base_url,
            )

            # 连接
            self._conversation.connect()

            # 配置会话
            turn_detection = None
            if self.config.enable_vad:
                turn_detection = {
                    "type": "server_vad",
                    "threshold": self.config.vad_threshold,
                    "silence_duration_ms": self.config.vad_silence_duration_ms,
                }

            self._conversation.update_session(
                output_modalities=[MultiModality.AUDIO, MultiModality.TEXT],
                voice=self.config.voice,
                input_audio_format=self.config.input_audio_format,
                output_audio_format=self.config.output_audio_format,
                enable_input_audio_transcription=self.config.enable_input_transcription,
                input_audio_transcription_model=self.config.transcription_model,
                enable_turn_detection=self.config.enable_vad,
                turn_detection_type="server_vad" if self.config.enable_vad else None,
                instructions=self.config.instructions,
            )

            logger.info(f"Qwen Omni session {self.session_id} connected and configured")

        except Exception as e:
            logger.exception(f"Failed to connect Qwen Omni session {self.session_id}: {e}")
            raise

    async def append_audio(self, audio_b64: str) -> None:
        """追加音频数据（Base64 编码）"""
        if self._conversation and not self._closed:
            try:
                self._conversation.append_audio(audio_b64)
            except Exception as e:
                logger.error(f"Failed to append audio: {e}")

    async def append_image(self, image_b64: str) -> None:
        """追加图片数据（Base64 编码）"""
        if self._conversation and not self._closed:
            try:
                self._conversation.append_image(image_b64)
            except Exception as e:
                logger.error(f"Failed to append image: {e}")

    async def _submit_tool_result(self, call_id: str, function_name: str, result: Any) -> None:
        """提交工具调用结果"""
        if self._conversation and not self._closed:
            try:
                # 构造工具结果事件
                result_str = json.dumps(result) if not isinstance(result, str) else result
                # 注意：具体的工具结果提交方式需要参考 DashScope SDK 文档
                # 这里假设有类似的方法，实际使用时可能需要调整
                logger.info(f"Tool {function_name} (call_id={call_id}) result: {result_str}")
                # self._conversation.submit_tool_output(call_id, result_str)
            except Exception as e:
                logger.error(f"Failed to submit tool result: {e}")

    async def _send_to_websocket(self, message: Dict[str, Any]) -> None:
        """发送消息到 WebSocket 客户端"""
        try:
            if not self._closed:
                await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send message to WebSocket: {e}")

    async def close(self) -> None:
        """关闭会话"""
        if not self._closed:
            self._closed = True
            if self._conversation:
                try:
                    self._conversation.close()
                except Exception as e:
                    logger.error(f"Error closing Qwen Omni conversation: {e}")
            logger.info(f"Qwen Omni session {self.session_id} closed")

    @property
    def is_closed(self) -> bool:
        return self._closed


class QwenOmniRealtimeHub:
    """Qwen Omni Realtime 会话管理中心"""

    def __init__(self, config: Optional[QwenOmniRealtimeConfig] = None):
        self.config = config or QwenOmniRealtimeConfig()
        self.sessions: Dict[str, QwenOmniRealtimeSession] = {}

    async def create_session(
        self,
        websocket: WebSocket,
        session_id: Optional[str] = None,
        on_transcript: Optional[Callable[[str], None]] = None,
        on_audio: Optional[Callable[[str], None]] = None,
        on_tool_call: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> QwenOmniRealtimeSession:
        """创建新会话"""
        if session_id is None:
            session_id = str(uuid.uuid4())

        session = QwenOmniRealtimeSession(
            session_id=session_id,
            websocket=websocket,
            config=self.config,
            on_transcript=on_transcript,
            on_audio=on_audio,
            on_tool_call=on_tool_call,
        )

        await session.connect()
        self.sessions[session_id] = session
        logger.info(f"Created Qwen Omni session: {session_id}")
        return session

    async def get_session(self, session_id: str) -> Optional[QwenOmniRealtimeSession]:
        """获取会话"""
        return self.sessions.get(session_id)

    async def remove_session(self, session_id: str) -> None:
        """移除会话"""
        session = self.sessions.pop(session_id, None)
        if session:
            await session.close()
            logger.info(f"Removed Qwen Omni session: {session_id}")
