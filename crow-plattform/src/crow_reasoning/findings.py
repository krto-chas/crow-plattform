from __future__ import annotations

import csv
import io
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

VALID_FINDING_STATUSES = {"open", "acknowledged", "resolved", "dismissed"}
ACTIVE_FINDING_STATUSES = {"open", "acknowledged"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


class FindingRepository:
    """Atomisk persistens och livscykel för deterministiska regel-findings."""

    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": "crow-findings-v0.1", "revision": 0, "findings": [], "history": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        os.replace(tmp, self.path)


class FindingService:
    """Synkroniserar utvärderade findings med en persistent, granskningsbar livscykel."""

    def __init__(self, repository: FindingRepository):
        self.repository = repository

    def synchronize(
        self, evaluation: dict[str, Any], *, actor: str = "rule-engine"
    ) -> dict[str, Any]:
        store = self.repository.load()
        now = _now()
        existing = {item["id"]: item for item in store.get("findings", [])}
        incoming = {item["id"]: item for item in evaluation.get("findings", [])}
        history = list(store.get("history", []))

        created = reopened = unchanged = auto_resolved = 0
        merged: dict[str, dict[str, Any]] = {}

        for finding_id, finding in incoming.items():
            current = existing.get(finding_id)
            if current is None:
                item = dict(finding)
                item.update(
                    {
                        "status": "open",
                        "first_seen_at": now,
                        "last_seen_at": now,
                        "resolved_at": None,
                        "resolution_note": None,
                        "assignee": None,
                        "occurrence_count": 1,
                    }
                )
                history.append(self._event(finding_id, "created", actor, now, to_status="open"))
                created += 1
            else:
                item = dict(current)
                lifecycle = {
                    key: item.get(key)
                    for key in (
                        "status",
                        "first_seen_at",
                        "resolved_at",
                        "resolution_note",
                        "assignee",
                        "occurrence_count",
                    )
                }
                item.update(finding)
                item.update(lifecycle)
                item["last_seen_at"] = now
                item["occurrence_count"] = int(current.get("occurrence_count", 1)) + 1
                if current.get("status") == "resolved":
                    item.update({"status": "open", "resolved_at": None, "resolution_note": None})
                    history.append(
                        self._event(
                            finding_id,
                            "reopened",
                            actor,
                            now,
                            from_status="resolved",
                            to_status="open",
                        )
                    )
                    reopened += 1
                else:
                    unchanged += 1
            merged[finding_id] = item

        for finding_id, current in existing.items():
            if finding_id in incoming:
                continue
            item = dict(current)
            if item.get("status") in ACTIVE_FINDING_STATUSES:
                old_status = item.get("status")
                item.update(
                    {
                        "status": "resolved",
                        "resolved_at": now,
                        "resolution_note": "Regeln utlöses inte längre.",
                    }
                )
                history.append(
                    self._event(
                        finding_id,
                        "auto_resolved",
                        actor,
                        now,
                        from_status=old_status,
                        to_status="resolved",
                    )
                )
                auto_resolved += 1
            merged[finding_id] = item

        store = {
            "schema": "crow-findings-v0.1",
            "revision": int(store.get("revision", 0)) + 1,
            "evaluated_at": now,
            "rule_evaluation_schema": evaluation.get("schema"),
            "findings": sorted(merged.values(), key=lambda item: item["id"]),
            "history": history,
            "sync": {
                "created": created,
                "reopened": reopened,
                "unchanged": unchanged,
                "auto_resolved": auto_resolved,
            },
        }
        self.repository.save(store)
        return self.list()

    def update_status(
        self,
        finding_id: str,
        status: str,
        *,
        actor: str,
        note: str | None = None,
        assignee: str | None = None,
    ) -> dict[str, Any]:
        if status not in VALID_FINDING_STATUSES:
            raise ValueError(f"Ogiltig finding-status: {status}")
        store = self.repository.load()
        item = next(
            (entry for entry in store.get("findings", []) if entry.get("id") == finding_id), None
        )
        if item is None:
            raise KeyError(finding_id)
        previous = item.get("status", "open")
        now = _now()
        item["status"] = status
        if assignee is not None:
            item["assignee"] = assignee or None
        if note is not None:
            item["resolution_note"] = note or None
        item["resolved_at"] = now if status in {"resolved", "dismissed"} else None
        store.setdefault("history", []).append(
            self._event(
                finding_id,
                "status_changed",
                actor,
                now,
                from_status=previous,
                to_status=status,
                note=note,
            )
        )
        store["revision"] = int(store.get("revision", 0)) + 1
        self.repository.save(store)
        return dict(item)

    def list(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        rule_id: str | None = None,
        object_id: str | None = None,
    ) -> dict[str, Any]:
        store = self.repository.load()
        findings = list(store.get("findings", []))
        if status:
            findings = [item for item in findings if item.get("status") == status]
        if severity:
            findings = [item for item in findings if item.get("severity") == severity]
        if rule_id:
            findings = [item for item in findings if item.get("rule_id") == rule_id]
        if object_id:
            findings = [item for item in findings if item.get("object_id") == object_id]
        by_status = Counter(item.get("status", "open") for item in findings)
        by_severity = Counter(item.get("severity", "warning") for item in findings)
        return {
            "schema": "crow-findings-list-v0.1",
            "revision": store.get("revision", 0),
            "finding_count": len(findings),
            "findings": findings,
            "summary": {
                "active": sum(by_status.get(value, 0) for value in ACTIVE_FINDING_STATUSES),
                "by_status": {
                    value: by_status.get(value, 0) for value in sorted(VALID_FINDING_STATUSES)
                },
                "by_severity": {
                    value: by_severity.get(value, 0)
                    for value in ("critical", "error", "warning", "info")
                },
            },
            "sync": store.get("sync", {}),
        }

    def history(self, finding_id: str | None = None) -> dict[str, Any]:
        events = self.repository.load().get("history", [])
        if finding_id:
            events = [event for event in events if event.get("finding_id") == finding_id]
        return {"schema": "crow-finding-history-v0.1", "event_count": len(events), "events": events}

    def csv_export(self, **filters: Any) -> str:
        findings = self.list(**filters)["findings"]
        stream = io.StringIO()
        columns = [
            "id",
            "status",
            "severity",
            "confidence",
            "rule_id",
            "rule_version",
            "object_id",
            "title",
            "message",
            "recommendation",
            "assignee",
            "first_seen_at",
            "last_seen_at",
            "resolved_at",
            "occurrence_count",
            "evidence_ids",
            "related_object_ids",
            "resolution_note",
        ]
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for item in findings:
            row = dict(item)
            row["evidence_ids"] = ";".join(item.get("evidence_ids", ()))
            row["related_object_ids"] = ";".join(item.get("related_object_ids", ()))
            writer.writerow(row)
        return stream.getvalue()

    @staticmethod
    def _event(
        finding_id: str, action: str, actor: str, timestamp: str, **details: Any
    ) -> dict[str, Any]:
        return {
            "finding_id": finding_id,
            "action": action,
            "actor": actor,
            "timestamp": timestamp,
            **{key: value for key, value in details.items() if value is not None},
        }
