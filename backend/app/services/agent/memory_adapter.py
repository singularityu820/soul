from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from ...config import AgentConfig
from ...memory import (
    MemoryConfig,
    MemoryItem,
    MemoryKind,
    MemoryManager,
)
from ...memory.manager import MemoryAddResult
from ...schemas import MemoryRecordOut
from ...tools.builtin.memory_tool import MemoryTool


class AgentMemory:
    """Adapter that exposes a legacy-friendly API on top of the modular memory stack."""

    def __init__(
        self,
        config: AgentConfig | None = None,
        memory_config: MemoryConfig | None = None,
    ) -> None:
        self.agent_config = config or AgentConfig()
        self.manager = MemoryManager(memory_config)
        self._tool = MemoryTool(self.manager)

    def add_event(
        self,
        text: str,
        tags: Iterable[str] | None = None,
        metadata: Mapping[str, object] | None = None,
        kind: MemoryKind = MemoryKind.WORKING,
        cascade: bool = True,
        importance: float | None = None,
    ) -> str:
        result = self.manager.add_event(
            text=text,
            tags=tags,
            metadata=metadata,
            kind=kind,
            cascade=cascade,
            importance=importance,
        )
        return result.record_id

    def add_dialogue(
        self,
        speaker: str,
        utterance: str,
        tags: Iterable[str] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        return self.manager.add_dialogue_turn(speaker, utterance, tags, metadata).record_id

    def add_perception(
        self,
        description: str,
        modality: str,
        metadata: Mapping[str, object] | None = None,
    ) -> str:
        return self.manager.add_perception(description, modality, metadata).record_id

    def add_fact(
        self,
        subject: str,
        predicate: str,
        obj: str,
        description: Optional[str] = None,
        tags: Iterable[str] | None = None,
    ) -> str:
        return self.manager.add_fact(subject, predicate, obj, description, tags).record_id

    def search(
        self,
        query: str,
        limit: int = 5,
        kinds: Sequence[MemoryKind] | None = None,
    ) -> Sequence[MemoryItem]:
        return self.manager.search(query, limit=limit, kinds=kinds)

    def recent(self, limit: int = 10) -> Sequence[MemoryItem]:
        return self.manager.recent(limit=limit, kind=MemoryKind.WORKING)

    def snapshot(self) -> list[MemoryRecordOut]:
        return self.manager.snapshot(limit=self.agent_config.memory_limit)

    def count(self) -> int:
        return self.manager.count()

    def forget(self, record_id: str, kinds: Sequence[MemoryKind] | None = None) -> int:
        return self.manager.forget(record_id, kinds=kinds)

    def consolidate(
        self,
        limit: int = 5,
        min_importance: float = 0.65,
    ) -> Sequence[MemoryAddResult]:
        return self.manager.consolidate(limit=limit, min_importance=min_importance)

    @property
    def embedding(self):
        return self.manager.embedding

    @property
    def rag_pipeline(self):
        from ...memory.rag.pipeline import RAGPipeline

        return RAGPipeline(self.manager)

    @property
    def tool(self) -> MemoryTool:
        return self._tool

    def record_user_message(self, text: str) -> str:
        return self._tool.remember(
            text=f"用户: {text}",
            tags=("user", "dialogue"),
            metadata={"role": "user"},
            kind=MemoryKind.WORKING,
            importance=0.75,
        )

    def record_agent_message(self, text: str, proactive: bool = False) -> str:
        return self._tool.remember(
            text=f"助手: {text}",
            tags=("agent", "dialogue"),
            metadata={"role": "agent", "proactive": proactive},
            kind=MemoryKind.WORKING,
            importance=0.65 if proactive else 0.6,
        )

    def record_emotion_observation(self, label: str, mood_score: float, confidence: float) -> str:
        return self._tool.remember(
            text=f"Emotion observed: {label} (score={mood_score:.2f}, confidence={confidence:.2f})",
            tags=("emotion",),
            metadata={
                "role": "observer",
                "emotion": label,
                "mood_score": mood_score,
                "confidence": confidence,
            },
            kind=MemoryKind.PERCEPTUAL,
            importance=max(0.3, 1.0 - max(-mood_score, 0.0)),
        )

    def context_for(self, query: str, limit: int = 5) -> str:
        return self._tool.get_context_for_query(query, limit=limit)

    def recent_dialogue(self, limit: int = 5) -> list[str]:
        items = self.manager.recent(limit=limit, kind=MemoryKind.WORKING)
        return [item.content for item in items]

    def search_relevant_memories(
        self,
        query: str,
        top_k: int = 3,
        memory_types: Optional[Sequence[str]] = None,
    ) -> list[Dict[str, Any]]:
        if not query:
            return []
        types = memory_types or (
            MemoryKind.EPISODIC.value,
            MemoryKind.SEMANTIC.value,
        )
        results = self.manager.retrieve_memories(
            query=query,
            limit=top_k,
            memory_types=list(types),
            min_importance=0.0,
        )
        payload: list[Dict[str, Any]] = []
        for item in results:
            payload.append(
                {
                    "id": item.record_id,
                    "type": item.memory_type,
                    "content": item.content,
                    "importance": item.importance,
                    "metadata": dict(item.metadata),
                }
            )
        return payload

    def add_interaction(
        self,
        user_text: str,
        agent_reply: str,
        importance: float = 0.7,
    ) -> str:
        content = f"对话交互\n用户: {user_text}\n助手: {agent_reply}"
        metadata = {
            "type": "interaction",
            "role": "conversation",
        }
        return self.manager.add_memory(
            content=content,
            memory_type=MemoryKind.EPISODIC.value,
            importance=importance,
            metadata=metadata,
            auto_classify=False,
        )

    def build_context(
        self,
        query: str,
        *,
        recent_limit: int = 5,
        top_k: int = 3,
    ) -> Dict[str, Any]:
        return {
            "recent": self.recent_dialogue(limit=recent_limit),
            "relevant": self.search_relevant_memories(query, top_k=top_k),
        }
