from __future__ import annotations

<<<<<<< HEAD
from datetime import datetime
from typing import List
=======
from datetime import datetime, timedelta
from typing import Any, Dict, List
>>>>>>> origin/main

from ..base import BaseMemory, MemoryConfig, MemoryItem, MemoryKind
from ..embedding import EmbeddingService
from ..storage.document_store import DocumentStore, DocumentRecord
from ..storage.qdrant_store import QdrantVectorStore, VectorRecord


class EpisodicMemory(BaseMemory):
    def __init__(
        self,
        config: MemoryConfig,
        embedding: EmbeddingService,
        vector_store: QdrantVectorStore,
        document_store: DocumentStore,
    ) -> None:
        super().__init__(MemoryKind.EPISODIC, config)
        self.embedding = embedding
        self.vector_store = vector_store
        self.document_store = document_store
        self.collection = config.episodic_collection

    def add(self, item: MemoryItem) -> str:
        embedding = item.embedding or self.embedding.embed(item.content, item.tags)
        payload = {
            "content": item.content,
            "tags": list(item.tags),
            "metadata": dict(item.metadata),
            "created_at": item.created_at.isoformat(),
<<<<<<< HEAD
=======
            "importance": item.importance,
            "user_id": item.user_id,
>>>>>>> origin/main
        }
        record = VectorRecord(record_id=item.record_id, vector=embedding, payload=payload)
        self.vector_store.upsert(self.collection, record)
        self.document_store.upsert(
            self.collection,
            record_id=item.record_id,
            content=item.content,
<<<<<<< HEAD
            metadata={"tags": list(item.tags), **dict(item.metadata)},
=======
            metadata={
                "tags": list(item.tags),
                "_importance": item.importance,
                "user_id": item.user_id,
                **dict(item.metadata),
            },
>>>>>>> origin/main
            created_at=item.created_at,
        )
        return item.record_id

    def _from_document(self, doc: DocumentRecord) -> MemoryItem:
        metadata = dict(doc.metadata)
        tags = metadata.pop("tags", [])
<<<<<<< HEAD
=======
        raw_importance = metadata.pop("_importance", metadata.pop("importance", 0.5))
        user_id = metadata.pop("user_id", "default_user")
        try:
            importance = float(raw_importance)
        except (TypeError, ValueError):
            importance = 0.5
>>>>>>> origin/main
        return MemoryItem(
            kind=self.kind,
            content=doc.content,
            tags=tags,
            metadata=metadata,
            created_at=doc.created_at,
            record_id=doc.record_id,
<<<<<<< HEAD
        )

    def search(self, query: str, limit: int | None = None) -> List[MemoryItem]:
=======
            importance=importance,
            user_id=user_id,
        )

    def retrieve(self, query: str, limit: int | None = None, **kwargs: Any) -> List[MemoryItem]:
>>>>>>> origin/main
        limit = self.normalize_limit(limit)
        vector = self.embedding.embed(query)
        matches = self.vector_store.search(self.collection, vector, limit=limit)
        output: List[MemoryItem] = []
        for score, record in matches:
            created_at = datetime.fromisoformat(record.payload["created_at"])
<<<<<<< HEAD
=======
            raw_importance = record.payload.get("importance", 0.5)
            try:
                importance = float(raw_importance)
            except (TypeError, ValueError):
                importance = 0.5
>>>>>>> origin/main
            output.append(
                MemoryItem(
                    kind=self.kind,
                    content=record.payload["content"],
                    tags=record.payload.get("tags", []),
                    metadata=record.payload.get("metadata", {}),
                    created_at=created_at,
                    score=score,
                    record_id=record.record_id,
<<<<<<< HEAD
=======
                    importance=importance,
                    user_id=record.payload.get("user_id", "default_user"),
>>>>>>> origin/main
                )
            )
        if len(output) < limit:
            recent_docs = self.document_store.search(self.collection, query, limit - len(output))
            output.extend(self._from_document(doc) for doc in recent_docs)
        return output[:limit]

<<<<<<< HEAD
=======
    def search(self, query: str, limit: int | None = None, **kwargs: Any) -> List[MemoryItem]:
        return self.retrieve(query, limit=limit, **kwargs)

>>>>>>> origin/main
    def recent(self, limit: int | None = None) -> List[MemoryItem]:
        limit = self.normalize_limit(limit)
        docs = self.document_store.recent(self.collection, limit)
        return [self._from_document(doc) for doc in docs]
<<<<<<< HEAD
=======

    def update(
        self,
        record_id: str,
        content: str | None = None,
        importance: float | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> bool:
        existing = self.document_store.get(self.collection, record_id)
        if not existing:
            return False
        current_item = self._from_document(existing)
        new_content = content if content is not None else current_item.content
        new_importance = float(importance) if importance is not None else current_item.importance
        new_metadata = dict(current_item.metadata)
        new_tags = tuple(current_item.tags)
        if metadata:
            meta_copy = dict(metadata)
            if "tags" in meta_copy:
                raw_tags = meta_copy.pop("tags")
                if isinstance(raw_tags, (list, tuple)):
                    new_tags = tuple(str(tag) for tag in raw_tags)
            new_metadata.update(meta_copy)
        updated_item = current_item.copy(
            content=new_content,
            metadata=new_metadata,
            importance=new_importance,
            tags=new_tags,
        )
        self.add(updated_item)
        return True

    def remove(self, record_id: str) -> bool:
        removed_vector = self.vector_store.remove(self.collection, record_id)
        removed_doc = self.document_store.delete(self.collection, record_id)
        return removed_vector or removed_doc

    def has_memory(self, record_id: str) -> bool:
        return self.document_store.get(self.collection, record_id) is not None

    def clear(self) -> None:
        for doc in self.document_store.list_all(self.collection):
            self.vector_store.remove(self.collection, doc.record_id)
        self.document_store.delete_collection(self.collection)

    def get_stats(self) -> Dict[str, Any]:
        count = self.document_store.count(self.collection)
        return {
            "count": count,
            "total_count": count,
            "forgotten_count": 0,
            "memory_type": self.kind.value,
        }

    def get_all(self) -> List[MemoryItem]:
        return [self._from_document(doc) for doc in self.document_store.list_all(self.collection)]

    def forget(
        self,
        strategy: str = "importance_based",
        threshold: float = 0.1,
        max_age_days: int = 30,
    ) -> int:
        docs = self.document_store.list_all(self.collection)
        removed = 0
        now = datetime.utcnow()
        for doc in docs:
            item = self._from_document(doc)
            should_remove = False
            if strategy == "importance_based" and item.importance < threshold:
                should_remove = True
            elif strategy == "time_based" and item.created_at < now - timedelta(days=max_age_days):
                should_remove = True
            if should_remove and self.remove(item.record_id):
                removed += 1
        return removed
>>>>>>> origin/main
