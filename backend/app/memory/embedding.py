from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Sequence

_TOKEN_RE = re.compile(r"[\w']+")


def _tokenize(text: str) -> List[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


class EmbeddingBackend(str, Enum):
    TFIDF = "tfidf"
    LOCAL = "local"
    DASHSCOPE = "dashscope"


@dataclass(slots=True)
class EmbeddingConfig:
    backend: EmbeddingBackend = EmbeddingBackend.LOCAL
    dimension: int = 384


class EmbeddingService:
    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        self.config = config or EmbeddingConfig()

    def embed(self, text: str, metadata: Sequence[str] | None = None) -> List[float]:
        tokens = _tokenize(text)
        if metadata:
            tokens.extend(str(value).lower() for value in metadata)
        if not tokens:
            return [0.0] * self.config.dimension
        buckets = [0.0] * self.config.dimension
        for token in tokens:
            digest = hashlib.sha1(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.config.dimension
            buckets[index] += 1.0
        norm = math.sqrt(sum(weight * weight for weight in buckets)) or 1.0
        return [weight / norm for weight in buckets]

    def embed_many(
        self, texts: Iterable[str], metadata: Iterable[Sequence[str]] | None = None
    ) -> List[List[float]]:
        text_list = list(texts)
        meta_list = list(metadata or ([] for _ in range(len(text_list))))
        vectors: List[List[float]] = []
        for index, text in enumerate(text_list):
            meta = meta_list[index] if index < len(meta_list) else []
            vectors.append(self.embed(text, meta))
        return vectors
