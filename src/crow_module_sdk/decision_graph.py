from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Relation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    SELECTS = "selects"
    REJECTS = "rejects"
    CREATES = "creates"
    PRICES = "prices"
    EXPLAINS = "explains"
    INVALIDATES = "invalidates"


@dataclass(frozen=True, slots=True)
class GraphNode:
    id: str
    node_type: str


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source_id: str
    relation: Relation
    target_id: str


class DecisionGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []

    @property
    def nodes(self) -> tuple[GraphNode, ...]:
        return tuple(sorted(self._nodes.values(), key=lambda node: node.id))

    @property
    def edges(self) -> tuple[GraphEdge, ...]:
        return tuple(
            sorted(
                self._edges,
                key=lambda edge: (edge.source_id, edge.relation.value, edge.target_id),
            )
        )

    def add_node(self, node: GraphNode) -> None:
        existing = self._nodes.get(node.id)
        if existing is not None and existing != node:
            raise ValueError(f"Node id already exists with another type: {node.id}")
        self._nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
            raise ValueError("Both nodes must exist before an edge is added")
        if edge not in self._edges:
            self._edges.append(edge)

    def trace_to(self, target_id: str) -> tuple[GraphEdge, ...]:
        if target_id not in self._nodes:
            raise KeyError(target_id)
        result: list[GraphEdge] = []
        frontier = [target_id]
        visited: set[str] = set()
        while frontier:
            current = frontier.pop()
            if current in visited:
                continue
            visited.add(current)
            incoming = [edge for edge in self._edges if edge.target_id == current]
            result.extend(incoming)
            frontier.extend(edge.source_id for edge in incoming)
        return tuple(
            sorted(
                result,
                key=lambda edge: (edge.source_id, edge.relation.value, edge.target_id),
            )
        )

    def descendants_of(self, source_id: str) -> tuple[str, ...]:
        if source_id not in self._nodes:
            raise KeyError(source_id)
        result: set[str] = set()
        frontier = [source_id]
        while frontier:
            current = frontier.pop()
            outgoing = [edge for edge in self._edges if edge.source_id == current]
            for edge in outgoing:
                if edge.target_id not in result:
                    result.add(edge.target_id)
                    frontier.append(edge.target_id)
        return tuple(sorted(result))
