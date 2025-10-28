from __future__ import annotations

import heapq
import re
import time
from collections import deque
from typing import Deque, List, Tuple

from ..base import BaseMemory, MemoryConfig, MemoryItem, MemoryKind

_TOKEN_RE = re.compile(r"[\w']+")


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text)}


class WorkingMemory(BaseMemory):
    def __init__(self, config: MemoryConfig) -> None:
        super().__init__(MemoryKind.WORKING, config)
        self._items: Deque[MemoryItem] = deque()

    def add(self, item: MemoryItem) -> str:
        self._items.append(item)
        self._trim()
        return item.record_id

    def _trim(self) -> None:
        ttl = self.config.working_ttl_seconds
        limit = self.config.working_max_items
        now = time.time()
        while self._items and now - self._items[0].created_at.timestamp() > ttl:
            self._items.popleft()
        while len(self._items) > limit:
            self._items.popleft()

    def search(self, query: str, limit: int | None = None) -> List[MemoryItem]:
        limit = self.normalize_limit(limit)
        tokens = _tokenize(query)
        if not tokens:
            return list(self.recent(limit))
        scored: List[Tuple[float, MemoryItem]] = []
        for item in self._items:
            item_tokens = _tokenize(item.content)
            intersection = item_tokens.intersection(tokens)
            if not intersection:
                continue
            union = item_tokens.union(tokens)
            score = len(intersection) / len(union)
            scored.append((score, item))
        top = heapq.nlargest(limit, scored, key=lambda entry: entry[0])
        return [item for _, item in top]

    def recent(self, limit: int | None = None) -> List[MemoryItem]:
        limit = self.normalize_limit(limit)
        if limit <= 0:
            return []
        return list(self._items)[-limit:]

    def count(self) -> int:
        return len(self._items)
