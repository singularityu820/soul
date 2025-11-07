from __future__ import annotations

import heapq
<<<<<<< HEAD
import re
import time
from collections import deque
from typing import Deque, List, Tuple

from ..base import BaseMemory, MemoryConfig, MemoryItem, MemoryKind

_TOKEN_RE = re.compile(r"[\w']+")


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text)}

=======
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from ..base import BaseMemory, MemoryConfig, MemoryItem, MemoryKind

>>>>>>> origin/main

class WorkingMemory(BaseMemory):
    def __init__(self, config: MemoryConfig) -> None:
        super().__init__(MemoryKind.WORKING, config)
<<<<<<< HEAD
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
=======
        self.max_capacity = max(1, config.working_memory_capacity or config.working_max_items)
        self.max_tokens = max(1, config.working_memory_tokens)
        self.max_age_minutes = getattr(config, "working_memory_ttl_minutes", int(config.working_ttl_seconds / 60))
        self.session_start = datetime.utcnow()
        self.memories: List[MemoryItem] = []
        self.memory_heap: List[Tuple[float, datetime, MemoryItem]] = []
        self.current_tokens = 0

    def add(self, item: MemoryItem) -> str:
        self._expire_old_memories()
        priority = self._calculate_priority(item)
        heapq.heappush(self.memory_heap, (-priority, item.created_at, item))
        self.memories.append(item)
        self.current_tokens += self._count_tokens(item.content)
        self._enforce_capacity_limits()
        return item.record_id

    def retrieve(self, query: str, limit: int | None = None, **_: Any) -> List[MemoryItem]:
        self._expire_old_memories()
        limit = self.normalize_limit(limit)
        if not self.memories:
            return []
        query_lower = query.lower()
        scored: List[Tuple[float, MemoryItem]] = []
        for memory in self.memories:
            if memory.metadata.get("forgotten"):
                continue
            keyword_score = 0.0
            content_lower = memory.content.lower()
            if query_lower and query_lower in content_lower:
                keyword_score = len(query_lower) / max(1, len(content_lower))
            elif query_lower:
                query_words = set(query_lower.split())
                content_words = set(content_lower.split())
                if content_words:
                    intersection = query_words.intersection(content_words)
                    if intersection:
                        keyword_score = len(intersection) / len(query_words.union(content_words)) * 0.8
            # 轻量相似度分数：基于词交集的加权得分
            if query_lower:
                query_tokens = set(query_lower.split())
                content_tokens = set(content_lower.split())
                union_size = len(query_tokens.union(content_tokens)) or 1
                vector_score = len(query_tokens.intersection(content_tokens)) / union_size
            else:
                vector_score = 0.0
            base_relevance = max(vector_score, keyword_score)
            time_decay = self._calculate_time_decay(memory.created_at)
            importance_weight = 0.8 + (memory.importance * 0.4)
            final_score = base_relevance * time_decay * importance_weight
            if final_score <= 0:
                continue
            scored.append((final_score, memory.copy(score=final_score)))

        scored.sort(key=lambda entry: entry[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def search(self, query: str, limit: int | None = None, **kwargs: Any) -> List[MemoryItem]:
        return self.retrieve(query, limit=limit, **kwargs)

    def recent(self, limit: int | None = None) -> List[MemoryItem]:
        self._expire_old_memories()
        limit = self.normalize_limit(limit)
        return sorted(self.memories, key=lambda mem: mem.created_at, reverse=True)[:limit]

    def update(
        self,
        record_id: str,
        content: str | None = None,
        importance: float | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> bool:
        updated = False
        for memory in self.memories:
            if memory.record_id != record_id:
                continue
            current_tokens = self._count_tokens(memory.content)
            new_content = content if content is not None else memory.content
            new_metadata = dict(memory.metadata)
            if metadata:
                new_metadata.update(metadata)
            new_importance = float(importance) if importance is not None else memory.importance
            replacement = memory.copy(
                content=new_content,
                metadata=new_metadata,
                importance=new_importance,
            )
            index = self.memories.index(memory)
            self.memories[index] = replacement
            self.current_tokens += self._count_tokens(new_content) - current_tokens
            updated = True
            break
        if updated:
            self._rebuild_heap()
        return updated

    def remove(self, record_id: str) -> bool:
        removed = False
        remaining: List[MemoryItem] = []
        delta_tokens = 0
        for memory in self.memories:
            if memory.record_id == record_id:
                removed = True
                delta_tokens += self._count_tokens(memory.content)
            else:
                remaining.append(memory)
        if removed:
            self.memories = remaining
            self.current_tokens = max(0, self.current_tokens - delta_tokens)
            self._rebuild_heap()
        return removed

    def has_memory(self, record_id: str) -> bool:
        return any(memory.record_id == record_id for memory in self.memories)

    def clear(self) -> None:
        self.memories.clear()
        self.memory_heap.clear()
        self.current_tokens = 0

    def get_stats(self) -> Dict[str, Any]:
        self._expire_old_memories()
        active_count = len(self.memories)
        return {
            "count": active_count,
            "total_count": active_count,
            "forgotten_count": 0,
            "current_tokens": self.current_tokens,
            "max_capacity": self.max_capacity,
            "max_tokens": self.max_tokens,
            "max_age_minutes": self.max_age_minutes,
            "session_duration_minutes": (datetime.utcnow() - self.session_start).total_seconds() / 60,
            "avg_importance": (
                sum(memory.importance for memory in self.memories) / active_count if active_count else 0.0
            ),
            "capacity_usage": active_count / self.max_capacity if self.max_capacity else 0.0,
            "token_usage": self.current_tokens / self.max_tokens if self.max_tokens else 0.0,
            "memory_type": self.kind.value,
        }

    def get_all(self) -> List[MemoryItem]:
        self._expire_old_memories()
        return [memory.copy() for memory in self.memories]

    def get_recent(self, limit: int = 10) -> List[MemoryItem]:
        return self.recent(limit)

    def get_important(self, limit: int = 10) -> List[MemoryItem]:
        self._expire_old_memories()
        sorted_items = sorted(self.memories, key=lambda memory: memory.importance, reverse=True)
        return [memory.copy() for memory in sorted_items[:limit]]

    def get_context_summary(self, max_length: int = 500) -> str:
        if not self.memories:
            return "No working memories available."
        sorted_items = sorted(
            self.memories,
            key=lambda memory: (memory.importance, memory.created_at),
            reverse=True,
        )
        summary_parts: List[str] = []
        current_length = 0
        for memory in sorted_items:
            content = memory.content
            if current_length + len(content) <= max_length:
                summary_parts.append(content)
                current_length += len(content)
            else:
                remaining = max_length - current_length
                if remaining > 50:
                    summary_parts.append(content[:remaining] + "...")
                break
        return "Working Memory Context:\n" + "\n".join(summary_parts)

    def forget(
        self,
        strategy: str = "importance_based",
        threshold: float = 0.1,
        max_age_days: int = 1,
    ) -> int:
        self._expire_old_memories()
        removed_ids: List[str] = []
        now = datetime.utcnow()
        if strategy == "importance_based":
            for memory in self.memories:
                if memory.importance < threshold:
                    removed_ids.append(memory.record_id)
        elif strategy == "time_based":
            cutoff = now - timedelta(days=max_age_days)
            for memory in self.memories:
                if memory.created_at < cutoff:
                    removed_ids.append(memory.record_id)
        elif strategy == "capacity_based" and len(self.memories) > self.max_capacity:
            excess = len(self.memories) - self.max_capacity
            sorted_by_priority = sorted(self.memories, key=self._calculate_priority)
            removed_ids.extend(memory.record_id for memory in sorted_by_priority[:excess])
        removed = 0
        for record_id in removed_ids:
            if self.remove(record_id):
                removed += 1
        return removed

    def count(self) -> int:
        self._expire_old_memories()
        return len(self.memories)

    def select_for_consolidation(self, limit: int, min_importance: float) -> List[MemoryItem]:
        self._expire_old_memories()
        if limit <= 0:
            return []
        threshold = max(0.0, min(1.0, min_importance))
        candidates = [memory for memory in self.memories if memory.importance >= threshold]
        if not candidates:
            return []
        top = heapq.nlargest(
            min(limit, len(candidates)),
            candidates,
            key=lambda memory: (memory.importance, memory.created_at),
        )
        return [memory.copy() for memory in top]

    def _count_tokens(self, content: str) -> int:
        return len(content.split())

    def _calculate_priority(self, memory: MemoryItem) -> float:
        base = memory.importance
        decay = self._calculate_time_decay(memory.created_at)
        return base * decay

    def _calculate_time_decay(self, timestamp: datetime) -> float:
        hours_passed = max(0.0, (datetime.utcnow() - timestamp).total_seconds() / 3600)
        decay = self.config.decay_factor ** (hours_passed / 6) if self.config.decay_factor else 1.0
        return max(0.1, decay)

    def _enforce_capacity_limits(self) -> None:
        while len(self.memories) > self.max_capacity or self.current_tokens > self.max_tokens:
            self._remove_lowest_priority_memory()

    def _expire_old_memories(self) -> None:
        if not self.memories:
            return
        cutoff = datetime.utcnow() - timedelta(minutes=self.max_age_minutes)
        kept: List[MemoryItem] = []
        removed_tokens = 0
        for memory in self.memories:
            if memory.created_at >= cutoff:
                kept.append(memory)
            else:
                removed_tokens += self._count_tokens(memory.content)
        if len(kept) == len(self.memories):
            return
        self.memories = kept
        self.current_tokens = max(0, self.current_tokens - removed_tokens)
        self._rebuild_heap()

    def _remove_lowest_priority_memory(self) -> None:
        if not self.memories:
            return
        lowest = min(self.memories, key=self._calculate_priority)
        self.remove(lowest.record_id)

    def _rebuild_heap(self) -> None:
        self.memory_heap = []
        for memory in self.memories:
            priority = self._calculate_priority(memory)
            heapq.heappush(self.memory_heap, (-priority, memory.created_at, memory))

>>>>>>> origin/main
