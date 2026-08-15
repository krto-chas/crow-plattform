from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from crow_workbench.shell import create_app


def _enable_vent(root: Path, customer_id: str = "acme") -> None:
    target = root / "config" / "customers" / customer_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "entitlements.json").write_text(
        json.dumps({"customer_id": customer_id, "modules": [{"id": "vent", "active": True}]}),
        encoding="utf-8",
    )


def test_vent_page_is_served_from_product_route(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    client = TestClient(create_app(tmp_path))
    response = client.get("/vent")
    assert response.status_code == 200
    assert "Mängdning & kalkyl" in response.text
    assert "/api/vent/projects/" in response.text


def test_vent_takeoff_alias_is_denied_without_entitlement(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    client = TestClient(create_app(tmp_path))
    response = client.post(
        "/api/vent/projects/adhoc/takeoff",
        json={"table_rows": [["T-125", "10", "m"]]},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == {"code": "MODULE_NOT_ACTIVE", "module": "vent"}


def test_vent_takeoff_alias_reuses_existing_pipeline(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    _enable_vent(tmp_path)
    client = TestClient(create_app(tmp_path))
    response = client.post(
        "/api/vent/projects/adhoc/takeoff",
        json={"table_rows": [["T-125", "10", "m"]]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["consolidated"]["line_count"] == 1


def test_vent_surface_exposes_csv_action(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    _enable_vent(tmp_path)
    client = TestClient(create_app(tmp_path))
    response = client.get("/vent")
    assert response.status_code == 200
    assert "Exportera CSV" in response.text
