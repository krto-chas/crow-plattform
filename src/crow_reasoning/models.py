from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TraversalStep:
    depth: int
    object_id: str
    via_relation_id: str | None = None
    via_relation_type: str | None = None
    direction: str | None = None


@dataclass(frozen=True)
class TraversalResult:
    start_id: str
    mode: str
    steps: tuple[TraversalStep, ...]
    relation_types: tuple[str, ...] = ()
    max_depth: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PathResult:
    source_id: str
    target_id: str
    object_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]
    found: bool


@dataclass(frozen=True)
class GraphDiagnostic:
    code: str
    severity: str
    object_ids: tuple[str, ...]
    relation_ids: tuple[str, ...] = ()
    message: str = ""
