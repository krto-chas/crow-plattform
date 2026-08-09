from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from crow_workbench.shell import create_app


def _client(tmp_path: Path, monkeypatch: object, *, entitled: bool) -> TestClient:
    monkeypatch.setenv("CROW_MODE", "local")  # type: ignore[attr-defined]
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")  # type: ignore[attr-defined]
    if entitled:
        target = tmp_path / "config" / "customers" / "acme"
        target.mkdir(parents=True, exist_ok=True)
        (target / "entitlements.json").write_text(
            json.dumps({"customer_id": "acme", "modules": [{"id": "vent", "active": True}]}),
            encoding="utf-8",
        )
    return TestClient(create_app(tmp_path))


def _body() -> dict[str, object]:
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
            "quote_date": "2026-08-08",
            "validity_days": 30,
            "overhead_percent": "10",
            "risk_percent": "5",
            "profit_percent": "15",
        },
    }


def test_quote_surface_is_available(tmp_path: Path, monkeypatch: object) -> None:
    client = _client(tmp_path, monkeypatch, entitled=True)
    response = client.get("/vent/offert")
    assert response.status_code == 200
    assert "Offert" in response.text
    assert "Skriv ut / PDF" in response.text


def test_quote_endpoint_is_entitlement_protected(tmp_path: Path, monkeypatch: object) -> None:
    client = _client(tmp_path, monkeypatch, entitled=False)
    response = client.post("/api/vent/projects/adhoc/quote", json=_body())
    assert response.status_code == 403


def test_quote_endpoint_reuses_takeoff_and_returns_decimal_strings(
    tmp_path: Path, monkeypatch: object
) -> None:
    client = _client(tmp_path, monkeypatch, entitled=True)
    response = client.post("/api/vent/projects/adhoc/quote", json=_body())
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "crow-vent-quote-v0.1"
    assert payload["source_price_book_id"] == "pb-1"
    assert isinstance(payload["base_cost"], str)
    assert isinstance(payload["offer_total"], str)
    assert payload["ready_to_send"] is True
