from __future__ import annotations

from typing import Iterable, Mapping, Optional, Sequence

from ...config import AgentConfig
from ...memory import MemoryConfig, MemoryItem, MemoryKind, MemoryManager
from ...schemas import MemoryRecordOut


class AgentMemory:
    """Adapter that exposes a legacy-friendly API on top of the modular memory stack."""

    def __init__(
        self,
        config: AgentConfig | None = None,
        memory_config: MemoryConfig | None = None,
    ) -> None:
        self.agent_config = config or AgentConfig()
        self.manager = MemoryManager(memory_config)

    def add_event(
        self,
        text: str,
        tags: Iterable[str] | None = None,
        metadata: Mapping[str, object] | None = None,
        kind: MemoryKind = MemoryKind.WORKING,
        cascade: bool = True,
    ) -> str:
        result = self.manager.add_event(
            text=text,
            tags=tags,
            metadata=metadata,
            kind=kind,
            cascade=cascade,
        )
        return result.record_id

    def add_dialogue(
        self,
        speaker: str,
        utterance: str,
        tags: Iterable[str] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        return self.manager.add_dialogue_turn(speaker, utterance, tags, metadata).record_id

    def add_perception(
        self,
        description: str,
        modality: str,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        return self.manager.add_perception(description, modality, metadata).record_id

    def add_fact(
        self,
        subject: str,
        predicate: str,
        obj: str,
        description: Optional[str] = None,
        tags: Iterable[str] | None = None,
    ) -> str:
        return self.manager.add_fact(subject, predicate, obj, description, tags).record_id

    def search(
        self,
        query: str,
        limit: int = 5,
        kinds: Sequence[MemoryKind] | None = None,
    ) -> Sequence[MemoryItem]:
        return self.manager.search(query, limit=limit, kinds=kinds)

    def recent(self, limit: int = 10) -> Sequence[MemoryItem]:
        return self.manager.recent(limit=limit, kind=MemoryKind.WORKING)

    def snapshot(self) -> list[MemoryRecordOut]:
        return self.manager.snapshot(limit=self.agent_config.memory_limit)

    def count(self) -> int:
        return self.manager.count()

    @property
    def embedding(self):
        return self.manager.embedding

    @property
    def rag_pipeline(self):
        from ...memory.rag.pipeline import RAGPipeline

        return RAGPipeline(self.manager)
