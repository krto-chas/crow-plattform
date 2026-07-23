import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from crow_workbench.app import create_app


def client() -> TestClient:
    return TestClient(create_app(Path(tempfile.mkdtemp())))


def test_takeoff_endpoint_consolidates_and_prices() -> None:
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
    response = client().post("/api/projects/adhoc/takeoff", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["consolidated"]["line_count"] == 2
    assert payload["priced"]["priced_line_count"] == 2
    assert payload["priced"]["grand_total"] > 0
    assert payload["priced"]["currency"] == "SEK"


def test_takeoff_endpoint_requires_at_least_one_source() -> None:
    response = client().post("/api/projects/adhoc/takeoff", json={})
    assert response.status_code == 422
