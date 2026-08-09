from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True, slots=True)
class ReviewedLegacyFact:
    field: str
    value: str
    source_id: str
    filename: str
    locator: str
    source_sha256: str


@dataclass(frozen=True, slots=True)
class LegacyHistoricalCommit:
    inspection_id: str
    project_id: str
    inspector: str
    inspection_date: str
    source_sha256: str
    source_filename: str
    facts: tuple[ReviewedLegacyFact, ...]


class LegacyHistoryCommitRepository:
    def __init__(self, data_root: Path) -> None:
        self._snapshot_root = data_root / "ovk-field-sync"
        self._context_root = data_root / "ovk-field-context"
        self._legacy_root = data_root / "ovk-legacy-import"

    def commit(self, item: LegacyHistoricalCommit) -> str:
        _validate_id(item.inspection_id)
        if not item.project_id.strip() or not item.inspector.strip():
            raise ValueError("project_id and inspector are required")
        if not item.facts:
            raise ValueError("at least one reviewed fact is required")
        if any(fact.source_sha256 != item.source_sha256 for fact in item.facts):
            raise ValueError("all facts must refer to the committed source SHA-256")

        snapshot = _build_snapshot(item)
        context = {
            "inspection_id": item.inspection_id,
            "project_id": item.project_id,
            "inspector": item.inspector,
            "previous_inspection_id": None,
            "saved_at": datetime.now(UTC).isoformat(),
            "source_kind": "legacy_import",
            "source_filename": item.source_filename,
            "source_sha256": item.source_sha256,
            "inspection_date": item.inspection_date,
        }
        manifest = {
            "inspection_id": item.inspection_id,
            "project_id": item.project_id,
            "source_filename": item.source_filename,
            "source_sha256": item.source_sha256,
            "facts": [_fact_payload(fact) for fact in item.facts],
        }

        self._snapshot_root.mkdir(parents=True, exist_ok=True)
        self._context_root.mkdir(parents=True, exist_ok=True)
        self._legacy_root.mkdir(parents=True, exist_ok=True)
        snapshot_digest = _atomic_write(
            self._snapshot_root / f"{item.inspection_id}.json", snapshot
        )
        _atomic_write(self._context_root / f"{item.inspection_id}.json", context)
        _atomic_write(self._legacy_root / f"{item.inspection_id}.json", manifest)
        return snapshot_digest


def historical_commit_from_payload(payload: dict[str, Any]) -> LegacyHistoricalCommit:
    facts = tuple(
        ReviewedLegacyFact(
            field=str(fact["field"]),
            value=str(fact["value"]),
            source_id=str(fact["source_id"]),
            filename=str(fact["filename"]),
            locator=str(fact["locator"]),
            source_sha256=str(fact["source_sha256"]),
        )
        for fact in _object_list(payload.get("facts"))
    )
    inspection_date = str(payload.get("inspection_date", "")).strip()
    if not inspection_date:
        dates = [fact.value for fact in facts if fact.field == "inspection_date"]
        if len(set(dates)) != 1:
            raise ValueError("inspection_date must be explicit or uniquely extracted")
        inspection_date = dates[0]
    return LegacyHistoricalCommit(
        inspection_id=str(payload["inspection_id"]),
        project_id=str(payload["project_id"]),
        inspector=str(payload.get("inspector", "Legacy import")),
        inspection_date=inspection_date,
        source_sha256=str(payload["source_sha256"]),
        source_filename=str(payload["source_filename"]),
        facts=facts,
    )


def _build_snapshot(item: LegacyHistoricalCommit) -> dict[str, Any]:
    unit_numbers = _unique_values(item.facts, "apartment_number")
    units = [
        {
            "unit_id": f"legacy-unit-{index}",
            "inspection_id": item.inspection_id,
            "number": number,
            "kind": "apartment",
            "label": "Historiskt importerad",
        }
        for index, number in enumerate(unit_numbers, start=1)
    ]
    findings: list[dict[str, Any]] = []
    for index, fact in enumerate(
        (fact for fact in item.facts if fact.field == "finding"), start=1
    ):
        findings.append(
            {
                "finding_id": f"legacy-finding-{index}",
                "inspection_id": item.inspection_id,
                "unit_id": units[0]["unit_id"] if len(units) == 1 else "",
                "defect_type": "legacy_finding",
                "description": fact.value,
                "severity": "info",
                "room_id": None,
                "checkpoint_id": None,
                "system_id": None,
                "rule_refs": [],
                "origin": "stated",
                "legacy_source": _fact_payload(fact),
            }
        )
    legacy_measurements = [
        _fact_payload(fact)
        for fact in item.facts
        if fact.field in {"measured_airflow", "designed_airflow", "system_id"}
    ]
    return {
        "inspection_id": item.inspection_id,
        "units": units,
        "rooms": [],
        "findings": findings,
        "photos": [],
        "legacy": {
            "source_filename": item.source_filename,
            "source_sha256": item.source_sha256,
            "inspection_date": item.inspection_date,
            "measurements_and_systems": legacy_measurements,
        },
    }


def _unique_values(facts: tuple[ReviewedLegacyFact, ...], field: str) -> list[str]:
    return sorted({fact.value for fact in facts if fact.field == field and fact.value})


def _fact_payload(fact: ReviewedLegacyFact) -> dict[str, str]:
    return {
        "field": fact.field,
        "value": fact.value,
        "source_id": fact.source_id,
        "filename": fact.filename,
        "locator": fact.locator,
        "source_sha256": fact.source_sha256,
    }


def _object_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _atomic_write(path: Path, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(canonical, encoding="utf-8")
    temporary.replace(path)
    return sha256(canonical.rstrip("\n").encode()).hexdigest()


def _validate_id(value: str) -> None:
    if not _SAFE_ID.fullmatch(value):
        raise ValueError("invalid identifier")
