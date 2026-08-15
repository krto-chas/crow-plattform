from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import (
    BoundingBox2D,
    GeometryDocument,
    GeometryKind,
    GeometryLayer,
    GeometryObject,
    ObjectIdentity,
)


def _stable_object_id(checksum: str, locator: dict[str, Any]) -> str:
    canonical = json.dumps(locator, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(f"{checksum}:{canonical}".encode()).hexdigest()[:20]
    return f"obj-{digest}"


def _bounds(objects: list[GeometryObject]) -> BoundingBox2D | None:
    xs: list[float] = []
    ys: list[float] = []
    for obj in objects:
        data = obj.geometry
        if obj.kind is GeometryKind.LINE:
            xs.extend([float(data["x1"]), float(data["x2"])])
            ys.extend([float(data["y1"]), float(data["y2"])])
        elif obj.kind in {GeometryKind.CIRCLE, GeometryKind.ARC}:
            cx, cy, r = float(data["cx"]), float(data["cy"]), float(data["r"])
            xs.extend([cx - r, cx + r])
            ys.extend([cy - r, cy + r])
        elif obj.kind is GeometryKind.POLYLINE:
            for point in data.get("points", []):
                if len(point) >= 2:
                    xs.append(float(point[0]))
                    ys.append(float(point[1]))
        elif obj.kind in {GeometryKind.TEXT, GeometryKind.INSERT}:
            if "x" in data and "y" in data:
                xs.append(float(data["x"]))
                ys.append(float(data["y"]))
    if not xs:
        return None
    return BoundingBox2D(min(xs), min(ys), max(xs), max(ys))


def geometry_from_import_manifest(
    manifest: dict[str, Any], layer_state: dict[str, dict[str, bool]] | None = None
) -> GeometryDocument:
    checksum = str(manifest["checksum_sha256"])
    source_format = str(manifest["format_id"])
    preview = manifest.get("preview") or {}
    objects: list[GeometryObject] = []
    layer_counts: dict[str, int] = {}
    warnings = list(manifest.get("warnings") or [])
    layer_state = layer_state or {}

    if source_format == "dxf" and preview.get("kind") == "dxf_2d":
        for index, raw in enumerate(preview.get("geometry") or [], 1):
            raw_type = str(raw.get("type", "")).upper()
            kind = {
                "LINE": GeometryKind.LINE,
                "CIRCLE": GeometryKind.CIRCLE,
                "ARC": GeometryKind.ARC,
                "LWPOLYLINE": GeometryKind.POLYLINE,
                "POLYLINE": GeometryKind.POLYLINE,
                "TEXT": GeometryKind.TEXT,
                "MTEXT": GeometryKind.TEXT,
                "INSERT": GeometryKind.INSERT,
            }.get(raw_type, GeometryKind.UNKNOWN)
            layer = str(raw.get("layer") or "0")
            layer_counts[layer] = layer_counts.get(layer, 0) + 1
            geometry = {
                k: v for k, v in raw.items() if k not in {"type", "layer", "text", "name", "handle"}
            }
            if kind in {GeometryKind.TEXT, GeometryKind.INSERT}:
                geometry.update(
                    {
                        key: raw[key]
                        for key in ("x", "y", "height", "rotation", "scale_x", "scale_y")
                        if key in raw
                    }
                )
            locator = {"entity_index": index, "entity_type": raw_type, "layer": layer}
            if raw.get("handle"):
                locator["handle"] = raw["handle"]
            crow_id = _stable_object_id(checksum, locator)
            identity = ObjectIdentity(crow_id, checksum, "dxf", locator)
            objects.append(
                GeometryObject(
                    object_id=crow_id,
                    identity=identity,
                    kind=kind,
                    source_format="dxf",
                    source_locator=locator,
                    layer=layer,
                    geometry=geometry,
                    properties={
                        "entity_type": raw_type,
                        **({"text": raw.get("text", "")} if kind is GeometryKind.TEXT else {}),
                        **({"name": raw.get("name", "")} if kind is GeometryKind.INSERT else {}),
                    },
                )
            )
    elif source_format == "dwg":
        warnings.append(
            "DWG-geometri är inte tillgänglig utan konverteringsadapter. "
            "Originalfilen förblir auktoritativ evidens."
        )
    elif source_format == "ifc":
        warnings.append(
            "IFC-modellträdet är importerat, "
            "men tessellerad 3D-geometri ingår inte i Geometry Framework 0.2."
        )

    layers = tuple(
        GeometryLayer(
            name,
            count,
            visible=layer_state.get(name, {}).get("visible", True),
            locked=layer_state.get(name, {}).get("locked", False),
        )
        for name, count in sorted(layer_counts.items())
    )
    return GeometryDocument(
        checksum,
        source_format,
        tuple(objects),
        layers,
        _bounds(objects),
        metadata={
            "object_count": len(objects),
            "layer_count": len(layers),
            "identity_version": "crow-object-id-v1",
        },
        warnings=tuple(dict.fromkeys(warnings)),
    )


def find_object(document: GeometryDocument, object_id: str) -> GeometryObject | None:
    return next((item for item in document.objects if item.object_id == object_id), None)


def dwg_adapter_status(path: Path | None = None) -> dict[str, Any]:
    candidates = {
        "oda_file_converter": shutil.which("ODAFileConverter"),
        "libredwg_dwg2dxf": shutil.which("dwg2dxf"),
    }
    header = None
    checksum = None
    if path and path.exists():
        raw = path.read_bytes()
        header = raw[:6].decode("ascii", errors="replace")
        checksum = hashlib.sha256(raw).hexdigest()
    available = {key: value for key, value in candidates.items() if value}
    return {
        "source_header": header,
        "source_checksum": checksum,
        "native_metadata": True,
        "geometry_available": bool(available),
        "available_adapters": available,
        "supported_adapters": [
            "ODA File Converter",
            "Autodesk RealDWG service",
            "LibreDWG dwg2dxf",
        ],
        "conversion_target": "DXF",
        "policy": "Original DWG bevaras oförändrad; "
        "härledd DXF länkas med checksumma och adapterversion.",
    }


def as_payload(document: GeometryDocument) -> dict[str, Any]:
    return asdict(document)
