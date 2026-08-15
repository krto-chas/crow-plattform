import csv
import io
from pathlib import Path

import pytest

from crow_reasoning import FindingRepository, FindingService


def evaluation(ids=("finding:a",), severity="error"):
    return {
        "schema": "crow-reasoning-rule-evaluation-v0.1",
        "findings": [
            {
                "id": finding_id,
                "rule_id": "r1",
                "rule_version": "1.0.0",
                "object_id": "o1",
                "severity": severity,
                "confidence": 0.9,
                "title": "Fel",
                "message": "Något saknas",
                "recommendation": "Åtgärda",
                "evidence_ids": ["e1"],
                "related_object_ids": [],
                "failed_requirements": [],
            }
            for finding_id in ids
        ],
    }


def test_synchronize_deduplicates_and_increments_occurrences(tmp_path: Path):
    service = FindingService(FindingRepository(tmp_path / "findings.json"))
    first = service.synchronize(evaluation())
    second = service.synchronize(evaluation())
    assert first["finding_count"] == 1
    assert second["finding_count"] == 1
    assert second["findings"][0]["occurrence_count"] == 2
    assert second["sync"]["unchanged"] == 1


def test_lifecycle_auto_resolve_and_reopen(tmp_path: Path):
    service = FindingService(FindingRepository(tmp_path / "findings.json"))
    service.synchronize(evaluation())
    service.update_status("finding:a", "acknowledged", actor="kristoffer", note="Granskas")
    resolved = service.synchronize(evaluation(ids=()))
    assert resolved["findings"][0]["status"] == "resolved"
    reopened = service.synchronize(evaluation())
    assert reopened["findings"][0]["status"] == "open"
    actions = [event["action"] for event in service.history("finding:a")["events"]]
    assert actions == ["created", "status_changed", "auto_resolved", "reopened"]


def test_filters_summary_and_csv(tmp_path: Path):
    service = FindingService(FindingRepository(tmp_path / "findings.json"))
    service.synchronize(evaluation(("finding:a", "finding:b")))
    service.update_status("finding:b", "dismissed", actor="reviewer", note="Ej relevant")
    active = service.list(status="open")
    assert active["finding_count"] == 1
    assert active["summary"]["active"] == 1
    rows = list(csv.DictReader(io.StringIO(service.csv_export(status="open"))))
    assert rows[0]["id"] == "finding:a"
    assert rows[0]["evidence_ids"] == "e1"


def test_invalid_status_and_missing_finding(tmp_path: Path):
    service = FindingService(FindingRepository(tmp_path / "findings.json"))
    with pytest.raises(ValueError):
        service.update_status("x", "banana", actor="reviewer")
    with pytest.raises(KeyError):
        service.update_status("x", "open", actor="reviewer")
