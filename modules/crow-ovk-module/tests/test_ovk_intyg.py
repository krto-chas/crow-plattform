from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from crow_ovk import (
    CheckStatus,
    EvidenceOrigin,
    FindingSeverity,
    OvkCheckpoint,
    OvkFinding,
    OvkObject,
    VentilationSystemRef,
)
from crow_ovk_intyg import (
    Behorighet,
    Byggnadsagare,
    Funktionskontrollant,
    IntygResult,
    OvkIntyg,
    OvkIntygRepository,
    build_intyg,
    intyg_from_payload,
    intyg_html,
    intyg_to_payload,
)
from crow_ovk_pricing import BuildingCategory, InspectionType
from crow_ovk_workflow import (
    AggregatCoverage,
    AggregatStatus,
    BekraftelseRoll,
    InspectionCoverage,
    OvkReviewDecision,
    OvkWorkflowRecord,
    OvkWorkflowRepository,
    ReviewStatus,
    SystemForteckningBekraftelse,
    build_record,
)
from crow_workbench.shell import create_app

_KONTROLLANT = Funktionskontrollant(
    name="Stina Kontrollant",
    behorighet=Behorighet.K,
    certification_body="RISE",
    certificate_number="K-12345",
    certificate_valid_to=date(2028, 12, 31),
)
_AGARE = Byggnadsagare(name="Brf Berghällen")


def _record(
    *,
    checkpoint_status: CheckStatus = CheckStatus.PASS,
    findings: tuple[OvkFinding, ...] = (),
    review_status: ReviewStatus = ReviewStatus.ACCEPTED,
    systems: tuple[VentilationSystemRef, ...] = (
        VentilationSystemRef("FTX01", "FTX", "System FTX01"),
    ),
) -> OvkWorkflowRecord:
    return build_record(
        inspection_id="ovk-001",
        ovk_object=OvkObject(
            object_id="object-1",
            project_id="p1",
            building_id="building-1",
            name="Testobjekt",
            address="Bergvägen 1",
        ),
        systems=systems,
        checkpoints=(
            OvkCheckpoint(
                checkpoint_id="cp1",
                label="Drift och funktion",
                status=checkpoint_status,
                system_id=systems[0].system_id if systems else None,
            ),
        ),
        findings=findings,
        review=(
            OvkReviewDecision(
                observation_id="o1",
                source_text="B1 FTX01 34 l/s 40 l/s",
                evidence_ref="doc#page=1",
                reason="unlabelled_airflow_value",
                status=review_status,
                reviewer="tester",
            ),
        ),
        coverage=InspectionCoverage(
            inspection_id="ovk-001",
            aggregat=(
                AggregatCoverage(
                    aggregat_id="agg-1", label="FTX01", status=AggregatStatus.BESIKTIGAD
                ),
            ),
            system_list_confirmation=SystemForteckningBekraftelse(
                confirmed_by="Test Besiktningsman", role=BekraftelseRoll.BESIKTNINGSMAN
            ),
        ),
    )


def _build(
    record: OvkWorkflowRecord,
    *,
    building_category: BuildingCategory = BuildingCategory.FLERBOSTADSHUS,
) -> OvkIntyg:
    return build_intyg(
        intyg_id="intyg-001",
        record=record,
        fastighetsbeteckning="Berghällen 1:2",
        byggnadsagare=_AGARE,
        funktionskontrollant=_KONTROLLANT,
        inspection_type=InspectionType.ATERKOMMANDE,
        inspection_date=date(2026, 8, 1),
        building_category=building_category,
    )


def test_approved_record_yields_godkand_with_inferred_next_inspection() -> None:
    intyg = _build(_record())
    assert intyg.result is IntygResult.GODKAND
    assert intyg.systems[0].result is IntygResult.GODKAND
    next_inspection = intyg.next_inspection
    assert next_inspection.interval_years == 3
    assert next_inspection.due_date == date(2029, 8, 1)
    assert next_inspection.origin is EvidenceOrigin.INFERRED
    assert "BFS 2011:16" in next_inspection.basis
    assert "2026-08-01" in next_inspection.basis


def test_shortest_interval_wins_across_multiple_systems() -> None:
    record = _record(
        systems=(
            VentilationSystemRef("F01", "F", "Frånluft"),
            VentilationSystemRef("FTX01", "FTX", "Huvudsystem"),
        )
    )
    intyg = _build(record)
    assert intyg.next_inspection.interval_years == 3


def test_deficiencies_yield_ej_godkand_without_next_inspection() -> None:
    record = _record(
        checkpoint_status=CheckStatus.FAIL,
        findings=(
            OvkFinding(
                finding_id="f1",
                description="Otillräckligt frånluftsflöde",
                severity=FindingSeverity.MAJOR,
                system_id="FTX01",
            ),
        ),
    )
    intyg = _build(record)
    assert intyg.result is IntygResult.EJ_GODKAND
    assert intyg.systems[0].result is IntygResult.EJ_GODKAND
    assert intyg.next_inspection.due_date is None
    assert "ombesiktning" in intyg.next_inspection.basis


def test_smahus_has_no_recurring_deadline_but_written_basis() -> None:
    intyg = _build(_record(), building_category=BuildingCategory.SMAHUS)
    assert intyg.next_inspection.interval_years is None
    assert intyg.next_inspection.due_date is None
    assert intyg.next_inspection.basis


def test_pending_review_blocks_intyg() -> None:
    record = _record(review_status=ReviewStatus.PENDING)
    with pytest.raises(ValueError, match="protocol ready"):
        _build(record)


def test_payload_roundtrip_preserves_intyg() -> None:
    intyg = _build(_record())
    payload = intyg_to_payload(intyg)
    restored = intyg_from_payload(json.loads(json.dumps(payload)))
    assert restored == intyg


def test_repository_roundtrip_and_safe_identifiers(tmp_path: Path) -> None:
    repository = OvkIntygRepository(tmp_path)
    intyg = _build(_record())
    repository.save(intyg)
    loaded = repository.load("p1", "intyg-001")
    assert loaded == intyg
    assert repository.list("p1") == (intyg,)
    with pytest.raises(ValueError, match="invalid intyg_id"):
        repository.load("p1", "../intyg-001")


def test_anslag_html_contains_core_fields() -> None:
    html = intyg_html(_build(_record()))
    assert "OVK-INTYG" in html
    assert "Berghällen 1:2" in html
    assert "GODKÄND" in html
    assert "Stina Kontrollant" in html
    assert "2029-08-01" in html
    assert "härledd uppgift" in html


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


def _intyg_body() -> dict[str, object]:
    return {
        "intyg_id": "intyg-001",
        "fastighetsbeteckning": "Berghällen 1:2",
        "byggnadsagare_name": "Brf Berghällen",
        "inspection_type": "aterkommande",
        "building_category": "flerbostadshus",
        "inspection_date": "2026-08-01",
        "kontrollant_name": "Stina Kontrollant",
        "kontrollant_behorighet": "K",
        "kontrollant_certification_body": "RISE",
        "kontrollant_certificate_number": "K-12345",
    }


def test_surface_issues_intyg_and_serves_anslag(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    OvkWorkflowRepository(tmp_path).save(_record())
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/ovk/projects/p1/inspections/ovk-001/intyg", json=_intyg_body())
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["result"] == "godkand"
    assert payload["next_inspection"]["due_date"] == "2029-08-01"
    assert payload["next_inspection"]["origin"] == "inferred"

    listing = client.get("/api/ovk/projects/p1/intyg")
    assert listing.status_code == 200
    assert listing.json()["intyg"][0]["intyg_id"] == "intyg-001"

    anslag = client.get("/api/ovk/projects/p1/intyg/intyg-001/anslag")
    assert anslag.status_code == 200
    assert "OVK-INTYG" in anslag.text


def test_surface_blocks_intyg_when_workflow_not_ready(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    OvkWorkflowRepository(tmp_path).save(_record(review_status=ReviewStatus.PENDING))
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/ovk/projects/p1/inspections/ovk-001/intyg", json=_intyg_body())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OVK_INTYG_NOT_READY"


def test_surface_returns_404_for_unknown_inspection(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.post("/api/ovk/projects/p1/inspections/saknas/intyg", json=_intyg_body())
    assert response.status_code == 404
