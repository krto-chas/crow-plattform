from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from crow_workbench.shell import create_app


def _write_entitlements(root: Path, modules: list[dict[str, object]]) -> None:
    target = root / "config" / "customers" / "acme"
    target.mkdir(parents=True, exist_ok=True)
    (target / "entitlements.json").write_text(
        json.dumps({"customer_id": "acme", "modules": modules}),
        encoding="utf-8",
    )


def _client(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    modules: list[dict[str, object]],
) -> TestClient:
    monkeypatch.setenv("CROW_MODE", "local")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    _write_entitlements(tmp_path, modules)
    return TestClient(create_app(tmp_path))


def _pressure_with_vent() -> list[dict[str, object]]:
    return [
        {"id": "vent", "active": True},
        {"id": "provtryckning", "active": True},
    ]


def _payload() -> dict[str, object]:
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


def test_pressure_test_api_requires_its_own_entitlement(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch, [{"id": "vent", "active": True}])
    response = client.post("/api/provtryckning/projects/p1/evaluate", json=_payload())
    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "MODULE_NOT_ACTIVE",
        "module": "provtryckning",
    }


def test_pressure_test_requires_vent_entitlement(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _client(
        tmp_path,
        monkeypatch,
        [{"id": "provtryckning", "active": True}],
    )
    response = client.post("/api/provtryckning/projects/p1/evaluate", json=_payload())
    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "MODULE_NOT_ACTIVE",
        "module": "provtryckning",
    }
    modules = client.get("/api/me/modules").json()["modules"]
    assert not any(module["id"] == "provtryckning" for module in modules)


def test_pressure_test_runs_when_both_entitlements_are_active(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch, _pressure_with_vent())
    response = client.post("/api/provtryckning/projects/p1/evaluate", json=_payload())
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass"
    assert payload["ready_for_protocol"] is True
    assert payload["tightness_class"] == "C"


def test_inferred_requirement_requires_confirmation(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch, _pressure_with_vent())
    body = _payload()
    body.update(
        {
            "pre_pour_inferred": True,
            "pre_pour_confirmed": False,
        }
    )
    response = client.post("/api/provtryckning/projects/p1/evaluate", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass"
    assert payload["ready_for_protocol"] is False
    inferred = [item for item in payload["provenance"] if item["origin"] == "inferred"]
    assert inferred[0]["requires_confirmation"] is True


def test_pressure_test_page_is_served(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch, _pressure_with_vent())
    response = client.get("/provtryckning")
    assert response.status_code == 200
    assert "Täthetsprovning" in response.text
    assert "STATED/INFERRED" in response.text
