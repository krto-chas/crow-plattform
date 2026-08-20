from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crow_entitlements.auth import UserRecord, hash_password, write_user
from crow_workbench.shell import create_app


def _enable_vent(root: Path, customer_id: str = "acme") -> None:
    target = root / "config" / "customers" / customer_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "entitlements.json").write_text(
        json.dumps({"customer_id": customer_id, "modules": [{"id": "vent", "active": True}]}),
        encoding="utf-8",
    )


def _quote_body() -> dict[str, object]:
    return {
        "takeoff": {
            "table_rows": [["T-125", "10", "m"]],
            "price_book": {
                "price_book_id": "pb-1",
                "labour_rate_per_hour": 500,
                "entries": [
                    {
                        "kind": "duct",
                        "code": "T",
                        "dimension": "Ø125",
                        "unit": "m",
                        "material_unit_price": 100,
                        "labour_hours_per_unit": 0.5,
                    }
                ],
            },
        },
        "quote": {
            "project_name": "Projekt A",
            "customer_name": "Kund AB",
            "quote_date": "2026-08-20",
            "validity_days": 30,
            "overhead_percent": "10",
            "risk_percent": "5",
            "profit_percent": "15",
        },
    }


def test_vent_product_workspace_serves_dashboard_and_quote_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    _enable_vent(tmp_path)
    client = TestClient(create_app(tmp_path))

    dashboard = client.get("/vent")
    dashboard_script = client.get("/vent/assets/dashboard.js")
    quote = client.get("/vent/offert")
    quote_script = client.get("/vent/assets/quote.js")

    assert dashboard.status_code == 200
    assert "Vent-arbetsyta" in dashboard.text
    assert "Ritningar &amp; system" in dashboard.text
    assert "/static/product.css" in dashboard.text
    assert dashboard_script.status_code == 200
    assert "geometry_checksums" in dashboard_script.text
    assert "/drawings/${enc(checksum)}/model" in dashboard_script.text
    assert quote.status_code == 200
    assert "Ritningskällor" in quote.text
    assert quote_script.status_code == 200
    assert "geometry_checksums" in quote_script.text


def test_vent_drawing_analysis_alias_is_entitlement_protected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    client = TestClient(create_app(tmp_path))

    response = client.get(f"/api/vent/projects/adhoc/drawings/{'0' * 64}/model")

    assert response.status_code == 403
    assert response.json()["detail"] == {"code": "MODULE_NOT_ACTIVE", "module": "vent"}


def test_vent_owned_takeoff_preserves_legacy_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    _enable_vent(tmp_path)
    client = TestClient(create_app(tmp_path))
    body = {"table_rows": [["T-125", "10", "m"]]}

    product = client.post("/api/vent/projects/adhoc/takeoff", json=body)
    legacy = client.post("/api/projects/adhoc/takeoff", json=body)

    assert product.status_code == 200
    assert legacy.status_code == 200
    assert product.json() == legacy.json()
    assert product.json()["consolidated"]["line_count"] == 1


def test_vent_registry_is_entitlement_protected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    client = TestClient(create_app(tmp_path))

    denied = client.get("/api/vent/registry")
    _enable_vent(tmp_path)
    allowed = client.get("/api/vent/registry")

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["version"] == "crow-vent-registry-v0.2"
    assert allowed.json()["count"] > 0


def test_vent_quote_works_in_session_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROW_AUTH_MODE", "session")
    monkeypatch.setenv("CROW_SESSION_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.delenv("CROW_SESSION_SECRET_FILE", raising=False)
    monkeypatch.setenv("CROW_COOKIE_SECURE", "false")
    monkeypatch.delenv("CROW_CUSTOMER_ID", raising=False)
    monkeypatch.delenv("CROW_USER_ID", raising=False)
    monkeypatch.delenv("CROW_ROLES", raising=False)
    _enable_vent(tmp_path)
    salt, digest = hash_password("correct-horse-battery-staple")
    write_user(
        tmp_path / "config",
        UserRecord(
            username="anna",
            customer_id="acme",
            roles=(),
            password_salt=salt,
            password_hash=digest,
        ),
    )
    client = TestClient(create_app(tmp_path))

    login = client.post(
        "/api/auth/login",
        json={"username": "anna", "password": "correct-horse-battery-staple"},
    )
    quote = client.post("/api/vent/projects/adhoc/quote", json=_quote_body())

    assert login.status_code == 200
    assert quote.status_code == 200
    assert quote.json()["ready_to_send"] is True
