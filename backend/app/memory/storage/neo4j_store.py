from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass(slots=True)
class GraphNode:
    node_id: str
    labels: Set[str] = field(default_factory=set)
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GraphRelation:
    relation_type: str
    source_id: str
    target_id: str
    properties: Dict[str, Any] = field(default_factory=dict)


class Neo4jGraphStore:
    def __init__(self) -> None:
        self._nodes: Dict[str, GraphNode] = {}
        self._relations: List[GraphRelation] = []

    def upsert_node(self, node: GraphNode) -> None:
        self._nodes[node.node_id] = node

    def upsert_relation(self, relation: GraphRelation) -> None:
        self._relations.append(relation)

    def find_nodes(
        self,
        label: Optional[str] = None,
        property_key: Optional[str] = None,
        property_value: Optional[Any] = None,
    ) -> List[GraphNode]:
        matches: List[GraphNode] = []
        for node in self._nodes.values():
            if label and label not in node.labels:
                continue
            if property_key is not None:
                if node.properties.get(property_key) != property_value:
                    continue
            matches.append(node)
        return matches

    def neighbors(
        self,
        node_id: str,
        relation_type: Optional[str] = None,
    ) -> List[Tuple[GraphRelation, GraphNode]]:
        output: List[Tuple[GraphRelation, GraphNode]] = []
        for relation in self._relations:
            if relation.source_id != node_id:
                continue
            if relation_type and relation.relation_type != relation_type:
                continue
            target = self._nodes.get(relation.target_id)
            if target:
                output.append((relation, target))
        return output

    def relation_count(self) -> int:
        return len(self._relations)

    def node_count(self) -> int:
        return len(self._nodes)
<<<<<<< HEAD
=======

    def remove_relations_by_property(self, key: str, value: Any) -> int:
        before = len(self._relations)
        self._relations = [rel for rel in self._relations if rel.properties.get(key) != value]
        return before - len(self._relations)
>>>>>>> origin/main
