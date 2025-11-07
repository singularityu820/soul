from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from ..schemas import MemoryRecordOut
from .base import BaseMemory, MemoryConfig, MemoryItem, MemoryKind
from .embedding import EmbeddingConfig, EmbeddingService
from .storage.document_store import DocumentStore
from .storage.neo4j_store import Neo4jGraphStore
from .storage.qdrant_store import QdrantVectorStore
from .types.episodic import EpisodicMemory
from .types.perceptual import PerceptualMemory
from .types.semantic import SemanticMemory
from .types.working import WorkingMemory


@dataclass(slots=True)
class MemoryAddResult:
    record_id: str
    kind: MemoryKind
    created_at: datetime


class MemoryManager:
    def __init__(
        self,
        config: MemoryConfig | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.config = config or MemoryConfig()
        self.embedding = embedding_service or EmbeddingService(
            EmbeddingConfig(dimension=self.config.vector_dimension)
        )
        self.vector_store = QdrantVectorStore()
        self.graph_store = Neo4jGraphStore()
        self.episodic_store = DocumentStore(self.config.episodic_db_path)
        self.perceptual_store = DocumentStore(self.config.perceptual_db_path)
        self.semantic_store = DocumentStore(self.config.semantic_db_path)

        self._memories: Dict[MemoryKind, BaseMemory] = {
            MemoryKind.WORKING: WorkingMemory(self.config),
            MemoryKind.EPISODIC: EpisodicMemory(
                self.config,
                self.embedding,
                self.vector_store,
                self.episodic_store,
            ),
            MemoryKind.PERCEPTUAL: PerceptualMemory(
                self.config,
                self.embedding,
                self.vector_store,
                self.perceptual_store,
            ),
            MemoryKind.SEMANTIC: SemanticMemory(
                self.config,
                self.graph_store,
                self.semantic_store,
            ),
        }

    def _clone(self, item: MemoryItem, kind: MemoryKind) -> MemoryItem:
        return MemoryItem(
            kind=kind,
            content=item.content,
            tags=tuple(item.tags),
            metadata=dict(item.metadata),
            created_at=item.created_at,
            embedding=item.embedding,
            record_id=item.record_id,
        )

    def _get_memory(self, kind: MemoryKind) -> BaseMemory:
        return self._memories[kind]

    def add_event(
        self,
        text: str,
        tags: Iterable[str] | None = None,
        metadata: Mapping[str, object] | None = None,
        kind: MemoryKind = MemoryKind.WORKING,
        cascade: bool = True,
        embedding: Optional[Sequence[float]] = None,
    ) -> MemoryAddResult:
        base_item = MemoryItem(
            kind=kind,
            content=text,
            tags=tuple(tags or ()),
            metadata=dict(metadata or {}),
            embedding=list(embedding) if embedding else None,
        )
        target = self._get_memory(kind)
        target.add(base_item)
        if cascade:
            for related_kind in self._cascade_targets(kind):
                self._get_memory(related_kind).add(self._clone(base_item, related_kind))
        return MemoryAddResult(
            record_id=base_item.record_id,
            kind=kind,
            created_at=base_item.created_at,
        )

    def _cascade_targets(self, kind: MemoryKind) -> List[MemoryKind]:
        if kind == MemoryKind.WORKING:
            return [MemoryKind.EPISODIC]
        if kind == MemoryKind.EPISODIC:
            return []
        if kind == MemoryKind.SEMANTIC:
            return []
        if kind == MemoryKind.PERCEPTUAL:
            return []
        return []

    def add_dialogue_turn(
        self,
        speaker: str,
        utterance: str,
        tags: Iterable[str] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> MemoryAddResult:
        combined_tags = list(tags or []) + ["dialogue", speaker]
        combined_metadata = dict(metadata or {})
        combined_metadata.setdefault("speaker", speaker)
        return self.add_event(
            text=f"{speaker}: {utterance}",
            tags=combined_tags,
            metadata=combined_metadata,
            kind=MemoryKind.EPISODIC,
        )

    def add_perception(
        self,
        description: str,
        modality: str,
        metadata: Mapping[str, object] | None = None,
    ) -> MemoryAddResult:
        tags = ["perception", modality]
        combined_metadata = {"modality": modality, **dict(metadata or {})}
        return self.add_event(
            text=description,
            tags=tags,
            metadata=combined_metadata,
            kind=MemoryKind.PERCEPTUAL,
        )

    def add_fact(
        self,
        subject: str,
        predicate: str,
        obj: str,
        description: Optional[str] = None,
        tags: Iterable[str] | None = None,
    ) -> MemoryAddResult:
        metadata = {
            "subject": subject,
            "predicate": predicate,
            "object": obj,
        }
        record_text = description or f"{subject} {predicate} {obj}"
        return self.add_event(
            text=record_text,
            tags=tags or ("fact",),
            metadata=metadata,
            kind=MemoryKind.SEMANTIC,
        )

    def search(
        self,
        query: str,
        limit: int = 5,
        kinds: Optional[Sequence[MemoryKind]] = None,
    ) -> List[MemoryItem]:
        targets = list(kinds or self._memories.keys())
        if not targets:
            return []
        per_kind = max(1, limit // len(targets))
        remainder = limit - per_kind * len(targets)
        results: List[MemoryItem] = []
        for index, kind in enumerate(targets):
            pool_limit = per_kind + (1 if index < remainder else 0)
            results.extend(self._get_memory(kind).search(query, pool_limit))
        return self._sort_results(results)[:limit]

    def recent(
        self,
        limit: int = 10,
        kind: MemoryKind = MemoryKind.WORKING,
    ) -> List[MemoryItem]:
        return self._get_memory(kind).recent(limit)

    def snapshot(self, limit: int = 12) -> List[MemoryRecordOut]:
        records = []
        for item in self.recent(limit=limit, kind=MemoryKind.WORKING):
            records.append(
                MemoryRecordOut(
                    text=item.content,
                    timestamp=item.created_at,
                    tags=list(item.tags),
                )
            )
        return records

    def count(self) -> int:
        working = self._get_memory(MemoryKind.WORKING)
        count = getattr(working, "count", lambda: 0)()
        count += self.episodic_store.count(self.config.episodic_collection)
        count += self.perceptual_store.count(self.config.perceptual_collection)
        count += self.semantic_store.count(self.config.semantic_collection)
        return count

    def _sort_results(self, items: Iterable[MemoryItem]) -> List[MemoryItem]:
        return sorted(
            items,
            key=lambda item: (
                item.score if item.score is not None else 0.0,
                item.created_at,
            ),
            reverse=True,
        )

    def add_bulk(self, items: Iterable[MemoryItem], kind: MemoryKind) -> List[str]:
        targets = self._get_memory(kind)
        return targets.add_bulk(items)
