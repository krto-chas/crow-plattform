from __future__ import annotations

import io
import json
from decimal import Decimal
from pathlib import Path

import openpyxl
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from crow_pressure_test.vent_bridge import candidate_from_riser_string, circular_duct_area
from crow_riser_model.models import RiserString
from crow_workbench.shell import create_app


def _enable_pressure_test(root: Path) -> None:
    target = root / "config" / "customers" / "acme"
    target.mkdir(parents=True, exist_ok=True)
    (target / "entitlements.json").write_text(
        json.dumps(
            {
                "customer_id": "acme",
                "modules": [{"id": "provtryckning", "active": True}],
            }
        ),
        encoding="utf-8",
    )


def _client(tmp_path: Path, monkeypatch: MonkeyPatch) -> TestClient:
    monkeypatch.setenv("CROW_MODE", "local")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    _enable_pressure_test(tmp_path)
    return TestClient(create_app(tmp_path))


def _evaluation_payload() -> dict[str, object]:
    return {
        "tightness_class": "C",
        "tightness_origin": "stated",
        "tightness_source_ref": "VVS-beskrivning s. 12",
        "pressure_pa": "400",
        "pressure_origin": "stated",
        "pressure_source_ref": "VVS-beskrivning s. 12",
        "duct_area_m2": "10",
        "measured_leakage_lps": "1",
    }


def test_circular_duct_area_is_derived_from_dimension_and_length() -> None:
    area = circular_duct_area("Ø160", Decimal("10"))
    assert area == Decimal("5.026548")


def test_riser_candidate_keeps_source_evidence() -> None:
    item = RiserString(
        apartment_id="L1",
        stairwell_id="A",
        kind="franluft",
        plan="11",
        dimension="Ø160",
        length_m=Decimal("10"),
        evidence={"document_id": "V-57-1", "origin": "stated"},
    )
    candidate = candidate_from_riser_string(item)
    assert candidate.duct_area_m2 == Decimal("5.026548")
    assert candidate.source == "riser_model"
    assert candidate.evidence["document_id"] == "V-57-1"


def test_vent_candidates_api_returns_area_and_evidence(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.post(
        "/api/provtryckning/projects/p1/vent-candidates",
        json={
            "strings": [
                {
                    "apartment_id": "L1",
                    "stairwell_id": "A",
                    "kind": "franluft",
                    "plan": "11",
                    "dimension": "Ø160",
                    "length_m": "10",
                    "evidence": {"document_id": "V-57-1"},
                }
            ]
        },
    )
    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate["duct_area_m2"] == "5.026548"
    assert candidate["evidence"]["document_id"] == "V-57-1"


def test_protocol_export_uses_evaluated_result(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.post(
        "/api/provtryckning/projects/p1/protocol.xlsx",
        json=_evaluation_payload(),
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    workbook = openpyxl.load_workbook(io.BytesIO(response.content), data_only=False)
    sheet = workbook["Provningsresultat"]
    assert sheet["B3"].value == "p1"
    assert sheet["B4"].value == "C"
    assert sheet["B10"].value == "PASS"
    provenance = workbook["Proveniens"]
    assert provenance["C2"].value == "STATED"


def test_protocol_export_blocks_unconfirmed_inference(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    payload = _evaluation_payload()
    payload.update({"pre_pour_inferred": True, "pre_pour_confirmed": False})
    response = client.post(
        "/api/provtryckning/projects/p1/protocol.xlsx",
        json=payload,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PRESSURE_TEST_NOT_PROTOCOL_READY"
