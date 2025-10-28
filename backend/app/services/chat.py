from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from ..schemas import (
    AgentMessage,
    ChatEvent,
    ChatMessage,
    ChatThreadOut,
    EmotionState,
)
from .agent import ConversationalAgent
from .pipeline import EmotionPipeline


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
    ) -> None:
        self.agent = agent
        self.pipeline = pipeline
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
        return self._to_thread_out(record)

    async def list_threads(self) -> List[ChatThreadOut]:
        async with self._lock:
            return [self._to_thread_out(record) for record in self._threads.values()]

    async def get_thread(self, thread_id: str) -> Optional[ChatThreadOut]:
        async with self._lock:
            record = self._threads.get(thread_id)
            return self._to_thread_out(record) if record else None

    async def history(self, thread_id: str, limit: int = 100) -> List[ChatMessage]:
        async with self._lock:
            messages = self._messages.get(thread_id, [])
            return messages[-limit:]

    async def add_user_message(self, thread_id: str, text: str, language: str) -> ChatMessage:
        emotion = self.pipeline.latest_state
        message = await self._append_message(
            thread_id=thread_id,
            role="user",
            text=text,
            language=language,
            emotion=emotion,
            agent_message=None,
        )
        await self.agent.ingest_user_message(text)
        asyncio.create_task(self._agent_follow_up(thread_id, emotion))
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
            )
            self._messages[thread_id].append(message)
            record = self._threads[thread_id]
            record.last_message_at = created_at.timestamp()
        await self._broadcast(ChatEvent(thread_id=thread_id, message=message))
        return message

    async def _agent_follow_up(
        self,
        thread_id: str,
        emotion_hint: Optional[EmotionState],
    ) -> None:
        try:
            emotion = emotion_hint or self.pipeline.latest_state
            agent_message = await self.agent.respond_with_context(emotion)
            await self._append_message(
                thread_id=thread_id,
                role="agent",
                text=agent_message.text,
                language=agent_message.language,
                emotion=emotion,
                agent_message=agent_message,
            )
        except Exception:
            # Swallow errors to avoid crashing background task; logs handled in caller.
            pass

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