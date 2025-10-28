from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from ..base import MemoryKind
from ..manager import MemoryManager, MemoryAddResult


@dataclass(slots=True)
class DocumentChunk:
    text: str
    source: str
    index: int


class DocumentProcessor:
    def __init__(self, memory: MemoryManager, chunk_size: int = 400) -> None:
        self.memory = memory
        self.chunk_size = chunk_size

    def split(self, text: str, source: str) -> List[DocumentChunk]:
        paragraphs = [segment.strip() for segment in text.split("\n") if segment.strip()]
        chunks: List[DocumentChunk] = []
        index = 0
        buffer: List[str] = []
        current_length = 0
        for paragraph in paragraphs:
            if current_length + len(paragraph) > self.chunk_size and buffer:
                chunks.append(DocumentChunk("\n".join(buffer), source, index))
                index += 1
                buffer = [paragraph]
                current_length = len(paragraph)
            else:
                buffer.append(paragraph)
                current_length += len(paragraph)
        if buffer:
            chunks.append(DocumentChunk("\n".join(buffer), source, index))
        return chunks

    def ingest(self, text: str, source: str, tags: Iterable[str] | None = None) -> List[MemoryAddResult]:
        results: List[MemoryAddResult] = []
        for chunk in self.split(text, source):
            metadata = {"source": source, "chunk": chunk.index}
            result = self.memory.add_event(
                text=chunk.text,
                tags=list(tags or []) + ["document", source],
                metadata=metadata,
                kind=MemoryKind.EPISODIC,
            )
            results.append(result)
        return results
