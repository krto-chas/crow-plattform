from __future__ import annotations

import json
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
from crow_ovk_workflow import (
    AggregatCoverage,
    AggregatStatus,
    BekraftelseRoll,
    CaseStatus,
    InspectionCoverage,
    OvkReinspectionRepository,
    OvkReviewDecision,
    OvkWorkflowRecord,
    OvkWorkflowRepository,
    RemedyState,
    ReviewStatus,
    SystemForteckningBekraftelse,
    build_record,
    case_from_payload,
    case_to_payload,
    claim_remedy,
    close_case,
    open_case,
    verify_item,
)
from crow_workbench.shell import create_app


def _record(
    *,
    inspection_id: str = "ovk-001",
    checkpoint_status: CheckStatus = CheckStatus.FAIL,
    findings: tuple[OvkFinding, ...] | None = None,
    review_status: ReviewStatus = ReviewStatus.ACCEPTED,
) -> OvkWorkflowRecord:
    if findings is None:
        findings = (
            OvkFinding(
                finding_id="f1",
                description="Otillräckligt frånluftsflöde i kök",
                severity=FindingSeverity.MAJOR,
                system_id="FTX01",
            ),
            OvkFinding(
                finding_id="f2",
                description="Smutsigt tilluftsdon",
                severity=FindingSeverity.MINOR,
                system_id="FTX01",
            ),
        )
    return build_record(
        inspection_id=inspection_id,
        ovk_object=OvkObject(
            object_id="object-1",
            project_id="p1",
            building_id="building-1",
            name="Testobjekt",
        ),
        systems=(VentilationSystemRef("FTX01", "FTX", "System FTX01"),),
        checkpoints=(
            OvkCheckpoint(
                checkpoint_id="cp1",
                label="Drift och funktion",
                status=checkpoint_status,
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


def _approved_reinspection(inspection_id: str = "ovk-001-omb") -> OvkWorkflowRecord:
    return _record(
        inspection_id=inspection_id,
        checkpoint_status=CheckStatus.PASS,
        findings=(),
    )


def test_open_case_snapshots_action_required_findings() -> None:
    case = open_case(_record(), case_id="omb-001", opened_at="2026-08-10T10:00:00+00:00")
    assert case.status is CaseStatus.OPEN
    assert case.source_inspection_id == "ovk-001"
    assert tuple(item.finding_id for item in case.items) == ("f1", "f2")
    assert all(item.state is RemedyState.OPEN for item in case.items)


def test_open_case_requires_deficiencies_conclusion() -> None:
    approved = _record(checkpoint_status=CheckStatus.PASS, findings=())
    with pytest.raises(ValueError, match="deficiencies"):
        open_case(approved, case_id="omb-001")


def test_open_case_requires_protocol_ready() -> None:
    pending = _record(review_status=ReviewStatus.PENDING)
    with pytest.raises(ValueError, match="protocol ready"):
        open_case(pending, case_id="omb-001")


def test_claim_remedy_is_stated_and_requires_note() -> None:
    case = open_case(_record(), case_id="omb-001")
    case = claim_remedy(case, "f1", note="Injustering utförd av driftentreprenör")
    item = case.items[0]
    assert item.state is RemedyState.REMEDY_CLAIMED
    assert item.remedy_origin is EvidenceOrigin.STATED
    with pytest.raises(ValueError, match="written note"):
        claim_remedy(case, "f2", note="   ")


def test_verify_item_records_reinspection_id_and_failed_can_be_reclaimed() -> None:
    case = open_case(_record(), case_id="omb-001")
    case = verify_item(case, "f1", verified=False, reinspection_id="ovk-001-omb")
    assert case.items[0].state is RemedyState.FAILED
    assert case.items[0].verified_in == "ovk-001-omb"
    case = claim_remedy(case, "f1", note="Åtgärdad på nytt")
    assert case.items[0].state is RemedyState.REMEDY_CLAIMED
    with pytest.raises(ValueError, match="reinspection_id"):
        verify_item(case, "f1", verified=True, reinspection_id="  ")


def test_case_becomes_ready_when_all_items_verified() -> None:
    case = open_case(_record(), case_id="omb-001")
    for finding_id in ("f1", "f2"):
        case = verify_item(case, finding_id, verified=True, reinspection_id="ovk-001-omb")
    assert case.status is CaseStatus.READY


def test_close_case_requires_approved_record_and_matching_verification() -> None:
    case = open_case(_record(), case_id="omb-001")
    approved = _approved_reinspection()
    with pytest.raises(ValueError, match="unverified"):
        close_case(case, reinspection_record=approved)
    case = verify_item(case, "f1", verified=True, reinspection_id="annan-id")
    case = verify_item(case, "f2", verified=True, reinspection_id="ovk-001-omb")
    with pytest.raises(ValueError, match="another reinspection"):
        close_case(case, reinspection_record=approved)
    case = verify_item(case, "f1", verified=True, reinspection_id="ovk-001-omb")
    with pytest.raises(ValueError, match="not approved"):
        close_case(case, reinspection_record=_record(inspection_id="ovk-001-omb"))
    closed = close_case(case, reinspection_record=approved)
    assert closed.status is CaseStatus.CLOSED
    assert closed.result_inspection_id == "ovk-001-omb"
    with pytest.raises(ValueError, match="is closed"):
        claim_remedy(closed, "f1", note="för sent")


def test_close_case_rejects_source_inspection_as_result() -> None:
    case = open_case(_record(), case_id="omb-001")
    for finding_id in ("f1", "f2"):
        case = verify_item(case, finding_id, verified=True, reinspection_id="ovk-001")
    approved_same_id = _record(
        inspection_id="ovk-001", checkpoint_status=CheckStatus.PASS, findings=()
    )
    with pytest.raises(ValueError, match="source inspection"):
        close_case(case, reinspection_record=approved_same_id)


def test_payload_and_repository_roundtrip(tmp_path: Path) -> None:
    case = open_case(_record(), case_id="omb-001", opened_at="2026-08-10T10:00:00+00:00")
    case = claim_remedy(case, "f1", note="Filter bytt", evidence_ref="foto#1")
    restored = case_from_payload(json.loads(json.dumps(case_to_payload(case))))
    assert restored == case
    repository = OvkReinspectionRepository(tmp_path)
    repository.save(case)
    assert repository.load("p1", "omb-001") == case
    assert repository.list("p1") == (case,)
    with pytest.raises(ValueError, match="invalid case_id"):
        repository.load("p1", "../omb-001")


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


def test_surface_full_chain_from_failed_inspection_to_closed_case(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    repository = OvkWorkflowRepository(tmp_path)
    repository.save(_record())
    repository.save(_approved_reinspection())
    client = _client(tmp_path, monkeypatch)

    opened = client.post(
        "/api/ovk/projects/p1/inspections/ovk-001/ombesiktning",
        json={"case_id": "omb-001", "deadline": "2026-10-01"},
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["status"] == "open"

    remedied = client.post(
        "/api/ovk/projects/p1/ombesiktning/omb-001/remedy",
        json={"finding_id": "f1", "note": "Injustering utförd"},
    )
    assert remedied.status_code == 200
    assert remedied.json()["items"][0]["state"] == "remedy_claimed"

    premature = client.post(
        "/api/ovk/projects/p1/ombesiktning/omb-001/close",
        json={"reinspection_id": "ovk-001-omb"},
    )
    assert premature.status_code == 409
    assert premature.json()["detail"]["code"] == "OVK_CASE_NOT_CLOSABLE"

    for finding_id in ("f1", "f2"):
        verified = client.post(
            "/api/ovk/projects/p1/ombesiktning/omb-001/verify",
            json={
                "finding_id": finding_id,
                "verified": True,
                "reinspection_id": "ovk-001-omb",
            },
        )
        assert verified.status_code == 200
    assert verified.json()["status"] == "ready"

    closed = client.post(
        "/api/ovk/projects/p1/ombesiktning/omb-001/close",
        json={"reinspection_id": "ovk-001-omb"},
    )
    assert closed.status_code == 200
    payload = closed.json()
    assert payload["status"] == "closed"
    assert payload["result_inspection_id"] == "ovk-001-omb"

    listing = client.get("/api/ovk/projects/p1/ombesiktning")
    assert listing.status_code == 200
    assert listing.json()["cases"][0]["status"] == "closed"


def test_surface_blocks_case_on_approved_inspection(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    OvkWorkflowRepository(tmp_path).save(_record(checkpoint_status=CheckStatus.PASS, findings=()))
    client = _client(tmp_path, monkeypatch)
    response = client.post(
        "/api/ovk/projects/p1/inspections/ovk-001/ombesiktning",
        json={"case_id": "omb-001"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OVK_CASE_NOT_OPENABLE"


def test_surface_returns_404_for_unknown_case(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.get("/api/ovk/projects/p1/ombesiktning/saknas")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "OVK_CASE_NOT_FOUND"
