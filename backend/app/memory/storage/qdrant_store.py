from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass(slots=True)
class VectorRecord:
    record_id: str
    vector: List[float]
    payload: Dict[str, Any]


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Vector dimensions do not match")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


class QdrantVectorStore:
    def __init__(self) -> None:
        self._collections: Dict[str, Dict[str, VectorRecord]] = {}

    def upsert(self, collection: str, record: VectorRecord) -> None:
        bucket = self._collections.setdefault(collection, {})
        bucket[record.record_id] = record

    def remove(self, collection: str, record_id: str) -> None:
        bucket = self._collections.get(collection)
        if not bucket:
            return
        bucket.pop(record_id, None)

    def search(
        self,
        collection: str,
        vector: List[float],
        limit: int = 5,
        min_score: float = 0.0,
    ) -> List[Tuple[float, VectorRecord]]:
        bucket = self._collections.get(collection)
        if not bucket:
            return []
        scored = []
        for record in bucket.values():
            score = _cosine_similarity(vector, record.vector)
            if score < min_score:
                continue
            scored.append((score, record))
        top = heapq.nlargest(limit, scored, key=lambda item: item[0])
        return top

    def count(self, collection: str) -> int:
        return len(self._collections.get(collection, {}))
