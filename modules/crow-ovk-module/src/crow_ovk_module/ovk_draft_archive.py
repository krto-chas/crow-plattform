"""Sparade protokollutkast.

Ett nytt protokollutkast ersätter besiktningens post. Har posten ändrats
sedan den senast byggdes (granskningsbeslut, täckning, inmatade uppgifter)
sparas den undan här innan den ersätts, så att arbetet inte går förlorat och
går att ta tillbaka.

Kopiorna ligger utanför ``projects/{projekt}/ovk/``, där varje JSON-fil läses
som en besiktning.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from crow_ovk_workflow import OvkWorkflowRecord, record_from_payload, record_to_payload

_ARCHIVE_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$")
_KEEP = 20


def _digest(record: OvkWorkflowRecord) -> str:
    payload = record_to_payload(record)
    # Tidsstämpeln ändras vid varje sparning och säger inget om innehållet.
    payload.pop("updated_at", None)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def _field_root(data_root: Path, project_id: str, inspection_id: str) -> Path:
    return data_root / "projects" / project_id / "ovk-field" / inspection_id


def _archive_root(data_root: Path, project_id: str, inspection_id: str) -> Path:
    return data_root / "projects" / project_id / "ovk-utkast-sparade" / inspection_id


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def summary(record: OvkWorkflowRecord) -> dict[str, int]:
    """Vad posten innehåller, för beskedet till användaren."""

    inspection = record.inspection
    return {
        "granskningsbeslut": len(record.review),
        "kontrollpunkter": len(inspection.checkpoints),
        "anmarkningar": len(inspection.findings),
        "matningar": len(inspection.measurements),
        "atgarder": len(inspection.actions),
    }


def mark_built(data_root: Path, record: OvkWorkflowRecord) -> None:
    """Notera hur posten såg ut när utkastet byggdes."""

    project_id = record.inspection.ovk_object.project_id
    inspection_id = record.inspection.inspection_id
    _write(
        _field_root(data_root, project_id, inspection_id) / "draft-built.json",
        {"record_sha256": _digest(record)},
    )


def has_unsaved_work(data_root: Path, record: OvkWorkflowRecord) -> bool:
    """Sant när posten har innehåll som inte är ett orört, byggt utkast.

    En nyplanerad post utan innehåll har inget att förlora. En post som ser ut
    precis som när den senast byggdes ersätts av ett likadant bygge. Allt annat
    räknas som arbete, även poster byggda innan den här noteringen fanns.
    """

    if not any(summary(record).values()) and record.coverage is None:
        return False
    project_id = record.inspection.ovk_object.project_id
    inspection_id = record.inspection.inspection_id
    marker = _field_root(data_root, project_id, inspection_id) / "draft-built.json"
    try:
        built = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    return not isinstance(built, dict) or built.get("record_sha256") != _digest(record)


def archive(data_root: Path, record: OvkWorkflowRecord, reason: str) -> str:
    """Spara undan posten och ge kopians id.

    Kopian skrivs alltid på nytt, med aktuell tid. En äldre, läsbar kopia med
    samma innehåll tas bort efteråt, så att samma arbete inte ligger dubbelt
    och så att gallringen aldrig tar det som senast låg på posten. En äldre
    kopia som inte går att läsa litas det inte på; den lämnas kvar.
    """

    project_id = record.inspection.ovk_object.project_id
    inspection_id = record.inspection.inspection_id
    root = _archive_root(data_root, project_id, inspection_id)
    digest = _digest(record)
    now = datetime.now(UTC)
    archive_id = f"{now.strftime('%Y%m%dT%H%M%SZ')}-{digest[:12]}"
    _write(
        root / f"{archive_id}.json",
        {
            "archive_id": archive_id,
            "project_id": project_id,
            "inspection_id": inspection_id,
            "saved_at": now.isoformat(timespec="seconds"),
            "reason": reason,
            "record_sha256": digest,
            "summary": summary(record),
            "record": record_to_payload(record),
        },
    )
    # Kopian ska gå att läsa tillbaka innan något annat litar på den.
    # (load_archived kontrollerar identitet och checksumma och kastar annars.)
    load_archived(data_root, project_id, inspection_id, archive_id)
    for older in sorted(root.glob(f"*-{digest[:12]}.json")):
        if older.stem == archive_id:
            continue
        try:
            same = json.loads(older.read_text(encoding="utf-8")).get("record_sha256") == digest
        except (OSError, ValueError, AttributeError):
            same = False
        if same:
            older.unlink(missing_ok=True)
    # De äldsta gallras, så att upprepade byggen inte fyller disken.
    for old in sorted(root.glob("*.json"))[:-_KEEP]:
        old.unlink(missing_ok=True)
    return archive_id


def list_archived(data_root: Path, project_id: str, inspection_id: str) -> list[dict[str, Any]]:
    """Sparade kopior, senaste först. Oläsbara filer redovisas, inte döljs."""

    root = _archive_root(data_root, project_id, inspection_id)
    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json"), reverse=True) if root.exists() else []:
        if not _ARCHIVE_ID.fullmatch(path.stem):
            continue
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            if (
                stored["archive_id"] != path.stem
                or stored["project_id"] != project_id
                or stored["inspection_id"] != inspection_id
            ):
                raise ValueError("identity mismatch")
            items.append(
                {
                    "archive_id": path.stem,
                    "saved_at": str(stored["saved_at"]),
                    "reason": str(stored.get("reason", "")),
                    "summary": {key: int(value) for key, value in dict(stored["summary"]).items()},
                }
            )
        except (OSError, ValueError, KeyError, TypeError):
            items.append({"archive_id": path.stem, "olasbar": True})
    return items


def load_archived(
    data_root: Path, project_id: str, inspection_id: str, archive_id: str
) -> OvkWorkflowRecord:
    """Läs en sparad kopia. FileNotFoundError om den saknas, ValueError om den är trasig."""

    if not _ARCHIVE_ID.fullmatch(archive_id):
        raise FileNotFoundError(archive_id)
    path = _archive_root(data_root, project_id, inspection_id) / f"{archive_id}.json"
    if not path.exists():
        raise FileNotFoundError(archive_id)
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
        record = record_from_payload(stored["record"])
    except (OSError, KeyError, TypeError) as exc:
        raise ValueError("stored draft is unreadable") from exc
    if (
        stored.get("project_id") != project_id
        or stored.get("inspection_id") != inspection_id
        or record.inspection.inspection_id != inspection_id
        or record.inspection.ovk_object.project_id != project_id
        or _digest(record) != stored.get("record_sha256")
    ):
        raise ValueError("stored draft does not belong to this inspection")
    return record
