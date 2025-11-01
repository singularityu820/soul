from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List

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
        subject = metadata.get("subject") or metadata.get("entity") or item.content
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
            properties={
                "record_id": item.record_id,
                "importance": item.importance,
                "user_id": item.user_id,
            },
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
                "_importance": item.importance,
                "user_id": item.user_id,
                **dict(item.metadata),
            },
            created_at=item.created_at,
        )
        return item.record_id

    def _from_document(self, doc: DocumentRecord) -> MemoryItem:
        metadata = dict(doc.metadata)
        tags = metadata.pop("tags", [])
        raw_importance = metadata.pop("_importance", metadata.pop("importance", 0.5))
        user_id = metadata.pop("user_id", "default_user")
        try:
            importance = float(raw_importance)
        except (TypeError, ValueError):
            importance = 0.5
        return MemoryItem(
            kind=self.kind,
            content=doc.content,
            tags=tags,
            metadata=metadata,
            created_at=doc.created_at,
            record_id=doc.record_id,
            importance=importance,
            user_id=user_id,
        )

    def retrieve(self, query: str, limit: int | None = None, **kwargs: Any) -> List[MemoryItem]:
        limit = self.normalize_limit(limit)
        docs = self.document_store.search(self.collection, query, limit)
        if query.strip() and not docs:
            docs = self._fuzzy_search(query, limit)
        return [self._from_document(doc) for doc in docs]

    def search(self, query: str, limit: int | None = None, **kwargs: Any) -> List[MemoryItem]:
        return self.retrieve(query, limit=limit, **kwargs)

    def recent(self, limit: int | None = None) -> List[MemoryItem]:
        limit = self.normalize_limit(limit)
        docs = self.document_store.recent(self.collection, limit)
        return [self._from_document(doc) for doc in docs]

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
        self.remove(record_id)
        self.add(updated_item)
        return True

    def remove(self, record_id: str) -> bool:
        removed_doc = self.document_store.delete(self.collection, record_id)
        removed_rel = self.graph_store.remove_relations_by_property("record_id", record_id)
        return removed_doc or removed_rel > 0

    def has_memory(self, record_id: str) -> bool:
        return self.document_store.get(self.collection, record_id) is not None

    def clear(self) -> None:
        for doc in self.document_store.list_all(self.collection):
            self.graph_store.remove_relations_by_property("record_id", doc.record_id)
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _fuzzy_search(self, query: str, limit: int) -> List[DocumentRecord]:
        normalized_query = self._normalize_text(query)
        query_tokens = set(self._tokenize(query))
        if not (normalized_query or query_tokens):
            return []

        scored: List[tuple[float, DocumentRecord]] = []
        for record in self.document_store.list_all(self.collection):
            score = self._score_record(record, normalized_query, query_tokens)
            if score <= 0:
                continue
            scored.append((score, record))

        scored.sort(key=lambda entry: (entry[0], entry[1].created_at), reverse=True)
        return [record for _, record in scored[:limit]]

    def _score_record(
        self,
        record: DocumentRecord,
        normalized_query: str,
        query_tokens: set[str],
    ) -> float:
        content_norm = self._normalize_text(record.content)
        content_tokens = set(self._tokenize(record.content))
        metadata_strings: List[str] = []
        metadata_tokens: set[str] = set()

        for value in (record.metadata or {}).values():
            if isinstance(value, str):
                metadata_strings.append(value)
                metadata_tokens.update(self._tokenize(value))
            elif isinstance(value, (list, tuple)):
                for entry in value:
                    if isinstance(entry, str):
                        metadata_strings.append(entry)
                        metadata_tokens.update(self._tokenize(entry))

        combined_tokens = content_tokens | metadata_tokens
        overlap = query_tokens & combined_tokens if query_tokens else set()
        token_score = len(overlap) / max(len(query_tokens), 1) if query_tokens else 0.0

        substring_score = 0.0
        if normalized_query:
            if normalized_query in content_norm:
                substring_score += 0.7
            for text in metadata_strings:
                normalized_meta = self._normalize_text(text)
                if not normalized_meta:
                    continue
                if normalized_query in normalized_meta or normalized_meta in normalized_query:
                    substring_score += 0.5

        return token_score + substring_score

    def _tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""
        lowered = text.lower()
        return re.sub(r"[^\w\u4e00-\u9fff]", "", lowered)
