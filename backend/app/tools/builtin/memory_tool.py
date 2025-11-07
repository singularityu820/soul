from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from ...memory import MemoryManager, MemoryKind


class MemoryTool:
    def __init__(self, memory: MemoryManager) -> None:
        self.memory = memory

    def remember(
        self,
        text: str,
        tags: Iterable[str] | None = None,
        metadata: Mapping[str, object] | None = None,
        kind: MemoryKind = MemoryKind.WORKING,
    ) -> str:
        result = self.memory.add_event(text, tags=tags, metadata=metadata, kind=kind)
        return result.record_id

    def recall(self, query: str, limit: int = 5, kinds: Sequence[MemoryKind] | None = None):
        return self.memory.search(query, limit=limit, kinds=kinds)

    def recent(self, limit: int = 10, kind: MemoryKind = MemoryKind.WORKING):
        return self.memory.recent(limit=limit, kind=kind)

    def snapshot(self):
        return self.memory.snapshot()
