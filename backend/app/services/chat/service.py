from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from ...schemas import AgentMessage, ChatEvent, ChatMessage, ChatThreadOut, EmotionState
from ..agent import ConversationalAgent
from ..agent.text_chat_llm import TextChatLLMService
from ..emotion.pipeline import EmotionPipeline
from .storage import ChatStorage

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ThreadRecord:
    thread_id: str
    title: str
    participants: List[str]
    created_at: float
    last_message_at: float


class ChatService:
    """In-memory chat thread and message management with agent integration."""

    def __init__(
        self,
        agent: ConversationalAgent,
        pipeline: EmotionPipeline,
        text_chat_llm: Optional[TextChatLLMService] = None,
        storage: Optional[ChatStorage] = None,
    ) -> None:
        self.agent = agent
        self.pipeline = pipeline
        self.text_chat_llm = text_chat_llm or TextChatLLMService()
        self.storage = storage
        self._threads: Dict[str, ThreadRecord] = {}
        self._messages: Dict[str, List[ChatMessage]] = {}
        self._listeners: set[asyncio.Queue[ChatEvent]] = set()
        self._lock = asyncio.Lock()

    async def create_thread(self, title: str, participants: Iterable[str]) -> ChatThreadOut:
        async with self._lock:
            thread_id = uuid.uuid4().hex
            now = time.time()
            record = ThreadRecord(
                thread_id=thread_id,
                title=title,
                participants=list(participants),
                created_at=now,
                last_message_at=now,
            )
            self._threads[thread_id] = record
            self._messages[thread_id] = []
            
            # 保存到数据库
            if self.storage:
                self.storage.save_thread(
                    thread_id=thread_id,
                    title=title,
                    participants=list(participants),
                    created_at=now,
                    last_message_at=now,
                )
        return self._to_thread_out(record)

    async def list_threads(self) -> List[ChatThreadOut]:
        async with self._lock:
            return [self._to_thread_out(record) for record in self._threads.values()]

    async def get_thread(self, thread_id: str) -> Optional[ChatThreadOut]:
        async with self._lock:
            record = self._threads.get(thread_id)
            return self._to_thread_out(record) if record else None

    async def delete_thread(self, thread_id: str) -> bool:
        async with self._lock:
            if thread_id not in self._threads:
                return False
            
            # 删除会话记录和消息
            del self._threads[thread_id]
            if thread_id in self._messages:
                del self._messages[thread_id]
            
            # 广播会话删除事件
            await self._broadcast(ChatEvent(thread_id=thread_id, deleted=True))
            return True

    async def history(self, thread_id: str, limit: int = 100) -> List[ChatMessage]:
        async with self._lock:
            messages = self._messages.get(thread_id, [])
            return messages[-limit:]

    async def add_user_message(self, thread_id: str, text: str, language: str, use_text_chat: bool = False) -> ChatMessage:
        """添加用户消息，根据use_text_chat参数选择是否使用独立文本聊天LLM服务
        
        Args:
            thread_id: 对话线程ID
            text: 用户消息文本
            language: 消息语言
            use_text_chat: 是否使用独立文本聊天LLM服务（不依赖情绪识别）
        """
        logger.info(f"{'Text chat' if use_text_chat else 'User'} message received: thread={thread_id}, text='{text[:50]}...'")
        
        # 对于普通聊天，获取情绪状态；对于文本聊天，不使用情绪识别
        emotion = None if use_text_chat else self.pipeline.latest_state
        if not use_text_chat:
            logger.debug(f"Current emotion state: {emotion.label if emotion else 'None'}")
        
        # 添加用户消息
        message = await self._append_message(
            thread_id=thread_id,
            role="user",
            text=text,
            language=language,
            emotion=emotion,
            agent_message=None,
        )
        logger.debug(f"User message appended with id={message.message_id}")
        
        # 根据类型创建不同的后续处理任务
        if use_text_chat:
            # 使用独立文本聊天LLM服务
            asyncio.create_task(self._text_chat_follow_up(thread_id, text, language))
            logger.info(f"Text chat follow-up task created for thread {thread_id}")
        else:
            # 使用普通聊天流程
            await self.agent.ingest_user_message(text)
            logger.debug(f"User message ingested by agent")
            asyncio.create_task(self._agent_follow_up(thread_id, emotion, text))
            logger.info(f"Agent follow-up task created for thread {thread_id}")
        
        return message

    async def subscribe(self) -> asyncio.Queue[ChatEvent]:
        queue: asyncio.Queue[ChatEvent] = asyncio.Queue()
        self._listeners.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[ChatEvent]) -> None:
        self._listeners.discard(queue)

    async def _append_message(
        self,
        thread_id: str,
        role: str,
        text: str,
        language: str,
        emotion: Optional[EmotionState],
        agent_message: Optional[AgentMessage],
    ) -> ChatMessage:
        async with self._lock:
            if thread_id not in self._threads:
                raise ValueError(f"Thread {thread_id} not found")
            created_at = datetime.utcnow()
            message = ChatMessage(
                message_id=uuid.uuid4().hex,
                thread_id=thread_id,
                role=role,  # type: ignore[arg-type]
                text=text,
                created_at=created_at,
                language=language,
                emotion_label=(
                    agent_message.emotion if agent_message else (emotion.label if emotion else None)
                ),
                emotion_score=emotion.mood_score if emotion else None,
                voice_style=agent_message.voice_style if agent_message else None,
                llm_provider=agent_message.llm_provider if agent_message else None,
                tts_provider=agent_message.tts_provider if agent_message else None,
                audio_reference=agent_message.audio_reference if agent_message else None,
                audio_segments=agent_message.audio_segments if agent_message else None,
            )
            self._messages[thread_id].append(message)
            record = self._threads[thread_id]
            record.last_message_at = created_at.timestamp()
            
            # 保存到数据库
            if self.storage:
                self.storage.save_message(message)
                self.storage.update_thread_last_message(thread_id, created_at.timestamp())
        await self._broadcast(ChatEvent(thread_id=thread_id, message=message))
        return message

    async def _get_conversation_history(self, thread_id: str, limit: int = 5) -> list[dict]:
        """获取并转换对话历史为LLM服务所需的格式
        
        Args:
            thread_id: 对话线程ID
            limit: 历史消息数量限制
        
        Returns:
            转换后的对话历史列表
        """
        history = await self.history(thread_id, limit=limit)
        conversation_history = []
        
        # 转换历史消息为LLM服务所需的格式
        for msg in history:
            if msg.role == "user":
                conversation_history.append({"role": "user", "content": msg.text})
            elif msg.role == "agent":
                conversation_history.append({"role": "assistant", "content": msg.text})
        
        return conversation_history

    async def _text_chat_follow_up(self, thread_id: str, user_text: str, language: str) -> None:
        """使用独立文本聊天LLM服务生成流式回复"""
        try:
            logger.info(f"Text chat follow-up started for thread {thread_id}")
            
            # 获取对话历史
            conversation_history = await self._get_conversation_history(thread_id)
            
            # 使用独立LLM服务生成流式回复
            full_response = ""
            async for chunk in self.text_chat_llm.generate_response_stream(user_text, conversation_history):
                if chunk:
                    full_response += chunk
                    # 广播流式消息块
                    await self._broadcast(ChatEvent(
                        type="stream_chunk",
                        thread_id=thread_id,
                        stream_chunk=chunk,
                        stream_id=thread_id
                    ))
            
            # 创建AgentMessage对象
            agent_message = self.text_chat_llm.create_agent_message(full_response)
            
            # 添加AI回复到消息列表
            await self._append_message(
                thread_id=thread_id,
                role="agent",
                text=agent_message.text,
                language=agent_message.language,
                emotion=None,
                agent_message=agent_message,
            )
            logger.info(f"Text chat agent message appended to thread {thread_id}")
        except Exception as e:
            logger.exception(f"Text chat follow-up failed for thread {thread_id}: {e}")

    async def stream_text_chat_response(self, thread_id: str, user_text: str, language: str):
        """使用独立文本聊天LLM服务生成流式回复"""
        try:
            logger.info(f"Text chat stream response started for thread {thread_id}")
            
            # 获取对话历史
            conversation_history = await self._get_conversation_history(thread_id)
            
            # 使用独立LLM服务生成流式回复
            full_response = ""
            async for chunk in self.text_chat_llm.generate_response_stream(user_text, conversation_history):
                if chunk:
                    full_response += chunk
                    # 直接返回流式块
                    yield chunk
            
            # 创建AgentMessage对象
            agent_message = self.text_chat_llm.create_agent_message(full_response)
            
            # 添加AI回复到消息列表
            await self._append_message(
                thread_id=thread_id,
                role="agent",
                text=agent_message.text,
                language=agent_message.language,
                emotion=None,
                agent_message=agent_message,
            )
            logger.info(f"Text chat agent message appended to thread {thread_id}")
        except Exception as e:
            logger.exception(f"Text chat stream response failed for thread {thread_id}: {e}")
            yield f"[错误] 生成回复时出错: {str(e)}"

    async def _agent_follow_up(
        self,
        thread_id: str,
        emotion_hint: Optional[EmotionState],
        user_text: Optional[str],
    ) -> None:
        try:
            logger.info(f"Agent follow-up started for thread {thread_id}")
            emotion = emotion_hint or self.pipeline.latest_state
            logger.debug(f"Using emotion: {emotion.label if emotion else 'None'}")
            
            agent_message = await self.agent.respond_with_context(
                emotion,
                user_text=user_text,
            )
            logger.info(f"Agent generated message: {agent_message.text[:50]}...")
            
            await self._append_message(
                thread_id=thread_id,
                role="agent",
                text=agent_message.text,
                language=agent_message.language,
                emotion=emotion,
                agent_message=agent_message,
            )
            logger.info(f"Agent message appended to thread {thread_id}")
        except Exception as e:
            logger.exception(f"Agent follow-up failed for thread {thread_id}: {e}")
            # Swallow errors to avoid crashing background task, but log them

    async def _broadcast(self, event: ChatEvent) -> None:
        logger.info(f"Broadcasting event: {event.thread_id}, type: {event.type}, listeners: {len(self._listeners)}")
        for queue in list(self._listeners):
            await queue.put(event)
            logger.debug(f"Added event to queue: {event.thread_id}")

    def _to_thread_out(self, record: ThreadRecord) -> ChatThreadOut:
        return ChatThreadOut(
            thread_id=record.thread_id,
            title=record.title,
            participants=record.participants,
            created_at=datetime.utcfromtimestamp(record.created_at),
            last_message_at=datetime.utcfromtimestamp(record.last_message_at),
        )
