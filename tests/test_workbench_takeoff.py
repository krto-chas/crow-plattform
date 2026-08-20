import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crow_workbench.shell import create_app


def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    target = tmp_path / "config" / "customers" / "acme"
    target.mkdir(parents=True, exist_ok=True)
    (target / "entitlements.json").write_text(
        json.dumps({"customer_id": "acme", "modules": [{"id": "vent", "active": True}]}),
        encoding="utf-8",
    )
    return TestClient(create_app(tmp_path))


def test_takeoff_endpoint_consolidates_and_prices(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = {
        "table_rows": [["T-125", "132", "m"]],
        "text_segments": ["24 st TD1"],
        "price_book": {
            "labour_rate_per_hour": 520,
            "entries": [
                {
                    "kind": "duct",
                    "code": "T",
                    "dimension": "Ø125",
                    "unit": "m",
                    "material_unit_price": 89,
                    "labour_hours_per_unit": 0.35,
                },
                {
                    "kind": "component",
                    "code": "TD",
                    "dimension": "*",
                    "unit": "st",
                    "material_unit_price": 640,
                    "labour_hours_per_unit": 0.5,
                },
            ],
        },
    }
    response = client(tmp_path, monkeypatch).post("/api/projects/adhoc/takeoff", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["consolidated"]["line_count"] == 2
    assert payload["priced"]["priced_line_count"] == 2
    assert payload["priced"]["grand_total"] > 0
    assert payload["priced"]["currency"] == "SEK"


def test_takeoff_endpoint_requires_at_least_one_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = client(tmp_path, monkeypatch).post("/api/projects/adhoc/takeoff", json={})
    assert response.status_code == 422
