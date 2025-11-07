from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
<<<<<<< HEAD
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence
=======
from typing import Any, Dict, Iterable, List, Optional, Sequence
>>>>>>> origin/main
from uuid import uuid4


class MemoryKind(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PERCEPTUAL = "perceptual"


@dataclass(slots=True)
class MemoryConfig:
    working_ttl_seconds: float = 1800.0
    working_max_items: int = 128
    episodic_collection: str = "episodic_events"
    perceptual_collection: str = "perceptual_events"
    semantic_collection: str = "semantic_facts"
    episodic_db_path: str = "storage/episodic.sqlite3"
    perceptual_db_path: str = "storage/perceptual.sqlite3"
    semantic_db_path: str = "storage/semantic.sqlite3"
    semantic_graph_path: str = "storage/semantic_graph.json"
    vector_dimension: int = 384
    similarity_top_k: int = 5
<<<<<<< HEAD
=======
    storage_path: str = "./memory_data"
    max_capacity: int = 100
    importance_threshold: float = 0.1
    decay_factor: float = 0.95
    working_memory_capacity: int = 10
    working_memory_tokens: int = 2000
    working_memory_ttl_minutes: int = 120
>>>>>>> origin/main


@dataclass(slots=True)
class MemoryItem:
    kind: MemoryKind
    content: str
    tags: Sequence[str] = field(default_factory=tuple)
<<<<<<< HEAD
    metadata: Mapping[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    score: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    record_id: str = field(default_factory=lambda: uuid4().hex)
=======
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    score: Optional[float] = None
    importance: float = 0.5
    created_at: datetime = field(default_factory=datetime.utcnow)
    record_id: str = field(default_factory=lambda: uuid4().hex)
    user_id: str = "default_user"

    @property
    def id(self) -> str:
        return self.record_id

    @property
    def memory_type(self) -> str:
        return self.kind.value

    def copy(self, **updates: Any) -> "MemoryItem":
        data = {
            "kind": self.kind,
            "content": self.content,
            "tags": tuple(self.tags),
            "metadata": dict(self.metadata),
            "embedding": list(self.embedding) if self.embedding is not None else None,
            "score": self.score,
            "importance": self.importance,
            "created_at": self.created_at,
            "record_id": self.record_id,
            "user_id": self.user_id,
        }
        data.update(updates)
        return MemoryItem(**data)
>>>>>>> origin/main


class BaseMemory(ABC):
    def __init__(self, kind: MemoryKind, config: MemoryConfig) -> None:
        self.kind = kind
        self.config = config

    @abstractmethod
    def add(self, item: MemoryItem) -> str:
        raise NotImplementedError

    @abstractmethod
<<<<<<< HEAD
    def search(self, query: str, limit: Optional[int] = None) -> List[MemoryItem]:
        raise NotImplementedError

=======
    def retrieve(self, query: str, limit: Optional[int] = None, **kwargs: Any) -> List[MemoryItem]:
        raise NotImplementedError

    def search(self, query: str, limit: Optional[int] = None, **kwargs: Any) -> List[MemoryItem]:
        return self.retrieve(query, limit=limit, **kwargs)

>>>>>>> origin/main
    @abstractmethod
    def recent(self, limit: Optional[int] = None) -> List[MemoryItem]:
        raise NotImplementedError

<<<<<<< HEAD
=======
    @abstractmethod
    def update(
        self,
        record_id: str,
        content: Optional[str] = None,
        importance: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def remove(self, record_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def has_memory(self, record_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_all(self) -> List[MemoryItem]:
        raise NotImplementedError

    def forget(
        self,
        strategy: str = "importance_based",
        threshold: float = 0.1,
        max_age_days: int = 30,
    ) -> int:
        return 0

>>>>>>> origin/main
    def add_bulk(self, items: Iterable[MemoryItem]) -> List[str]:
        identifiers: List[str] = []
        for item in items:
            identifiers.append(self.add(item))
        return identifiers

    def normalize_limit(self, limit: Optional[int]) -> int:
        if limit is None or limit <= 0:
            return self.config.similarity_top_k
        return limit
