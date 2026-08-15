from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from crow_ovk import (
    CheckStatus,
    FindingSeverity,
    OvkCheckpoint,
    OvkFinding,
    OvkObject,
    VentilationSystemRef,
)
from crow_ovk_besiktningsbevakning import (
    WatchSource,
    WatchStatus,
    build_watchlist,
    watchlist_to_payload,
)
from crow_ovk_intyg import (
    Behorighet,
    Byggnadsagare,
    Funktionskontrollant,
    OvkIntyg,
    OvkIntygRepository,
    build_intyg,
)
from crow_ovk_pricing import BuildingCategory, InspectionType
from crow_ovk_workflow import (
    OvkReinspectionRepository,
    OvkReviewDecision,
    OvkWorkflowRecord,
    ReviewStatus,
    build_record,
    open_case,
)
from crow_workbench.shell import create_app

_TODAY = date(2026, 8, 10)
_KONTROLLANT = Funktionskontrollant(
    name="Stina Kontrollant",
    behorighet=Behorighet.K,
    certification_body="RISE",
    certificate_number="K-12345",
)
_AGARE = Byggnadsagare(name="Brf Berghällen")


def _record(
    *,
    inspection_id: str = "ovk-001",
    building_id: str = "building-1",
    approved: bool = True,
) -> OvkWorkflowRecord:
    findings: tuple[OvkFinding, ...] = ()
    if not approved:
        findings = (
            OvkFinding(
                finding_id="f1",
                description="Otillräckligt flöde",
                severity=FindingSeverity.MAJOR,
                system_id="FTX01",
            ),
        )
    return build_record(
        inspection_id=inspection_id,
        ovk_object=OvkObject(
            object_id="object-" + building_id,
            project_id="p1",
            building_id=building_id,
            name="Objekt " + building_id,
        ),
        systems=(VentilationSystemRef("FTX01", "FTX", "System FTX01"),),
        checkpoints=(
            OvkCheckpoint(
                checkpoint_id="cp1",
                label="Drift och funktion",
                status=CheckStatus.PASS if approved else CheckStatus.FAIL,
                system_id="FTX01",
            ),
        ),
        findings=findings,
        review=(
            OvkReviewDecision(
                observation_id="o1",
                source_text="B1 FTX01 34 l/s 40 l/s",
                evidence_ref="doc#page=1",
                reason="unlabelled_airflow_value",
                status=ReviewStatus.ACCEPTED,
                reviewer="tester",
            ),
        ),
    )


def _intyg(
    *,
    intyg_id: str = "intyg-001",
    inspection_id: str = "ovk-001",
    building_id: str = "building-1",
    approved: bool = True,
    inspection_date: date = date(2026, 8, 1),
    category: BuildingCategory = BuildingCategory.FLERBOSTADSHUS,
) -> OvkIntyg:
    return build_intyg(
        intyg_id=intyg_id,
        record=_record(inspection_id=inspection_id, building_id=building_id, approved=approved),
        fastighetsbeteckning="Berghällen 1:2",
        byggnadsagare=_AGARE,
        funktionskontrollant=_KONTROLLANT,
        inspection_type=InspectionType.ATERKOMMANDE,
        inspection_date=inspection_date,
        building_category=category,
    )


def test_upcoming_deadline_far_away_is_ok_and_carries_intyg_basis() -> None:
    watchlist = build_watchlist(project_id="p1", intyg=(_intyg(),), cases=(), today=_TODAY)
    item = watchlist.items[0]
    assert item.status is WatchStatus.OK
    assert item.source is WatchSource.INTYG
    assert item.due_date == date(2029, 8, 1)
    assert item.days_until == (date(2029, 8, 1) - _TODAY).days
    assert "BFS 2011:16" in item.basis


def test_deadline_inside_window_is_reminder_and_past_is_overdue() -> None:
    reminder = build_watchlist(
        project_id="p1",
        intyg=(_intyg(inspection_date=date(2023, 12, 1)),),
        cases=(),
        today=_TODAY,
    ).items[0]
    assert reminder.status is WatchStatus.PAMINNELSE
    overdue = build_watchlist(
        project_id="p1",
        intyg=(_intyg(inspection_date=date(2023, 6, 1)),),
        cases=(),
        today=_TODAY,
    ).items[0]
    assert overdue.status is WatchStatus.FORSENAD
    assert overdue.days_until is not None and overdue.days_until < 0


def test_ej_godkand_intyg_flags_ombesiktning_kravs() -> None:
    watchlist = build_watchlist(
        project_id="p1", intyg=(_intyg(approved=False),), cases=(), today=_TODAY
    )
    item = watchlist.items[0]
    assert item.status is WatchStatus.OMBESIKTNING_KRAVS
    assert item.due_date is None
    assert "ombesiktning" in item.basis
    assert watchlist.overdue_count == 1


def test_smahus_without_recurring_requirement_is_ingen_frist() -> None:
    watchlist = build_watchlist(
        project_id="p1",
        intyg=(_intyg(category=BuildingCategory.SMAHUS),),
        cases=(),
        today=_TODAY,
    )
    assert watchlist.items[0].status is WatchStatus.INGEN_FRIST


def test_latest_intyg_per_building_wins() -> None:
    older = _intyg(intyg_id="intyg-001", inspection_date=date(2023, 6, 1))
    newer = _intyg(intyg_id="intyg-002", inspection_id="ovk-002", inspection_date=date(2026, 8, 1))
    watchlist = build_watchlist(project_id="p1", intyg=(newer, older), cases=(), today=_TODAY)
    assert len(watchlist.items) == 1
    assert watchlist.items[0].ref_id == "intyg-002"
    assert watchlist.items[0].status is WatchStatus.OK


def test_open_case_deadline_is_watched_and_closed_cases_are_not() -> None:
    case = open_case(
        _record(approved=False),
        case_id="omb-001",
        opened_at="2026-08-01T10:00:00+00:00",
        deadline=date(2026, 9, 1),
    )
    watchlist = build_watchlist(project_id="p1", intyg=(), cases=(case,), today=_TODAY)
    item = watchlist.items[0]
    assert item.source is WatchSource.OMBESIKTNING
    assert item.status is WatchStatus.PAMINNELSE
    assert item.due_date == date(2026, 9, 1)
    assert "omb-001" in item.basis


def test_sort_order_puts_overdue_first() -> None:
    overdue = _intyg(
        intyg_id="intyg-a",
        building_id="building-a",
        inspection_id="ovk-a",
        inspection_date=date(2023, 6, 1),
    )
    ok = _intyg(
        intyg_id="intyg-b",
        building_id="building-b",
        inspection_id="ovk-b",
        inspection_date=date(2026, 8, 1),
    )
    watchlist = build_watchlist(project_id="p1", intyg=(ok, overdue), cases=(), today=_TODAY)
    assert [item.status for item in watchlist.items] == [
        WatchStatus.FORSENAD,
        WatchStatus.OK,
    ]


def test_payload_shape_and_counts() -> None:
    watchlist = build_watchlist(
        project_id="p1",
        intyg=(_intyg(inspection_date=date(2023, 6, 1)),),
        cases=(),
        today=_TODAY,
    )
    payload = watchlist_to_payload(watchlist)
    assert payload["schema_version"] == "crow-ovk-bevakning-v0.1"
    assert payload["overdue_count"] == 1
    assert payload["items"][0]["status"] == "forsenad"
    json.dumps(payload)


def test_watch_item_requires_written_basis() -> None:
    from crow_ovk_besiktningsbevakning import WatchItem

    with pytest.raises(ValueError, match="written basis"):
        WatchItem(
            project_id="p1",
            building_id="b1",
            object_name="Objekt",
            source=WatchSource.INTYG,
            ref_id="intyg-001",
            inspection_id="ovk-001",
            status=WatchStatus.OK,
            basis="   ",
        )


def _write_entitlements(root: Path) -> None:
    target = root / "config" / "customers" / "acme"
    target.mkdir(parents=True, exist_ok=True)
    (target / "entitlements.json").write_text(
        json.dumps(
            {
                "customer_id": "acme",
                "modules": [{"id": "ovk", "active": True}],
            }
        ),
        encoding="utf-8",
    )


def _client(tmp_path: Path, monkeypatch: MonkeyPatch) -> TestClient:
    monkeypatch.setenv("CROW_MODE", "local")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    _write_entitlements(tmp_path)
    return TestClient(create_app(tmp_path))


def test_surface_builds_watchlist_from_repositories(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    OvkIntygRepository(tmp_path).save(_intyg())
    case = open_case(
        _record(inspection_id="ovk-fail", building_id="building-2", approved=False),
        case_id="omb-001",
        opened_at="2026-08-01T10:00:00+00:00",
        deadline=date(2026, 7, 1),
    )
    OvkReinspectionRepository(tmp_path).save(case)
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/ovk/projects/p1/bevakning?today=2026-08-10")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["overdue_count"] == 1
    statuses = [item["status"] for item in payload["items"]]
    assert statuses == ["forsenad", "ok"]
    assert payload["items"][0]["source"] == "ombesiktning"

    invalid = client.get("/api/ovk/projects/p1/bevakning?today=igår")
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "INVALID_OVK_BEVAKNING"


def test_surface_empty_project_returns_empty_list(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.get("/api/ovk/projects/p1/bevakning?today=2026-08-10")
    assert response.status_code == 200
    assert response.json()["items"] == []
