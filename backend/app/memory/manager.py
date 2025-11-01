from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

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
    importance: float


class MemoryManager:
    def __init__(
        self,
        config: MemoryConfig | None = None,
        embedding_service: EmbeddingService | None = None,
        *,
        user_id: str = "default_user",
        enable_working: bool = True,
        enable_episodic: bool = True,
        enable_semantic: bool = True,
        enable_perceptual: bool = True,
    ) -> None:
        self.config = config or MemoryConfig()
        self.embedding = embedding_service or EmbeddingService(
            EmbeddingConfig(dimension=self.config.vector_dimension)
        )
        self.user_id = user_id

        self.vector_store = QdrantVectorStore()
        self.graph_store = Neo4jGraphStore()
        self.episodic_store = DocumentStore(self.config.episodic_db_path)
        self.perceptual_store = DocumentStore(self.config.perceptual_db_path)
        self.semantic_store = DocumentStore(self.config.semantic_db_path)

        self.memory_types: Dict[str, BaseMemory] = {}

        if enable_working:
            self.memory_types[MemoryKind.WORKING.value] = WorkingMemory(self.config)
        if enable_episodic:
            self.memory_types[MemoryKind.EPISODIC.value] = EpisodicMemory(
                self.config,
                self.embedding,
                self.vector_store,
                self.episodic_store,
            )
        if enable_perceptual:
            self.memory_types[MemoryKind.PERCEPTUAL.value] = PerceptualMemory(
                self.config,
                self.embedding,
                self.vector_store,
                self.perceptual_store,
            )
        if enable_semantic:
            self.memory_types[MemoryKind.SEMANTIC.value] = SemanticMemory(
                self.config,
                self.graph_store,
                self.semantic_store,
            )

        self._memories: Dict[MemoryKind, BaseMemory] = {
            kind: memory
            for kind, memory in (
                (MemoryKind(kind_name), memory)
                for kind_name, memory in self.memory_types.items()
            )
        }

    def _get_memory(self, kind: MemoryKind) -> BaseMemory:
        return self._memories[kind]

    def _get_by_type(self, memory_type: str) -> BaseMemory:
        memory = self.memory_types.get(memory_type)
        if not memory:
            raise ValueError(f"Unsupported memory type: {memory_type}")
        return memory

    def _normalize_importance(self, value: float | None) -> float:
        if value is None:
            return 0.5
        if value != value:  # NaN guard
            return 0.5
        return max(0.0, min(1.0, float(value)))

    def _build_memory_item(
        self,
        *,
        content: str,
        memory_type: str,
        importance: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryItem:
        kind = MemoryKind(memory_type)
        metadata = dict(metadata or {})
        tags = tuple(metadata.pop("tags", []))
        user_id = str(metadata.pop("user_id", self.user_id))
        return MemoryItem(
            kind=kind,
            content=content,
            tags=tags,
            metadata=metadata,
            importance=importance,
            user_id=user_id,
        )

    def _add_memory_item(self, item: MemoryItem) -> MemoryItem:
        self._get_by_type(item.kind.value).add(item)
        return item

    def add_memory(
        self,
        content: str,
        memory_type: str = "working",
        importance: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        auto_classify: bool = True,
    ) -> str:
        memory_type = self._resolve_memory_type(content, metadata, memory_type, auto_classify)
        importance_value = self._calculate_importance(content, metadata, importance)
        item = self._build_memory_item(
            content=content,
            memory_type=memory_type,
            importance=importance_value,
            metadata=metadata,
        )
        self._add_memory_item(item)
        return item.record_id

    def retrieve_memories(
        self,
        query: str,
        memory_types: Optional[List[str]] = None,
        limit: int = 10,
        min_importance: float = 0.0,
    ) -> List[MemoryItem]:
        types = memory_types or list(self.memory_types.keys())
        if not types:
            return []
        per_type = max(1, limit // len(types))
        results: List[MemoryItem] = []
        for memory_type in types:
            memory = self.memory_types.get(memory_type)
            if not memory:
                continue
            try:
                candidates = memory.retrieve(
                    query=query,
                    limit=per_type,
                    min_importance=min_importance,
                    user_id=self.user_id,
                )
                results.extend(candidates)
            except TypeError:
                # Backwards compatibility for memories without extended signature
                results.extend(memory.retrieve(query=query, limit=per_type))
        results.sort(key=lambda item: item.importance, reverse=True)
        return results[:limit]

    def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        importance: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        for memory in self.memory_types.values():
            if memory.has_memory(memory_id):
                return memory.update(memory_id, content, importance, metadata)
        return False

    def remove_memory(self, memory_id: str) -> bool:
        removed = False
        for memory in self.memory_types.values():
            if memory.remove(memory_id):
                removed = True
        return removed

    def forget_memories(
        self,
        strategy: str = "importance_based",
        threshold: float = 0.1,
        max_age_days: int = 30,
    ) -> int:
        forgotten = 0
        for memory in self.memory_types.values():
            forgotten += memory.forget(strategy=strategy, threshold=threshold, max_age_days=max_age_days)
        return forgotten

    def consolidate_memories(
        self,
        from_type: str = "working",
        to_type: str = "episodic",
        importance_threshold: float = 0.7,
    ) -> int:
        if from_type not in self.memory_types or to_type not in self.memory_types:
            return 0
        source = self.memory_types[from_type]
        target = self.memory_types[to_type]
        candidates = [
            item
            for item in getattr(source, "get_all", lambda: [])()
            if item.importance >= importance_threshold
        ]
        consolidated = 0
        for item in candidates:
            if source.remove(item.record_id):
                promoted = item.copy(
                    importance=item.importance * 1.1,
                    metadata=dict(item.metadata),
                )
                promoted.metadata.setdefault("origin", from_type)
                promoted.kind = MemoryKind(to_type)
                self._add_memory_item(promoted)
                consolidated += 1
        return consolidated

    def get_memory_stats(self) -> Dict[str, Any]:
        stats = {
            "user_id": self.user_id,
            "enabled_types": list(self.memory_types.keys()),
            "total_memories": 0,
            "memories_by_type": {},
            "config": {
                "max_capacity": self.config.max_capacity,
                "importance_threshold": self.config.importance_threshold,
                "decay_factor": self.config.decay_factor,
            },
        }
        for memory_type, memory in self.memory_types.items():
            type_stats = memory.get_stats()
            stats["memories_by_type"][memory_type] = type_stats
            stats["total_memories"] += type_stats.get("count", 0)
        return stats

    def clear_all_memories(self) -> None:
        for memory in self.memory_types.values():
            memory.clear()

    # ------------------------------------------------------------------
    # Backwards compatible helpers used by existing code paths
    # ------------------------------------------------------------------
    def add_event(
        self,
        text: str,
        tags: Iterable[str] | None = None,
        metadata: Mapping[str, object] | None = None,
        kind: MemoryKind = MemoryKind.WORKING,
        cascade: bool = True,
        embedding: Optional[Sequence[float]] = None,
        importance: float | None = None,
    ) -> MemoryAddResult:
        meta = dict(metadata or {})
        if tags:
            meta.setdefault("tags", list(tags))
        item = self._build_memory_item(
            content=text,
            memory_type=kind.value,
            importance=self._normalize_importance(importance),
            metadata=meta,
        )
        if embedding is not None:
            item.embedding = list(embedding)
        self._add_memory_item(item)
        if cascade:
            for target_kind in self._cascade_targets(kind):
                clone = item.copy(kind=target_kind)
                self._add_memory_item(clone)
        return MemoryAddResult(
            record_id=item.record_id,
            kind=kind,
            created_at=item.created_at,
            importance=item.importance,
        )

    def _cascade_targets(self, kind: MemoryKind) -> List[MemoryKind]:
        if kind == MemoryKind.WORKING and MemoryKind.EPISODIC in self._memories:
            return [MemoryKind.EPISODIC]
        return []

    def forget(
        self,
        record_id: str,
        kinds: Optional[Sequence[MemoryKind]] = None,
    ) -> int:
        targets = list(kinds or self._memories.keys())
        removed = 0
        for kind in targets:
            memory = self._memories.get(kind)
            if memory and memory.remove(record_id):
                removed += 1
        return removed

    def consolidate(
        self,
        limit: int = 5,
        min_importance: float = 0.65,
    ) -> List[MemoryAddResult]:
        working = self._memories.get(MemoryKind.WORKING)
        if not isinstance(working, WorkingMemory):
            return []
        threshold = self._normalize_importance(min_importance)
        candidates = working.select_for_consolidation(limit, threshold)
        results: List[MemoryAddResult] = []
        for item in candidates:
            result = self.add_event(
                text=item.content,
                tags=item.tags,
                metadata=item.metadata,
                kind=MemoryKind.EPISODIC,
                cascade=False,
                embedding=item.embedding,
                importance=item.importance,
            )
            working.remove(item.record_id)
            results.append(result)
        return results

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
            importance=0.6 if speaker.lower() == "user" else 0.5,
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
            importance=0.6,
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
            importance=0.7,
        )

    def search(
        self,
        query: str,
        limit: int = 5,
        kinds: Optional[Sequence[MemoryKind]] = None,
    ) -> List[MemoryItem]:
        targets = kinds or tuple(self._memories.keys())
        if not targets:
            return []
        per_kind = max(1, limit // len(targets))
        remainder = limit - per_kind * len(targets)
        results: List[MemoryItem] = []
        for index, kind in enumerate(targets):
            memory = self._memories.get(kind)
            if not memory:
                continue
            pool = per_kind + (1 if index < remainder else 0)
            results.extend(memory.search(query, pool))
        return self._sort_results(results)[:limit]

    def recent(
        self,
        limit: int = 10,
        kind: MemoryKind = MemoryKind.WORKING,
    ) -> List[MemoryItem]:
        memory = self._memories.get(kind)
        return memory.recent(limit) if memory else []

    def snapshot(self, limit: int = 12) -> List[MemoryRecordOut]:
        records = []
        for item in self.recent(limit=limit, kind=MemoryKind.WORKING):
            records.append(
                MemoryRecordOut(
                    text=item.content,
                    timestamp=item.created_at,
                    tags=list(item.tags),
                    importance=item.importance,
                )
            )
        return records

    def count(self) -> int:
        total = 0
        for memory in self.memory_types.values():
            total += memory.get_stats().get("count", 0)
        return total

    def _sort_results(self, items: Iterable[MemoryItem]) -> List[MemoryItem]:
        return sorted(
            items,
            key=lambda item: (
                item.importance,
                item.score if item.score is not None else 0.0,
                item.created_at,
            ),
            reverse=True,
        )

    def add_bulk(self, items: Iterable[MemoryItem], kind: MemoryKind) -> List[str]:
        memory = self._memories.get(kind)
        if not memory:
            return []
        return memory.add_bulk(items)

    def _resolve_memory_type(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]],
        fallback: str,
        auto_classify: bool,
    ) -> str:
        if not auto_classify:
            return fallback
        if metadata and metadata.get("type"):
            declared = str(metadata["type"]).lower()
            if declared in self.memory_types:
                return declared
        return self._classify_memory_type(content)

    def _classify_memory_type(self, content: str) -> str:
        episodic_keywords = ["昨天", "今天", "明天", "上次", "记得", "发生", "经历"]
        semantic_keywords = ["定义", "概念", "规则", "知识", "原理", "方法"]
        lower = content.lower()
        if any(keyword in content for keyword in episodic_keywords):
            if MemoryKind.EPISODIC.value in self.memory_types:
                return MemoryKind.EPISODIC.value
        if any(keyword in content for keyword in semantic_keywords):
            if MemoryKind.SEMANTIC.value in self.memory_types:
                return MemoryKind.SEMANTIC.value
        return MemoryKind.WORKING.value if MemoryKind.WORKING.value in self.memory_types else next(iter(self.memory_types))

    def _calculate_importance(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]],
        base_importance: Optional[float],
    ) -> float:
        importance = self._normalize_importance(base_importance)
        if len(content) > 100:
            importance += 0.1
        important_keywords = ["重要", "关键", "必须", "注意", "警告", "错误"]
        if any(keyword in content for keyword in important_keywords):
            importance += 0.2
        if metadata:
            priority = metadata.get("priority")
            if priority == "high":
                importance += 0.3
            elif priority == "low":
                importance -= 0.2
        return max(0.0, min(1.0, importance))
