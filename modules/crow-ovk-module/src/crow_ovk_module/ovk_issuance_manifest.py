from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import HTTPException

from crow_ovk_intyg import OvkIntyg, intyg_to_payload
from crow_ovk_workflow import OvkWorkflowRepository, record_to_payload

from .ovk_field_media import _FieldMediaRepository


def _digest(payload: Any) -> str:
    return sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def manifest_path(data_root: Path, project_id: str, inspection_id: str) -> Path:
    return data_root / "projects" / project_id / "ovk-issuance-manifest" / f"{inspection_id}.json"


def publish_manifest(
    data_root: Path,
    project_id: str,
    inspection_id: str,
    intyg: OvkIntyg,
    revision: str,
    review_path: Path,
) -> Path:
    """Publish before the certificate, under the shared inspection mutation lock."""
    record = OvkWorkflowRepository(data_root).load(project_id, inspection_id)
    approval = json.loads(review_path.read_bytes())
    if (
        not isinstance(approval, dict)
        or approval.get("revision") != revision
        or approval.get("intyg_id") != intyg.intyg_id
        or not approval.get("reviewed_at")
    ):
        raise ValueError("Invalid issuance review")
    root = data_root / "projects" / project_id / "ovk-field" / inspection_id
    field_digests = {
        name: sha256((root / name).read_bytes()).hexdigest()
        for name in ("snapshot.json", "context.json")
        if (root / name).is_file()
    }
    photos: list[dict[str, Any]] = []
    if "snapshot.json" in field_digests:
        snapshot = json.loads((root / "snapshot.json").read_bytes())
        if snapshot.get("inspection_id") != inspection_id:
            raise ValueError("Field snapshot identity mismatch")
        media = _FieldMediaRepository(data_root, project_id=project_id)
        for photo in snapshot.get("photos", []):
            photo_id = photo["photo_id"]
            try:
                content, receipt = media.load_media(inspection_id, photo_id)
            except (FileNotFoundError, ValueError, HTTPException) as exc:
                raise ValueError("Unverified issuance photo") from exc
            digest = sha256(content).hexdigest()
            if digest != photo.get("sha256"):
                raise ValueError("Issuance photo checksum mismatch")
            photos.append(
                {
                    "photo_id": photo_id,
                    "sha256": digest,
                    "receipt_sha256": _digest(receipt),
                    "size_bytes": len(content),
                }
            )
    workflow = record_to_payload(record)
    certificate = intyg_to_payload(intyg)
    if _digest([workflow, certificate, field_digests]) != revision:
        raise ValueError("Issuance revision changed")
    payload = {
        "schema_version": 1,
        "project_id": project_id,
        "inspection_id": inspection_id,
        "intyg_id": intyg.intyg_id,
        "prepared_at": datetime.now(UTC).isoformat(),
        "review_revision": revision,
        "review": approval,
        "workflow_sha256": _digest(workflow),
        "field_sha256": field_digests,
        "photos": photos,
        "intyg_sha256": _digest(certificate),
    }
    target = manifest_path(data_root, project_id, inspection_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent, suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target
