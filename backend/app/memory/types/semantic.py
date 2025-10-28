from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List

from ..base import BaseMemory, MemoryConfig, MemoryItem, MemoryKind
from ..storage.document_store import DocumentStore, DocumentRecord
from ..storage.neo4j_store import GraphNode, GraphRelation, Neo4jGraphStore


@dataclass(slots=True)
class SemanticTriple:
    subject: str
    predicate: str
    obj: str
    subject_labels: tuple[str, ...] = ()
    object_labels: tuple[str, ...] = ()


class SemanticMemory(BaseMemory):
    def __init__(
        self,
        config: MemoryConfig,
        graph_store: Neo4jGraphStore,
        document_store: DocumentStore,
    ) -> None:
        super().__init__(MemoryKind.SEMANTIC, config)
        self.graph_store = graph_store
        self.document_store = document_store
        self.collection = config.semantic_collection

    def _parse_triple(self, item: MemoryItem) -> SemanticTriple:
        metadata = dict(item.metadata)
        subject = metadata.get("subject") or item.metadata.get("entity") or item.content
        predicate = metadata.get("predicate") or metadata.get("relation") or "describes"
        obj = metadata.get("object") or metadata.get("value") or item.content
        subject_labels = tuple(metadata.get("subject_labels", []))
        object_labels = tuple(metadata.get("object_labels", []))
        return SemanticTriple(subject, predicate, obj, subject_labels, object_labels)

    def add(self, item: MemoryItem) -> str:
        triple = self._parse_triple(item)
        subject_node = GraphNode(
            node_id=f"subject:{triple.subject}",
            labels=set(triple.subject_labels) or {"Entity"},
            properties={"name": triple.subject},
        )
        object_node = GraphNode(
            node_id=f"object:{triple.obj}",
            labels=set(triple.object_labels) or {"Entity"},
            properties={"name": triple.obj},
        )
        relation = GraphRelation(
            relation_type=triple.predicate,
            source_id=subject_node.node_id,
            target_id=object_node.node_id,
            properties={"record_id": item.record_id},
        )
        self.graph_store.upsert_node(subject_node)
        self.graph_store.upsert_node(object_node)
        self.graph_store.upsert_relation(relation)
        summary = item.content
        self.document_store.upsert(
            self.collection,
            record_id=item.record_id,
            content=summary,
            metadata={
                "subject": triple.subject,
                "predicate": triple.predicate,
                "object": triple.obj,
                "tags": list(item.tags),
            },
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
        docs = self.document_store.search(self.collection, query, limit)
        return [self._from_document(doc) for doc in docs]

    def recent(self, limit: int | None = None) -> List[MemoryItem]:
        limit = self.normalize_limit(limit)
        docs = self.document_store.recent(self.collection, limit)
        return [self._from_document(doc) for doc in docs]
