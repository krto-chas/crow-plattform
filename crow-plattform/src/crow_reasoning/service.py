from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from crow_building_graph.repository import GraphRepository

from .engine import TraversalEngine


class ReasoningService:
    def __init__(self, graph_path: Path):
        self.repository = GraphRepository(graph_path)
        self._cache_signature: tuple[int, int, int] | None = None
        self._engine: TraversalEngine | None = None

    def engine(self) -> TraversalEngine:
        graph = self.repository.load()
        signature = (
            len(graph["objects"]),
            len(graph["relations"]),
            hash(str(graph.get("relations", []))),
        )
        if signature != self._cache_signature:
            self._engine = TraversalEngine(graph)
            self._cache_signature = signature
        assert self._engine is not None
        return self._engine

    def traverse(self, object_id: str, **kwargs: Any) -> dict[str, Any]:
        return asdict(self.engine().traverse(object_id, **kwargs))

    def shortest_path(self, source_id: str, target_id: str, **kwargs: Any) -> dict[str, Any]:
        return asdict(self.engine().shortest_path(source_id, target_id, **kwargs))

    def impact(self, object_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.engine().impact(object_id, **kwargs)

    def diagnostics(self) -> dict[str, Any]:
        return self.engine().diagnostics()
