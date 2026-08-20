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
    assert "Vent-arbetsyta" in response.text
    assert "Ritningar &amp; system" in response.text
    assert "Mängdning &amp; kalkyl" in response.text
    assert "/static/product.css" in response.text
    assert "/vent/assets/dashboard.js" in response.text


def test_vent_dashboard_script_connects_geometry_to_takeoff(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    _enable_vent(tmp_path)
    client = TestClient(create_app(tmp_path))
    response = client.get("/vent/assets/dashboard.js")
    assert response.status_code == 200
    assert "geometry_checksums" in response.text
    assert (
        "/api/vent/projects/${enc(state.projectId)}/drawings/${enc(checksum)}/model"
        in response.text
    )
    assert "/api/vent/projects/${enc(state.projectId)}/takeoff" in response.text


def test_shared_product_styles_are_served(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    client = TestClient(create_app(tmp_path))
    response = client.get("/static/product.css")
    assert response.status_code == 200
    assert ".product-shell" in response.text
    assert ".product-sidebar" in response.text


def test_vent_drawing_alias_is_denied_without_entitlement(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    client = TestClient(create_app(tmp_path))
    checksum = "0" * 64
    response = client.get(f"/api/vent/projects/adhoc/drawings/{checksum}/model")
    assert response.status_code == 403
    assert response.json()["detail"] == {"code": "MODULE_NOT_ACTIVE", "module": "vent"}


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
