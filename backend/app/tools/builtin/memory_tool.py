from __future__ import annotations

<<<<<<< HEAD
from typing import Iterable, Mapping, Sequence

from ...memory import MemoryManager, MemoryKind


class MemoryTool:
    def __init__(self, memory: MemoryManager) -> None:
        self.memory = memory

=======
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Sequence

try:  # pragma: no cover - optional dependency path
    from hello_agents.tools.base import Tool, ToolParameter
except ImportError:  # pragma: no cover - fallback when hello_agents is unavailable
    from abc import ABC, abstractmethod

    class ToolParameter:  # type: ignore[override]
        def __init__(
            self,
            name: str,
            type: str,
            description: str,
            required: bool = True,
            default: Any | None = None,
        ) -> None:
            self.name = name
            self.type = type
            self.description = description
            self.required = required
            self.default = default

        def dict(self) -> Dict[str, Any]:
            return {
                "name": self.name,
                "type": self.type,
                "description": self.description,
                "required": self.required,
                "default": self.default,
            }

    class Tool(ABC):  # type: ignore[override]
        def __init__(self, name: str, description: str) -> None:
            self.name = name
            self.description = description

        @abstractmethod
        def run(self, parameters: Dict[str, Any]) -> str:
            raise NotImplementedError

        @abstractmethod
        def get_parameters(self) -> List[ToolParameter]:
            raise NotImplementedError

        def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
            required = [param.name for param in self.get_parameters() if param.required]
            return all(param in parameters for param in required)

        def to_dict(self) -> Dict[str, Any]:
            return {
                "name": self.name,
                "description": self.description,
                "parameters": [param.dict() for param in self.get_parameters()],
            }


from ...memory import MemoryConfig, MemoryKind, MemoryManager


class MemoryTool(Tool):
    def __init__(
        self,
        memory: MemoryManager | None = None,
        *,
        user_id: str = "default_user",
        memory_config: MemoryConfig | None = None,
        memory_types: Sequence[str] | None = None,
    ) -> None:
        super().__init__(
            name="memory",
            description="记忆工具 - 可以存储和检索对话历史、知识和经验",
        )

        self.memory_config = memory_config or MemoryConfig()
        declared_types = list(dict.fromkeys(memory_types or ("working", "episodic", "semantic")))
        self.memory_types = declared_types
        self.user_id = user_id

        if memory is None:
            enabled = set(type_name.lower() for type_name in declared_types)
            self.memory_manager = MemoryManager(
                config=self.memory_config,
                user_id=user_id,
                enable_working="working" in enabled,
                enable_episodic="episodic" in enabled,
                enable_semantic="semantic" in enabled,
                enable_perceptual="perceptual" in enabled,
            )
        else:
            self.memory_manager = memory
            self.memory_config = getattr(memory, "config", self.memory_config)
            self.user_id = getattr(memory, "user_id", user_id)
            if not declared_types:
                self.memory_types = list(memory.memory_types.keys())

        self.memory = self.memory_manager  # Backwards compatibility for existing imports
        self.current_session_id: str | None = None
        self.conversation_count = 0

    # ------------------------------------------------------------------
    # Tool interface
    # ------------------------------------------------------------------
    def run(self, parameters: Dict[str, Any]) -> str:
        if not self.validate_parameters(parameters):
            return "❌ 参数验证失败：缺少必需的参数"

        action = parameters.get("action")
        kwargs = {key: value for key, value in parameters.items() if key != "action"}
        return self.execute(action, **kwargs)

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description=(
                    "要执行的操作："
                    "add(添加记忆), search(搜索记忆), summary(获取摘要), stats(获取统计), "
                    "update(更新记忆), remove(删除记忆), forget(遗忘记忆), consolidate(整合记忆), clear_all(清空所有记忆)"
                ),
                required=True,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="记忆内容（add/update时可用；感知记忆可作描述）",
                required=False,
            ),
            ToolParameter(
                name="query",
                type="string",
                description="搜索查询（search时可用）",
                required=False,
            ),
            ToolParameter(
                name="memory_type",
                type="string",
                description="记忆类型：working, episodic, semantic, perceptual（默认：working）",
                required=False,
                default="working",
            ),
            ToolParameter(
                name="importance",
                type="number",
                description="重要性分数，0.0-1.0（add/update时可用）",
                required=False,
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="搜索结果数量限制（默认：5）",
                required=False,
                default=5,
            ),
            ToolParameter(
                name="memory_id",
                type="string",
                description="目标记忆ID（update/remove时必需）",
                required=False,
            ),
            ToolParameter(
                name="file_path",
                type="string",
                description="感知记忆：本地文件路径（image/audio）",
                required=False,
            ),
            ToolParameter(
                name="modality",
                type="string",
                description="感知记忆模态：text/image/audio（不传则按扩展名推断）",
                required=False,
            ),
            ToolParameter(
                name="strategy",
                type="string",
                description="遗忘策略：importance_based/time_based/capacity_based（forget时可用）",
                required=False,
                default="importance_based",
            ),
            ToolParameter(
                name="threshold",
                type="number",
                description="遗忘阈值（forget时可用，默认0.1）",
                required=False,
                default=0.1,
            ),
            ToolParameter(
                name="max_age_days",
                type="integer",
                description="最大保留天数（forget策略为time_based时可用）",
                required=False,
                default=30,
            ),
            ToolParameter(
                name="from_type",
                type="string",
                description="整合来源类型（consolidate时可用，默认working）",
                required=False,
                default="working",
            ),
            ToolParameter(
                name="to_type",
                type="string",
                description="整合目标类型（consolidate时可用，默认episodic）",
                required=False,
                default="episodic",
            ),
            ToolParameter(
                name="importance_threshold",
                type="number",
                description="整合重要性阈值（默认0.7）",
                required=False,
                default=0.7,
            ),
        ]

    def execute(self, action: str, **kwargs: Any) -> str:
        if action == "add":
            return self._add_memory(**kwargs)
        if action == "search":
            return self._search_memory(**kwargs)
        if action == "summary":
            return self._get_summary(**kwargs)
        if action == "stats":
            return self._get_stats()
        if action == "update":
            return self._update_memory(**kwargs)
        if action == "remove":
            return self._remove_memory(**kwargs)
        if action == "forget":
            return self._forget(**kwargs)
        if action == "consolidate":
            return self._consolidate(**kwargs)
        if action == "clear_all":
            return self._clear_all()
        return (
            f"不支持的操作: {action}。支持的操作: "
            "add, search, summary, stats, update, remove, forget, consolidate, clear_all"
        )

    # ------------------------------------------------------------------
    # Backwards-compatible helper methods used across the codebase
    # ------------------------------------------------------------------
>>>>>>> origin/main
    def remember(
        self,
        text: str,
        tags: Iterable[str] | None = None,
        metadata: Mapping[str, object] | None = None,
        kind: MemoryKind = MemoryKind.WORKING,
<<<<<<< HEAD
    ) -> str:
        result = self.memory.add_event(text, tags=tags, metadata=metadata, kind=kind)
        return result.record_id

    def recall(self, query: str, limit: int = 5, kinds: Sequence[MemoryKind] | None = None):
        return self.memory.search(query, limit=limit, kinds=kinds)

    def recent(self, limit: int = 10, kind: MemoryKind = MemoryKind.WORKING):
        return self.memory.recent(limit=limit, kind=kind)

    def snapshot(self):
        return self.memory.snapshot()
=======
        importance: float | None = None,
        cascade: bool | None = None,
    ) -> str:
        target_kind = kind if isinstance(kind, MemoryKind) else MemoryKind(str(kind))
        result = self.memory_manager.add_event(
            text,
            tags=tags,
            metadata=metadata,
            kind=target_kind,
            importance=importance,
            cascade=True if cascade is None else cascade,
        )
        return result.record_id

    def recall(
        self,
        query: str,
        limit: int = 5,
        kinds: Sequence[MemoryKind] | None = None,
    ) -> List[Any]:
        if kinds is None:
            return self.memory_manager.search(query, limit=limit)
        normalized = tuple(
            kind if isinstance(kind, MemoryKind) else MemoryKind(str(kind)) for kind in kinds
        )
        return self.memory_manager.search(query, limit=limit, kinds=normalized)

    def recent(self, limit: int = 10, kind: MemoryKind = MemoryKind.WORKING) -> List[Any]:
        target_kind = kind if isinstance(kind, MemoryKind) else MemoryKind(str(kind))
        return self.memory_manager.recent(limit=limit, kind=target_kind)

    def snapshot(self) -> List[Any]:
        return self.memory_manager.snapshot()

    def forget(
        self,
        record_id: str,
        kinds: Sequence[MemoryKind] | None = None,
    ) -> int:
        if kinds is None:
            return self.memory_manager.forget(record_id)
        normalized = tuple(
            kind if isinstance(kind, MemoryKind) else MemoryKind(str(kind)) for kind in kinds
        )
        return self.memory_manager.forget(record_id, kinds=normalized)

    def consolidate(self, limit: int = 5, min_importance: float = 0.65):
        return self.memory_manager.consolidate(limit=limit, min_importance=min_importance)

    # ------------------------------------------------------------------
    # Rich memory operations mirroring hello_agents implementation
    # ------------------------------------------------------------------
    def _add_memory(
        self,
        content: str = "",
        memory_type: str = "working",
        importance: float = 0.5,
        file_path: str | None = None,
        modality: str | None = None,
        **metadata: Any,
    ) -> str:
        try:
            if self.current_session_id is None:
                self.current_session_id = f"session_{datetime.now():%Y%m%d_%H%M%S}"

            if memory_type == "perceptual" and file_path:
                inferred = modality or self._infer_modality(file_path)
                metadata.setdefault("modality", inferred)
                metadata.setdefault("raw_data", file_path)

            metadata.update(
                {
                    "session_id": self.current_session_id,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            memory_id = self.memory_manager.add_memory(
                content=content,
                memory_type=memory_type,
                importance=importance,
                metadata=metadata,
                auto_classify=False,
            )
            return f"✅ 记忆已添加 (ID: {memory_id[:8]}...)"
        except Exception as exc:  # pragma: no cover - defensive branch
            return f"❌ 添加记忆失败: {exc}"

    def _infer_modality(self, path: str) -> str:
        try:
            ext = (path.rsplit(".", 1)[-1] or "").lower()
        except Exception:  # pragma: no cover - defensive branch
            return "text"
        if ext in {"png", "jpg", "jpeg", "bmp", "gif", "webp"}:
            return "image"
        if ext in {"mp3", "wav", "flac", "m4a", "ogg"}:
            return "audio"
        return "text"

    def _search_memory(
        self,
        query: str,
        limit: int = 5,
        memory_types: List[str] | None = None,
        memory_type: str | None = None,
        min_importance: float = 0.1,
    ) -> str:
        try:
            if memory_type and not memory_types:
                memory_types = [memory_type]

            results = self.memory_manager.retrieve_memories(
                query=query,
                limit=limit,
                memory_types=memory_types,
                min_importance=min_importance,
            )

            if not results:
                return f"🔍 未找到与 '{query}' 相关的记忆"

            lines = [f"🔍 找到 {len(results)} 条相关记忆:"]
            labels = {
                "working": "工作记忆",
                "episodic": "情景记忆",
                "semantic": "语义记忆",
                "perceptual": "感知记忆",
            }
            for index, memory in enumerate(results, 1):
                label = labels.get(memory.memory_type, memory.memory_type)
                preview = memory.content[:80] + "..." if len(memory.content) > 80 else memory.content
                lines.append(
                    f"{index}. [{label}] {preview} (重要性: {memory.importance:.2f})"
                )
            return "\n".join(lines)
        except Exception as exc:  # pragma: no cover - defensive branch
            return f"❌ 搜索记忆失败: {exc}"

    def _get_summary(self, limit: int = 10) -> str:
        try:
            stats = self.memory_manager.get_memory_stats()
            parts = [
                "📊 记忆系统摘要",
                f"总记忆数: {stats['total_memories']}",
                f"当前会话: {self.current_session_id or '未开始'}",
                f"对话轮次: {self.conversation_count}",
            ]

            if stats.get("memories_by_type"):
                parts.append("\n📋 记忆类型分布:")
                for memory_type, type_stats in stats["memories_by_type"].items():
                    count = type_stats.get("count", 0)
                    avg_importance = type_stats.get("avg_importance", 0.0)
                    label_lookup = {
                        "working": "工作记忆",
                        "episodic": "情景记忆",
                        "semantic": "语义记忆",
                        "perceptual": "感知记忆",
                    }
                    label = label_lookup.get(memory_type, memory_type)
                    parts.append(
                        f"  • {label}: {count} 条 (平均重要性: {avg_importance:.2f})"
                    )

            important_memories = self.memory_manager.retrieve_memories(
                query="",
                memory_types=None,
                limit=limit * 3,
                min_importance=0.5,
            )

            if not important_memories:
                all_items: List[Any] = []
                for memory in self.memory_manager.memory_types.values():
                    try:
                        all_items.extend(memory.get_all())
                    except Exception:  # pragma: no cover - defensive branch
                        continue
                important_memories = sorted(
                    all_items,
                    key=lambda item: item.importance,
                    reverse=True,
                )[: limit * 3]

            if important_memories:
                seen_ids: set[str] = set()
                seen_contents: set[str] = set()
                unique: List[Any] = []
                for memory in important_memories:
                    if memory.id in seen_ids:
                        continue
                    content_key = memory.content.strip().lower()
                    if content_key in seen_contents:
                        continue
                    seen_ids.add(memory.id)
                    seen_contents.add(content_key)
                    unique.append(memory)
                unique.sort(key=lambda item: item.importance, reverse=True)
                parts.append(f"\n⭐ 重要记忆 (前{min(limit, len(unique))}条):")
                for index, memory in enumerate(unique[:limit], 1):
                    preview = memory.content[:60] + "..." if len(memory.content) > 60 else memory.content
                    parts.append(f"  {index}. {preview} (重要性: {memory.importance:.2f})")

            return "\n".join(parts)
        except Exception as exc:  # pragma: no cover - defensive branch
            return f"❌ 获取摘要失败: {exc}"

    def _get_stats(self) -> str:
        try:
            stats = self.memory_manager.get_memory_stats()
            info = [
                "📈 记忆系统统计",
                f"总记忆数: {stats['total_memories']}",
                f"启用的记忆类型: {', '.join(stats['enabled_types'])}",
                f"会话ID: {self.current_session_id or '未开始'}",
                f"对话轮次: {self.conversation_count}",
            ]
            return "\n".join(info)
        except Exception as exc:  # pragma: no cover - defensive branch
            return f"❌ 获取统计信息失败: {exc}"

    def _update_memory(
        self,
        memory_id: str,
        content: str | None = None,
        importance: float | None = None,
        **metadata: Any,
    ) -> str:
        try:
            success = self.memory_manager.update_memory(
                memory_id=memory_id,
                content=content,
                importance=importance,
                metadata=metadata or None,
            )
            return "✅ 记忆已更新" if success else "⚠️ 未找到要更新的记忆"
        except Exception as exc:  # pragma: no cover - defensive branch
            return f"❌ 更新记忆失败: {exc}"

    def _remove_memory(self, memory_id: str) -> str:
        try:
            success = self.memory_manager.remove_memory(memory_id)
            return "✅ 记忆已删除" if success else "⚠️ 未找到要删除的记忆"
        except Exception as exc:  # pragma: no cover - defensive branch
            return f"❌ 删除记忆失败: {exc}"

    def _forget(
        self,
        strategy: str = "importance_based",
        threshold: float = 0.1,
        max_age_days: int = 30,
    ) -> str:
        try:
            count = self.memory_manager.forget_memories(
                strategy=strategy,
                threshold=threshold,
                max_age_days=max_age_days,
            )
            return f"🧹 已遗忘 {count} 条记忆（策略: {strategy}）"
        except Exception as exc:  # pragma: no cover - defensive branch
            return f"❌ 遗忘记忆失败: {exc}"

    def _consolidate(
        self,
        from_type: str = "working",
        to_type: str = "episodic",
        importance_threshold: float = 0.7,
    ) -> str:
        try:
            count = self.memory_manager.consolidate_memories(
                from_type=from_type,
                to_type=to_type,
                importance_threshold=importance_threshold,
            )
            return (
                "🔄 已整合 "
                f"{count} 条记忆为长期记忆（{from_type} → {to_type}，阈值={importance_threshold}）"
            )
        except Exception as exc:  # pragma: no cover - defensive branch
            return f"❌ 整合记忆失败: {exc}"

    def _clear_all(self) -> str:
        try:
            self.memory_manager.clear_all_memories()
            return "🧽 已清空所有记忆"
        except Exception as exc:  # pragma: no cover - defensive branch
            return f"❌ 清空记忆失败: {exc}"

    def auto_record_conversation(self, user_input: str, agent_response: str) -> None:
        self.conversation_count += 1
        self._add_memory(
            content=f"用户: {user_input}",
            memory_type="working",
            importance=0.6,
            type="user_input",
            conversation_id=self.conversation_count,
        )
        self._add_memory(
            content=f"助手: {agent_response}",
            memory_type="working",
            importance=0.7,
            type="agent_response",
            conversation_id=self.conversation_count,
        )
        if (
            len(agent_response) > 100
            or "重要" in user_input
            or "记住" in user_input
        ):
            interaction_content = f"对话 - 用户: {user_input}\n助手: {agent_response}"
            self._add_memory(
                content=interaction_content,
                memory_type="episodic",
                importance=0.8,
                type="interaction",
                conversation_id=self.conversation_count,
            )

    def add_knowledge(self, content: str, importance: float = 0.9) -> str:
        return self._add_memory(
            content=content,
            memory_type="semantic",
            importance=importance,
            knowledge_type="factual",
            source="manual",
        )

    def get_context_for_query(self, query: str, limit: int = 3) -> str:
        results = self.memory_manager.retrieve_memories(
            query=query,
            limit=limit,
            min_importance=0.3,
        )
        if not results:
            return ""
        context_lines = ["相关记忆:"]
        for memory in results:
            context_lines.append(f"- {memory.content}")
        return "\n".join(context_lines)

    def clear_session(self) -> None:
        self.current_session_id = None
        self.conversation_count = 0
        working = self.memory_manager.memory_types.get(MemoryKind.WORKING.value)
        if working:
            working.clear()

    def consolidate_memories(self) -> int:
        return self.memory_manager.consolidate_memories()

    def forget_old_memories(self, max_age_days: int = 30) -> int:
        return self.memory_manager.forget_memories(
            strategy="time_based",
            max_age_days=max_age_days,
        )
>>>>>>> origin/main
