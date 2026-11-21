from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import HTTPException

from crow_ovk_workflow import OvkWorkflowRecord, record_to_payload
from crow_ovk_workflow.flow_protocol import build_flow_protocol

from .ovk_field_surface import _field_data_from_payload


def _source(
    data_root: Path, project_id: str, inspection_id: str, record: OvkWorkflowRecord
) -> dict[str, Any]:
    root = data_root / "projects" / project_id / "ovk-field" / inspection_id
    payload = record_to_payload(record)
    inspection = payload["inspection"]
    derived = {
        key: inspection[key]
        for key in ("object", "systems", "checkpoints", "measurements", "findings")
    }
    derived["planning"] = payload["planning"]
    derived["building_structure_sha256"] = payload["building_structure_sha256"]
    canonical = json.dumps(derived, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    snapshot = (root / "snapshot.json").read_bytes()
    flow = build_flow_protocol(_field_data_from_payload(json.loads(snapshot)))
    return {
        "flow_protocol": flow,
        "project_id": project_id,
        "inspection_id": inspection_id,
        "snapshot_sha256": sha256(snapshot).hexdigest(),
        "context_sha256": sha256((root / "context.json").read_bytes()).hexdigest(),
        "derived_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
    }


def save_protocol_source(
    data_root: Path, project_id: str, inspection_id: str, record: OvkWorkflowRecord
) -> None:
    root = data_root / "projects" / project_id / "ovk-field" / inspection_id
    source = _source(data_root, project_id, inspection_id, record)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=root, suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(source, stream, sort_keys=True)
        temporary.replace(root / "protocol-source.json")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def require_current_protocol_source(
    data_root: Path, project_id: str, inspection_id: str, record: OvkWorkflowRecord
) -> dict[str, Any] | None:
    root = data_root / "projects" / project_id / "ovk-field" / inspection_id
    path = root / "protocol-source.json"
    if not path.exists() and not (root / "snapshot.json").exists():
        return None
    try:
        stored = json.loads(path.read_bytes())
        current = _source(data_root, project_id, inspection_id, record)
        flow: dict[str, Any] = current["flow_protocol"]
        if stored == current:
            return flow
        # Older source records bind the same snapshot but lack the projection.
        legacy = {key: value for key, value in current.items() if key != "flow_protocol"}
        if stored == legacy:
            return flow
    except (OSError, ValueError, KeyError, TypeError):
        pass
    raise HTTPException(status_code=409, detail={"code": "OVK_PROTOCOL_SOURCE_STALE"})


def protocol_source_is_current(
    data_root: Path, project_id: str, inspection_id: str, record: OvkWorkflowRecord
) -> bool:
    """Samma kontroll som utfärdandet gör, som ja eller nej i stället för 409."""
    try:
        require_current_protocol_source(data_root, project_id, inspection_id, record)
    except HTTPException:
        return False
    return True
