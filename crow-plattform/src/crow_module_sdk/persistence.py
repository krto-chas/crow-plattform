from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from .decision_graph import DecisionGraph, GraphEdge, GraphNode, Relation
from .invalidation import ComputationFingerprint


@dataclass(frozen=True, slots=True)
class StoredFingerprint:
    fingerprint: str
    result_reference: str


class DecisionGraphRepository(Protocol):
    def save(self, graph_id: str, graph: DecisionGraph) -> None: ...

    def load(self, graph_id: str) -> DecisionGraph | None: ...


class FingerprintRepository(Protocol):
    def save(self, fingerprint: ComputationFingerprint, result_reference: str) -> None: ...

    def find(self, fingerprint: ComputationFingerprint) -> StoredFingerprint | None: ...


class JsonDecisionGraphRepository:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, graph_id: str, graph: DecisionGraph) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "graph_id": graph_id,
            "nodes": [asdict(node) for node in graph.nodes],
            "edges": [
                {
                    "source_id": edge.source_id,
                    "relation": edge.relation.value,
                    "target_id": edge.target_id,
                }
                for edge in graph.edges
            ],
        }
        self._path(graph_id).write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def load(self, graph_id: str) -> DecisionGraph | None:
        path = self._path(graph_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "1.0":
            raise ValueError("Unsupported Decision Graph persistence schema")

        graph = DecisionGraph()
        for item in payload["nodes"]:
            graph.add_node(GraphNode(id=item["id"], node_type=item["node_type"]))
        for item in payload["edges"]:
            graph.add_edge(
                GraphEdge(
                    source_id=item["source_id"],
                    relation=Relation(item["relation"]),
                    target_id=item["target_id"],
                )
            )
        return graph

    def _path(self, graph_id: str) -> Path:
        safe_id = graph_id.replace("/", "_").replace("\\", "_")
        return self._directory / f"{safe_id}.json"


class JsonFingerprintRepository:
    def __init__(self, path: Path) -> None:
        self._path = path

    def save(self, fingerprint: ComputationFingerprint, result_reference: str) -> None:
        records = self._read()
        records[fingerprint.value] = result_reference
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(records, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def find(self, fingerprint: ComputationFingerprint) -> StoredFingerprint | None:
        value = self._read().get(fingerprint.value)
        if value is None:
            return None
        return StoredFingerprint(fingerprint.value, value)

    def _read(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Fingerprint repository must contain a JSON object")
        return {str(key): str(value) for key, value in payload.items()}
