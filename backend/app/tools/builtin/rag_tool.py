from __future__ import annotations

from typing import Iterable

from ...memory.base import MemoryKind
from ...memory.rag.pipeline import RAGPipeline


class RagTool:
    def __init__(self, pipeline: RAGPipeline) -> None:
        self.pipeline = pipeline

    def retrieve(self, query: str, top_k: int = 5, kinds: Iterable[MemoryKind] | None = None):
        return self.pipeline.retrieve(query, top_k=top_k, kinds=kinds)

    def build_prompt(self, query: str, top_k: int = 5, kinds: Iterable[MemoryKind] | None = None) -> str:
        result = self.retrieve(query, top_k=top_k, kinds=kinds)
        return result.as_prompt()
