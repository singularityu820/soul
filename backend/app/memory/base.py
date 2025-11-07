from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence
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


@dataclass(slots=True)
class MemoryItem:
    kind: MemoryKind
    content: str
    tags: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    score: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    record_id: str = field(default_factory=lambda: uuid4().hex)


class BaseMemory(ABC):
    def __init__(self, kind: MemoryKind, config: MemoryConfig) -> None:
        self.kind = kind
        self.config = config

    @abstractmethod
    def add(self, item: MemoryItem) -> str:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, limit: Optional[int] = None) -> List[MemoryItem]:
        raise NotImplementedError

    @abstractmethod
    def recent(self, limit: Optional[int] = None) -> List[MemoryItem]:
        raise NotImplementedError

    def add_bulk(self, items: Iterable[MemoryItem]) -> List[str]:
        identifiers: List[str] = []
        for item in items:
            identifiers.append(self.add(item))
        return identifiers

    def normalize_limit(self, limit: Optional[int]) -> int:
        if limit is None or limit <= 0:
            return self.config.similarity_top_k
        return limit
