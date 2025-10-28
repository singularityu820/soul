from __future__ import annotations

from datetime import datetime
from typing import List

from ..base import BaseMemory, MemoryConfig, MemoryItem, MemoryKind
from ..embedding import EmbeddingService
from ..storage.document_store import DocumentStore, DocumentRecord
from ..storage.qdrant_store import QdrantVectorStore, VectorRecord


class PerceptualMemory(BaseMemory):
    def __init__(
        self,
        config: MemoryConfig,
        embedding: EmbeddingService,
        vector_store: QdrantVectorStore,
        document_store: DocumentStore,
    ) -> None:
        super().__init__(MemoryKind.PERCEPTUAL, config)
        self.embedding = embedding
        self.vector_store = vector_store
        self.document_store = document_store
        self.collection = config.perceptual_collection

    def add(self, item: MemoryItem) -> str:
        embedding = item.embedding or self.embedding.embed(item.content, item.tags)
        payload = {
            "content": item.content,
            "tags": list(item.tags),
            "metadata": dict(item.metadata),
            "created_at": item.created_at.isoformat(),
        }
        record = VectorRecord(record_id=item.record_id, vector=embedding, payload=payload)
        self.vector_store.upsert(self.collection, record)
        self.document_store.upsert(
            self.collection,
            record_id=item.record_id,
            content=item.content,
            metadata={"tags": list(item.tags), **dict(item.metadata)},
            created_at=item.created_at,
        )
        return item.record_id

    def _from_document(self, doc: DocumentRecord) -> MemoryItem:
        metadata = dict(doc.metadata)
        tags = metadata.pop("tags", [])
        return MemoryItem(
            kind=self.kind,
            content=doc.content,
            tags=tags,
            metadata=metadata,
            created_at=doc.created_at,
            record_id=doc.record_id,
        )

    def search(self, query: str, limit: int | None = None) -> List[MemoryItem]:
        limit = self.normalize_limit(limit)
        vector = self.embedding.embed(query)
        matches = self.vector_store.search(self.collection, vector, limit=limit)
        output: List[MemoryItem] = []
        for score, record in matches:
            created_at_value = record.payload.get("created_at")
            if isinstance(created_at_value, str):
                created_at = datetime.fromisoformat(created_at_value)
            elif isinstance(created_at_value, datetime):
                created_at = created_at_value
            else:
                created_at = datetime.utcnow()
            output.append(
                MemoryItem(
                    kind=self.kind,
                    content=record.payload["content"],
                    tags=record.payload.get("tags", []),
                    metadata=record.payload.get("metadata", {}),
                    created_at=created_at,
                    score=score,
                    record_id=record.record_id,
                )
            )
        if len(output) < limit:
            docs = self.document_store.search(self.collection, query, limit - len(output))
            output.extend(self._from_document(doc) for doc in docs)
        return output[:limit]

    def recent(self, limit: int | None = None) -> List[MemoryItem]:
        limit = self.normalize_limit(limit)
        docs = self.document_store.recent(self.collection, limit)
        return [self._from_document(doc) for doc in docs]
