from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from .decision_graph import DecisionGraph


@dataclass(frozen=True, slots=True)
class ComputationFingerprint:
    value: str

    @classmethod
    def from_payload(cls, payload: Any) -> ComputationFingerprint:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        ).encode("utf-8")
        return cls(sha256(encoded).hexdigest())


@dataclass(frozen=True, slots=True)
class InvalidationResult:
    source_id: str
    invalidated_node_ids: tuple[str, ...]


def invalidate_from_source(
    graph: DecisionGraph,
    source_id: str,
) -> InvalidationResult:
    return InvalidationResult(
        source_id=source_id,
        invalidated_node_ids=graph.descendants_of(source_id),
    )


class IdempotencyStore:
    def __init__(self) -> None:
        self._results: dict[str, Any] = {}

    def get(self, fingerprint: ComputationFingerprint) -> object | None:
        return self._results.get(fingerprint.value)

    def put(self, fingerprint: ComputationFingerprint, result: object) -> object:
        existing = self._results.get(fingerprint.value)
        if existing is not None:
            return existing
        self._results[fingerprint.value] = result
        return result

    def size(self) -> int:
        return len(self._results)
