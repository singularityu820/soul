from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from ..base import MemoryKind
from ..embedding import EmbeddingService
from ..manager import MemoryManager


@dataclass(slots=True)
class RetrievedChunk:
    text: str
    kind: MemoryKind
    score: float
    tags: Sequence[str]


@dataclass(slots=True)
class RAGResult:
    query: str
    chunks: List[RetrievedChunk]

    def as_prompt(self) -> str:
        lines = ["# Retrieval Context"]
        for chunk in self.chunks:
            lines.append(f"[{chunk.kind.value}] {chunk.text}")
        return "\n".join(lines)


class RAGPipeline:
    def __init__(self, memory: MemoryManager, embedding_service: EmbeddingService | None = None) -> None:
        self.memory = memory
        self.embedding = embedding_service or memory.embedding

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        kinds: Iterable[MemoryKind] | None = None,
    ) -> RAGResult:
        items = self.memory.search(query, limit=top_k, kinds=tuple(kinds) if kinds else None)
        chunks: List[RetrievedChunk] = []
        for item in items:
            score = item.score if item.score is not None else 0.0
            chunks.append(
                RetrievedChunk(
                    text=item.content,
                    kind=item.kind,
                    score=score,
                    tags=item.tags,
                )
            )
        return RAGResult(query=query, chunks=chunks)
