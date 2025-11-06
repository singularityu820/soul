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
from ..agent.llm import LLMService
from ..agent.tts import TTSService
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
    """Chat thread and message management with SQLite persistence and agent integration."""

    def __init__(
        self,
        agent: ConversationalAgent,
        pipeline: EmotionPipeline,
        storage: Optional[ChatStorage] = None,
    ) -> None:
        self.agent = agent
        self.pipeline = pipeline
        self.storage = storage or ChatStorage()
        self._listeners: set[asyncio.Queue[ChatEvent]] = set()
        self._lock = asyncio.Lock()
        
        # Load existing threads and messages from database
        self._threads: Dict[str, ThreadRecord] = {}
        self._messages: Dict[str, List[ChatMessage]] = {}
        self._load_from_storage()
    
    def _load_from_storage(self):
        """Load threads and messages from database on startup"""
        threads = self.storage.list_threads()
        for thread in threads:
            record = ThreadRecord(
                thread_id=thread.thread_id,
                title=thread.title,
                participants=thread.participants,
                created_at=thread.created_at.timestamp(),
                last_message_at=thread.last_message_at.timestamp(),
            )
            self._threads[thread.thread_id] = record
            
            # Load messages for this thread
            messages = self.storage.get_messages(thread.thread_id)
            self._messages[thread.thread_id] = messages
        
        logger.info(f"Loaded {len(self._threads)} threads and {sum(len(msgs) for msgs in self._messages.values())} messages from storage")

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
            
            # Save to database
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

    async def add_user_message(self, thread_id: str, text: str, language: str) -> ChatMessage:
        logger.info(f"User message received: thread={thread_id}, text='{text[:50]}...'")
        emotion = self.pipeline.latest_state
        logger.debug(f"Current emotion state: {emotion.label if emotion else 'None'}")
        
        message = await self._append_message(
            thread_id=thread_id,
            role="user",
            text=text,
            language=language,
            emotion=emotion,
            agent_message=None,
        )
        logger.debug(f"User message appended with id={message.message_id}")
        
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
            
            # Save message to database
            self.storage.save_message(message)
            self.storage.update_thread_last_message(thread_id, created_at.timestamp())
        
        await self._broadcast(ChatEvent(thread_id=thread_id, message=message))
        return message

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
            
            # 创建一个临时消息用于流式更新
            temp_message_id = uuid.uuid4().hex
            created_at = datetime.utcnow()
            response_text = ""
            
            # 构建 prompt（从 agent._build_prompt 逻辑复制）
            voice_style = "balanced"
            language = "zh"
            mood_summary = f"当前情绪：{emotion.label if emotion else 'neutral'}，心境值 {emotion.mood_score if emotion else 0:.2f}"
            
            prompt_sections = [
                "你是一位贴心的聊天搭子，根据用户当前情绪给出温暖、自然的回答，语言要口语化，适当使用 emoji，让对话轻松。",
                mood_summary,
            ]
            
            if user_text:
                prompt_sections.append(f"用户最新消息：{user_text}")
            
            prompt_sections.append(f"语气偏向：{voice_style}")
            prompt_sections.append(f"语言：{language}")
            prompt_sections.append("请输出下一句回复，并紧扣上述信息。")
            prompt = "\n".join(prompt_sections)
            
            # 流式生成 LLM 响应
            llm_service = LLMService()
            
            async for chunk in llm_service.generate_stream(prompt):
                response_text += chunk
                
                # 广播流式更新
                await self._broadcast(ChatEvent(
                    thread_id=thread_id,
                    message=ChatMessage(
                        message_id=temp_message_id,
                        thread_id=thread_id,
                        role="agent",
                        text=response_text,
                        created_at=created_at,
                        language=language,
                        emotion_label=emotion.label if emotion else None,
                        emotion_score=emotion.mood_score if emotion else None,
                    )
                ))
            
            logger.info(f"Agent generated message: {response_text[:50]}...")
            
            # 生成 TTS（可选）
            tts_service = TTSService()
            audio_reference = None
            try:
                speech = await tts_service.synthesize(response_text, "zhichu_emo", language)
                audio_reference = speech.audio_reference
            except Exception as e:
                logger.warning(f"TTS failed: {e}")
            
            # 保存最终消息到数据库（使用新的消息 ID）
            final_message_id = uuid.uuid4().hex
            async with self._lock:
                message = ChatMessage(
                    message_id=final_message_id,
                    thread_id=thread_id,
                    role="agent",
                    text=response_text,
                    created_at=created_at,
                    language=language,
                    emotion_label=emotion.label if emotion else None,
                    emotion_score=emotion.mood_score if emotion else None,
                    llm_provider=llm_service.provider.value,
                    tts_provider="dashscope" if audio_reference else None,
                    audio_reference=audio_reference,
                )
                self._messages[thread_id].append(message)
                record = self._threads[thread_id]
                record.last_message_at = created_at.timestamp()
                
                # 保存到数据库
                self.storage.save_message(message)
                self.storage.update_thread_last_message(thread_id, created_at.timestamp())
            
            # 广播最终消息（带新 ID）
            await self._broadcast(ChatEvent(thread_id=thread_id, message=message))
            logger.info(f"Agent message appended to thread {thread_id}")
        except Exception as e:
            logger.exception(f"Agent follow-up failed for thread {thread_id}: {e}")
            # Swallow errors to avoid crashing background task, but log them

    async def _broadcast(self, event: ChatEvent) -> None:
        for queue in list(self._listeners):
            await queue.put(event)

    def _to_thread_out(self, record: ThreadRecord) -> ChatThreadOut:
        return ChatThreadOut(
            thread_id=record.thread_id,
            title=record.title,
            participants=record.participants,
            created_at=datetime.utcfromtimestamp(record.created_at),
            last_message_at=datetime.utcfromtimestamp(record.last_message_at),
        )
