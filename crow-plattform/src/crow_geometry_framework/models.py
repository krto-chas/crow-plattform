from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class GeometryKind(StrEnum):
    LINE = "line"
    POLYLINE = "polyline"
    CIRCLE = "circle"
    ARC = "arc"
    TEXT = "text"
    BLOCK = "block"
    INSERT = "insert"
    MESH = "mesh"
    SOLID = "solid"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float


@dataclass(frozen=True)
class BoundingBox2D:
    min_x: float
    min_y: float
    max_x: float
    max_y: float


@dataclass(frozen=True)
class ObjectIdentity:
    crow_id: str
    source_checksum: str
    source_format: str
    source_locator: dict[str, Any]


@dataclass(frozen=True)
class GeometryObject:
    object_id: str
    identity: ObjectIdentity
    kind: GeometryKind
    source_format: str
    source_locator: dict[str, Any]
    layer: str = "0"
    geometry: dict[str, Any] = field(default_factory=dict)
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GeometryLayer:
    name: str
    object_count: int
    visible: bool = True
    locked: bool = False


@dataclass(frozen=True)
class GeometryDocument:
    source_checksum: str
    source_format: str
    objects: tuple[GeometryObject, ...]
    layers: tuple[GeometryLayer, ...]
    bounds: BoundingBox2D | None
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
