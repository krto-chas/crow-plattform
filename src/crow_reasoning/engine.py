from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable
from typing import Any

from .models import GraphDiagnostic, PathResult, TraversalResult, TraversalStep

DEFAULT_FLOW_RELATIONS = frozenset(
    {"feeds", "returns_to", "serves", "connects_to", "depends_on", "contains"}
)


class TraversalEngine:
    """Domänneutral traversering över Crow Building Graph-snapshots."""

    def __init__(self, graph: dict[str, Any]):
        self.graph = graph
        self.objects = {item["id"]: item for item in graph.get("objects", [])}
        self.relations = list(graph.get("relations", []))
        self._out: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._in: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for relation in self.relations:
            self._out[relation["source_id"]].append(relation)
            self._in[relation["target_id"]].append(relation)

    def traverse(
        self,
        start_id: str,
        *,
        direction: str = "both",
        relation_types: Iterable[str] | None = None,
        max_depth: int | None = None,
    ) -> TraversalResult:
        self._require(start_id)
        if direction not in {"outgoing", "incoming", "both"}:
            raise ValueError("direction måste vara outgoing, incoming eller both")
        allowed = frozenset(relation_types or ())
        visited = {start_id}
        queue = deque([(start_id, 0)])
        steps = [TraversalStep(depth=0, object_id=start_id)]
        while queue:
            current, depth = queue.popleft()
            if max_depth is not None and depth >= max_depth:
                continue
            candidates: list[tuple[dict[str, Any], str, str]] = []
            if direction in {"outgoing", "both"}:
                candidates.extend((r, r["target_id"], "outgoing") for r in self._out[current])
            if direction in {"incoming", "both"}:
                candidates.extend((r, r["source_id"], "incoming") for r in self._in[current])
            for relation, nxt, edge_direction in candidates:
                if allowed and relation["relation_type"] not in allowed:
                    continue
                if nxt in visited:
                    continue
                visited.add(nxt)
                steps.append(
                    TraversalStep(
                        depth=depth + 1,
                        object_id=nxt,
                        via_relation_id=relation["id"],
                        via_relation_type=relation["relation_type"],
                        direction=edge_direction,
                    )
                )
                queue.append((nxt, depth + 1))
        return TraversalResult(
            start_id=start_id,
            mode=direction,
            steps=tuple(steps),
            relation_types=tuple(sorted(allowed)),
            max_depth=max_depth,
        )

    def upstream(self, start_id: str, **kwargs: Any) -> TraversalResult:
        return self.traverse(start_id, direction="incoming", **kwargs)

    def downstream(self, start_id: str, **kwargs: Any) -> TraversalResult:
        return self.traverse(start_id, direction="outgoing", **kwargs)

    def shortest_path(
        self,
        source_id: str,
        target_id: str,
        *,
        relation_types: Iterable[str] | None = None,
        direction: str = "both",
    ) -> PathResult:
        self._require(source_id)
        self._require(target_id)
        if source_id == target_id:
            return PathResult(source_id, target_id, (source_id,), (), True)
        allowed = frozenset(relation_types or ())
        queue = deque([source_id])
        previous: dict[str, tuple[str, str]] = {}
        visited = {source_id}
        while queue:
            current = queue.popleft()
            candidates: list[tuple[dict[str, Any], str]] = []
            if direction in {"outgoing", "both"}:
                candidates.extend((r, r["target_id"]) for r in self._out[current])
            if direction in {"incoming", "both"}:
                candidates.extend((r, r["source_id"]) for r in self._in[current])
            for relation, nxt in candidates:
                if allowed and relation["relation_type"] not in allowed:
                    continue
                if nxt in visited:
                    continue
                visited.add(nxt)
                previous[nxt] = (current, relation["id"])
                if nxt == target_id:
                    return self._reconstruct(source_id, target_id, previous)
                queue.append(nxt)
        return PathResult(source_id, target_id, (), (), False)

    def impact(
        self,
        start_id: str,
        *,
        relation_types: Iterable[str] | None = None,
        max_depth: int | None = None,
    ) -> dict[str, Any]:
        result = self.downstream(
            start_id, relation_types=relation_types or DEFAULT_FLOW_RELATIONS, max_depth=max_depth
        )
        ids = [step.object_id for step in result.steps[1:]]
        by_type: dict[str, int] = defaultdict(int)
        by_discipline: dict[str, int] = defaultdict(int)
        for object_id in ids:
            obj = self.objects[object_id]
            by_type[obj.get("object_type", "unknown")] += 1
            by_discipline[obj.get("discipline", "generic")] += 1
        return {
            "start_id": start_id,
            "affected_object_ids": ids,
            "affected_count": len(ids),
            "by_object_type": dict(sorted(by_type.items())),
            "by_discipline": dict(sorted(by_discipline.items())),
            "max_depth_reached": max((step.depth for step in result.steps), default=0),
        }

    def isolated_objects(self) -> list[GraphDiagnostic]:
        return [
            GraphDiagnostic(
                code="isolated_object",
                severity="warning",
                object_ids=(object_id,),
                message="Objektet saknar relationer",
            )
            for object_id in sorted(self.objects)
            if not self._out[object_id] and not self._in[object_id]
        ]

    def dead_ends(self, *, relation_types: Iterable[str] | None = None) -> list[GraphDiagnostic]:
        allowed = frozenset(relation_types or DEFAULT_FLOW_RELATIONS)
        incoming = {r["target_id"] for r in self.relations if r["relation_type"] in allowed}
        outgoing = {r["source_id"] for r in self.relations if r["relation_type"] in allowed}
        return [
            GraphDiagnostic(
                code="dead_end",
                severity="info",
                object_ids=(object_id,),
                message="Flödet slutar vid objektet",
            )
            for object_id in sorted(incoming - outgoing)
        ]

    def cycles(self, *, relation_types: Iterable[str] | None = None) -> list[GraphDiagnostic]:
        allowed = frozenset(relation_types or DEFAULT_FLOW_RELATIONS)
        adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for r in self.relations:
            if r["relation_type"] in allowed:
                adjacency[r["source_id"]].append((r["target_id"], r["id"]))
        state: dict[str, int] = {}
        stack: list[str] = []
        edge_stack: list[str] = []
        found: set[tuple[str, ...]] = set()
        diagnostics: list[GraphDiagnostic] = []

        def visit(node: str) -> None:
            state[node] = 1
            stack.append(node)
            for nxt, relation_id in adjacency[node]:
                if state.get(nxt, 0) == 0:
                    edge_stack.append(relation_id)
                    visit(nxt)
                    edge_stack.pop()
                elif state.get(nxt) == 1:
                    index = stack.index(nxt)
                    cycle_nodes = tuple(stack[index:] + [nxt])
                    canonical = tuple(sorted(set(cycle_nodes)))
                    if canonical not in found:
                        found.add(canonical)
                        cycle_edges = tuple(edge_stack[index:] + [relation_id])
                        diagnostics.append(
                            GraphDiagnostic(
                                code="cycle",
                                severity="error",
                                object_ids=cycle_nodes,
                                relation_ids=cycle_edges,
                                message="Cykel upptäckt i riktad graf",
                            )
                        )
            stack.pop()
            state[node] = 2

        for object_id in sorted(self.objects):
            if state.get(object_id, 0) == 0:
                visit(object_id)
        return diagnostics

    def diagnostics(self) -> dict[str, Any]:
        isolated = self.isolated_objects()
        dead_ends = self.dead_ends()
        cycles = self.cycles()
        return {
            "isolated_objects": [d.__dict__ for d in isolated],
            "dead_ends": [d.__dict__ for d in dead_ends],
            "cycles": [d.__dict__ for d in cycles],
            "summary": {
                "isolated_objects": len(isolated),
                "dead_ends": len(dead_ends),
                "cycles": len(cycles),
            },
        }

    def _require(self, object_id: str) -> None:
        if object_id not in self.objects:
            raise KeyError(object_id)

    @staticmethod
    def _reconstruct(
        source_id: str, target_id: str, previous: dict[str, tuple[str, str]]
    ) -> PathResult:
        objects = [target_id]
        relations: list[str] = []
        current = target_id
        while current != source_id:
            current, relation_id = previous[current]
            objects.append(current)
            relations.append(relation_id)
        objects.reverse()
        relations.reverse()
        return PathResult(source_id, target_id, tuple(objects), tuple(relations), True)
