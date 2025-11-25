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
        self.instructions = instructions or (
                        """
你是一个实时语音助手，始终以温和、简洁、自然的口语风格与用户对话。对话场景是实时语音通话：优先低延迟、短句、清晰的回复。你可以并且应在需要时调用后端提供的工具（memory 与 agent 功能）来记忆、检索或生成更有上下文的回复。请遵循下面规则：

1) 可用工具（函数）概览 — 何时用：
- memory.add_dialogue(speaker, utterance)
    - 用途：保存一次对话轮次（例如用户或助手的短句），用于后续对话上下文。
    - 参数示例：{"speaker":"user","utterance":"我喜欢猫"}

- memory.add_event(text, tags=None, metadata=None)
    - 用途：保存事实/事件/偏好/感知（非逐句对话），例如“用户喜欢晚睡、喜欢爵士乐”。
    - 参数示例：{"text":"用户喜欢爵士乐","tags":["preference","music"],"metadata":{"source":"call_2025-11-25"}}

- memory.search(query, limit=5)
    - 用途：在生成回复前检索相关记忆以补充上下文（例如回忆用户偏好或最近提到的主题）。
    - 参数示例：{"query":"最近用户提到的旅行计划","limit":5}

- memory.snapshot()
    - 用途：获取记忆摘要或当前记忆快照以便快速参考。

- agent.respond(user_text)
    - 用途：请求 agent 基于记忆与情绪上下文生成带有多模态/策略性的回复（例如需要较长的、带同理心的段落或 TTS 参考）。
    - 参数示例：{"user_text":"我最近压力很大，怎么办？"}

2) 何时调用工具（简明判断）
- 需要把信息长期记住（爱好、常用昵称、重要事实） → 调用 memory.add_event。
- 每次对话轮次需要保存为历史（便于 later retrieval 或统计） → 调用 memory.add_dialogue（在用户说完或在你生成回复后记录）。
- 在回答涉及过去历史、偏好或长期信息时 → 先调用 memory.search(query) 以获取相关记忆，然后基于检索结果生成回答。
- 当需要 agent 的更复杂生成（例如个性化长回答、需要 TTS 选择、或触发策略性跟进） → 调用 agent.respond(user_text) 并使用返回的文本/音频引用直接作为对用户的回复或播放资源。

3) 调用格式（示例 JSON，工具调用后后端会执行并把结果回填）
- 请在需要时以“函数调用”的形式停止普通回复并发出工具请求，格式示例（注意：真实 SDK 会以 function_call/工具调用机制传递，这里给出语义示例）：
    {"type": "tool_call","function": {"name": "memory.add_event","arguments": {"text": "用户喜欢爵士乐","tags": ["preference","music"],"metadata": {"source":"realtime_call"}}}}
- 或：
    {"type": "tool_call","function": {"name": "memory.search","arguments": {"query":"用户的旅行计划", "limit":5}}}
- 或请求 agent 生成回复：
    {"type": "tool_call","function": {"name": "agent.respond","arguments": {"user_text":"我今天心情很差"}}}

4) 工具调用后的行为
- 你应在工具返回结果后继续生成对用户的自然语言语音回复，利用工具返回的数据（例如记忆检索结果、agent 生成文本、或确认 id）来丰富回答。
- 避免把内部 JSON 或工具实现细节直接说给用户；向用户只输出自然语言或播放/引用的语音资源（如有 audio_reference）。

5) 其它准则（风格与安全）
- 及时确认与澄清：若用户提供含糊信息，先用简短问题澄清，再记录或检索记忆。
- 优先同理、简洁、以语音友好的短句为主。对于特别情绪化的用户，给予同理并建议可执行的情绪调节步骤（例如深呼吸）。
- 减少不必要的工具调用：只有在确实需要检索/保存上下文或生成复杂回复时才调用。
- 若工具调用失败或超时，优先给出安全的 fallback 回复，并告知用户（简短一句）。

示例 1（记忆新事实）：
用户说： “顺便告诉你，我下个月要去日本出差。”
步骤：
- 调用 memory.add_event 保存事实：{"text":"用户下个月去日本出差","tags":["event","travel"],"metadata":{...}}
- 向用户确认并继续对话： “知道了！我已记下你下个月要去日本出差，需要我帮你在出发前提醒或准备旅行清单吗？”

示例 2（检索并回答）：
用户问： “你还记得我之前说过喜欢什么音乐吗？”
步骤：
- 调用 memory.search query="用户 音乐 偏好" limit=5
- 依据返回结果生成语音回复： “记得的，你之前提到喜欢爵士乐和电子氛围音乐，想听点推荐吗？”

在实时语音通话中，把工具视为“你可信赖的记忆与助手扩展”，当它能改善体验时就调用，但不要频繁打断用户的语流。始终在调用后用自然、友好的语音回复结束动作。
"""
                )


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
        on_response: Optional[Callable[[str], None]] = None,
    ):
        self.session_id = session_id
        self.websocket = websocket
        self.config = config
        self.on_transcript = on_transcript
        self.on_audio = on_audio
        self.on_tool_call = on_tool_call
        # 回调：当模型生成最终回复文本时调用（可用于持久化助手消息）
        self.on_response = on_response

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
                    # 辅助：从复杂或嵌套事件中提取所有字符串叶子节点并拼接
                    def _extract_text(obj: Any) -> str:
                        if obj is None:
                            return ""
                        if isinstance(obj, str):
                            return obj
                        if isinstance(obj, (int, float, bool)):
                            return str(obj)
                        if isinstance(obj, dict):
                            parts = []
                            for k, v in obj.items():
                                parts.append(_extract_text(v))
                            return "".join([p for p in parts if p])
                        if isinstance(obj, (list, tuple)):
                            parts = []
                            for item in obj:
                                parts.append(_extract_text(item))
                            return "".join([p for p in parts if p])
                        try:
                            return str(obj)
                        except Exception:
                            return ""

                    # 处理音频转录文本（兼容多种事件命名）
                    if event_type == "response.audio_transcript.delta":
                        delta = event.get("delta", "")
                        if delta:
                            logger.debug(f"Model transcript delta: {delta}")
                            self.session._current_transcript += delta
                            # 转发为 model_transcript（表示这是模型自己对音频的转录/生成片段）
                            asyncio.run_coroutine_threadsafe(
                                self.session._send_to_websocket(
                                    {"type": "model_transcript", "text": delta, "is_final": False}
                                ),
                                self.session._loop
                            )

                    elif event_type == "response.audio_transcript.done":
                        transcript = event.get("transcript", self.session._current_transcript)
                        if transcript:
                            logger.info(f"Model transcript done: {transcript}")
                            # 将模型端的转录视为模型输出，发送为 model_transcript
                            asyncio.run_coroutine_threadsafe(
                                self.session._send_to_websocket(
                                    {"type": "model_transcript", "text": transcript, "is_final": True}
                                ),
                                self.session._loop
                            )
                        # 如果注册了 on_transcript 回调，也把该转录交给上层处理（例如保存为实时记录）
                        try:
                            if self.session.on_transcript:
                                try:
                                    self.session._loop.call_soon_threadsafe(self.session.on_transcript, transcript)
                                except Exception as _e:
                                    logger.exception(f"Failed to schedule on_transcript callback: {_e}")
                        except Exception:
                            pass
                        self.session._current_transcript = ""

                    # 处理独立的输入音频转录事件（有些 SDK/模型会使用不同的事件名）
                    elif "input_audio_transcription" in (event_type or "") or "input_audio_transcript" in (event_type or ""):
                        # 尝试从事件中提取转录文本字段（兼容 transcript/text/result 等）
                        transcript = (
                            event.get("transcript")
                            or event.get("text")
                            or event.get("result")
                            or event.get("payload", {}).get("transcript")
                            or ""
                        )
                        if transcript:
                            logger.info(f"Input audio transcription event ({event_type}): {transcript}")
                            # 将转录作为专用事件发送给前端，前端可据此把它显示为“你：”
                            asyncio.run_coroutine_threadsafe(
                                self.session._send_to_websocket(
                                    {
                                        "type": "input_audio_transcription.completed",
                                        "text": transcript,
                                        "is_final": True,
                                        "source_event": event_type,
                                    }
                                ),
                                self.session._loop,
                            )
                            # 同时调用 session.on_transcript 回调，以便上层（如 websockets.py）持久化该转录
                            try:
                                if self.session.on_transcript:
                                    try:
                                        self.session._loop.call_soon_threadsafe(self.session.on_transcript, transcript)
                                    except Exception as _e:
                                        logger.exception(f"Failed to schedule on_transcript callback: {_e}")
                            except Exception:
                                pass

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

                    # 处理文本响应（流式 delta 或最终文本） - 兼容多种命名
                    elif event_type.startswith("response.") and not event_type.startswith("response.audio"):
                        # 忽略已处理的 transcript / function_call / done 事件
                        if event_type in ("response.audio_transcript.delta", "response.audio_transcript.done"):
                            # 已由上面的转录分支处理
                            pass
                        else:
                            # 尝试从事件中提取文本片段或完整文本（递归抽取字符串叶子）
                            raw_delta = event.get("delta") or event.get("text") or event.get("content") or event.get("message")
                            text_delta = _extract_text(raw_delta)
                            # 某些事件会把最终文本放在 "final"/"transcript"/"result" 字段
                            raw_final = event.get("final") or event.get("transcript") or event.get("result") or None
                            text_final = _extract_text(raw_final) if raw_final is not None else None

                            if text_delta:
                                # 流式片段，确保为字符串
                                logger.debug(f"Response text chunk extracted: {text_delta}")
                                asyncio.run_coroutine_threadsafe(
                                    self.session._send_to_websocket({"type": "response_chunk", "text": text_delta}),
                                    self.session._loop,
                                )

                            # 如果存在明确的最终文本字段，或事件类型以 done/final 结尾，则发送最终响应
                            if text_final or event_type.endswith(".done") or event_type.endswith(".final"):
                                final_text = text_final or (_extract_text(event.get("delta")) if event.get("delta") is not None else None)
                                if final_text:
                                    logger.info(f"Response final text extracted: {final_text}")
                                    # 先触发 on_response 回调（例如持久化助手消息），再发送到 websocket
                                    try:
                                        if self.session.on_response:
                                            try:
                                                self.session.on_response(final_text)
                                            except Exception as _e:
                                                logger.exception(f"on_response callback error: {_e}")
                                    except Exception:
                                        pass
                                    asyncio.run_coroutine_threadsafe(
                                        self.session._send_to_websocket({"type": "response", "text": final_text}),
                                        self.session._loop,
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
        on_response: Optional[Callable[[str], None]] = None,
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
            on_response=on_response,
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
