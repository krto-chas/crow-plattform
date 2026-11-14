"""Offline, non-destructive migration of legacy OVK field data."""

from __future__ import annotations

import argparse
import json
import re
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from crow_ovk_fastighet import BesiktningsmanRepository
from fastapi import HTTPException

from crow_ovk_workflow.repository import OvkWorkflowRepository

from .ovk_field_media import _FieldMediaRepository
from .ovk_field_surface import _FieldSyncRepository, _validated_payload

_SAFE_ID = re.compile(r"[A-Za-z0-9._-]+")


def _identifier(value: object) -> str:
    if not isinstance(value, str) or value in {".", ".."} or not _SAFE_ID.fullmatch(value):
        raise ValueError("invalid identifier")
    return value


def _read(path: Path) -> dict[str, Any]:
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def migrate_field_data(data_root: Path, *, apply: bool = False) -> list[dict[str, Any]]:
    """Run only with all application writers stopped when apply is true."""
    results: list[dict[str, Any]] = []
    workflows = OvkWorkflowRepository(data_root)
    legacy_media = _FieldMediaRepository(data_root)
    snapshots = data_root / "ovk-field-sync"
    contexts = data_root / "ovk-field-context"
    ids = {path.stem for path in snapshots.glob("*.json")}
    ids.update(path.stem for path in contexts.glob("*.json"))
    ids.update(path.name for path in (data_root / "ovk-field-media").glob("*") if path.is_dir())
    for inspection_id in sorted(ids):
        result: dict[str, Any] = {"inspection_id": inspection_id}
        try:
            _identifier(inspection_id)
            context = _read(contexts / f"{inspection_id}.json")
            project_id = _identifier(context.get("project_id"))
            result["project_id"] = project_id
            snapshot, revision = _FieldSyncRepository(data_root).load(inspection_id)
            if (
                context.get("inspection_id") != inspection_id
                or snapshot.get("inspection_id") != inspection_id
            ):
                raise ValueError("legacy identity mismatch")
            record = workflows.load(project_id, inspection_id)
            if record.inspection.ovk_object.project_id != project_id:
                raise ValueError("workflow project mismatch")
            planning = record.planning
            if planning is None:
                raise ValueError("planned workflow required")
            if context.get("previous_inspection_id") != planning.previous_inspection_id:
                raise ValueError("predecessor mismatch")
            if context.get("system_type") not in {
                system.system_type for system in record.inspection.systems
            }:
                raise ValueError("system type mismatch")
            person = BesiktningsmanRepository(data_root).load(planning.inspector_id)
            if context.get("inspector_id") not in (None, planning.inspector_id):
                raise ValueError("legacy inspector identity mismatch")
            if context.get("inspector_id") is None:
                matches = [
                    item.besiktningsman_id
                    for item in BesiktningsmanRepository(data_root).list()
                    if item.namn == context.get("inspector")
                ]
                if matches != [planning.inspector_id]:
                    raise ValueError("legacy inspector identity requires manual reconciliation")
            context = {**context, "inspector_id": planning.inspector_id, "inspector": person.namn}
            _validated_payload(snapshot)
            target = data_root / "projects" / project_id / "ovk-field" / inspection_id
            if target.exists() or target.is_symlink():
                raise ValueError("destination already exists")
            photos: list[tuple[str, str, str, bytes]] = []
            for photo in snapshot.get("photos", []):
                photo_id = _identifier(photo.get("photo_id"))
                if photo.get("sync_status") != "synced":
                    continue
                content, receipt = legacy_media.load_media(inspection_id, photo_id)
                digest = sha256(content).hexdigest()
                mime = photo.get("mime_type")
                if (
                    receipt.get("inspection_id") != inspection_id
                    or receipt.get("photo_id") != photo_id
                    or receipt.get("sha256") != digest
                    or photo.get("sha256") != digest
                    or receipt.get("mime_type") != mime
                    or receipt.get("size_bytes") != len(content)
                    or not isinstance(mime, str)
                    or mime not in {"image/jpeg", "image/png", "image/webp"}
                    or not 0 < len(content) <= 25 * 1024 * 1024
                ):
                    raise ValueError("legacy media verification failed")
                photos.append((photo_id, digest, mime, content))
            result.update(status="ready", snapshot_sha256=revision, verified_photos=len(photos))
            if apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                with TemporaryDirectory(dir=target.parent) as directory:
                    stage = Path(directory)
                    media = _FieldMediaRepository(stage, project_id=project_id)
                    for photo_id, digest, mime, content in photos:
                        media.save_media(
                            inspection_id=inspection_id,
                            photo_id=photo_id,
                            mime_type=mime,
                            digest=digest,
                            content=content,
                        )
                    staged = stage / "projects" / project_id / "ovk-field" / inspection_id
                    _write(staged / "context.json", context)
                    _write(staged / "snapshot.json", snapshot)
                    _write(staged / "migration.json", {**result, "status": "migrated"})
                    if target.exists() or target.is_symlink():
                        raise ValueError("destination already exists")
                    staged.rename(target)
                result["status"] = "migrated"
        except (OSError, ValueError, TypeError, KeyError, HTTPException) as exc:
            result.update(status="blocked", reason=str(exc))
        results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_root", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--offline-confirmed", action="store_true")
    args = parser.parse_args()
    if args.apply and not args.offline_confirmed:
        parser.error("--apply requires --offline-confirmed (stop all application writers)")
    if not args.data_root.is_dir():
        parser.error("data_root must exist")
    results = migrate_field_data(args.data_root, apply=args.apply)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if any(item["status"] == "blocked" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
