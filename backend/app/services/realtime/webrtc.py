from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from ...schemas import WebRTCAnswer, WebRTCCandidate, WebRTCOffer


@dataclass(slots=True)
class RoomState:
    room_id: str
    offer: Optional[WebRTCOffer] = None
    answer: Optional[WebRTCAnswer] = None
    candidates: List[WebRTCCandidate] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class WebRTCSignalHub:
    """Lightweight in-memory signaling hub for future WebRTC integration."""

    def __init__(self) -> None:
        self._rooms: Dict[str, RoomState] = {}
        self._listeners: Dict[str, set[asyncio.Queue[dict]]] = {}
        self._lock = asyncio.Lock()

    async def publish_offer(self, room_id: str, offer: WebRTCOffer) -> RoomState:
        async with self._lock:
            state = self._rooms.get(room_id) or RoomState(room_id=room_id)
            state.offer = offer
            state.updated_at = datetime.utcnow()
            self._rooms[room_id] = state
        await self._broadcast(room_id, {"type": "offer", "payload": offer})
        return state

    async def publish_answer(self, room_id: str, answer: WebRTCAnswer) -> RoomState:
        async with self._lock:
            state = self._rooms.get(room_id) or RoomState(room_id=room_id)
            state.answer = answer
            state.updated_at = datetime.utcnow()
            self._rooms[room_id] = state
        await self._broadcast(room_id, {"type": "answer", "payload": answer})
        return state

    async def add_candidate(self, room_id: str, candidate: WebRTCCandidate) -> RoomState:
        async with self._lock:
            state = self._rooms.get(room_id) or RoomState(room_id=room_id)
            state.candidates.append(candidate)
            state.updated_at = datetime.utcnow()
            self._rooms[room_id] = state
        await self._broadcast(room_id, {"type": "candidate", "payload": candidate})
        return state

    async def get_state(self, room_id: str) -> Optional[RoomState]:
        async with self._lock:
            return self._rooms.get(room_id)

    async def subscribe(self, room_id: str) -> asyncio.Queue[dict]:
        queue: asyncio.Queue[dict] = asyncio.Queue()
        listeners = self._listeners.setdefault(room_id, set())
        listeners.add(queue)
        return queue

    def unsubscribe(self, room_id: str, queue: asyncio.Queue[dict]) -> None:
        listeners = self._listeners.get(room_id)
        if not listeners:
            return
        listeners.discard(queue)
        if not listeners:
            self._listeners.pop(room_id, None)

    async def _broadcast(self, room_id: str, payload: dict) -> None:
        listeners = list(self._listeners.get(room_id, set()))
        for queue in listeners:
            await queue.put(payload)
