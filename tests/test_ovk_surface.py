from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_workbench.ovk_surface import ovk_router


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(ovk_router())
    return TestClient(app)


def test_ovk_page_is_available() -> None:
    response = make_client().get("/ovk")
    assert response.status_code == 200
    assert "OVK" in response.text
    assert "Review-kö" in response.text


def test_import_preview_maps_explicit_evidence_and_keeps_review() -> None:
    response = make_client().post(
        "/api/ovk/projects/p1/import-preview",
        json={
            "observations": [
                {
                    "text": "System FTX01, B1 uppmätt 34,5 l/s, projekterat 40 l/s",
                    "document_id": "ovk-2025",
                    "page_number": 2,
                },
                {
                    "text": "Anmärkning: Filter i FTX02 är smutsigt",
                    "document_id": "ovk-2025",
                    "page_number": 3,
                },
                {
                    "text": "B1 FTX03 34 l/s 40 l/s",
                    "document_id": "ovk-2025",
                    "page_number": 4,
                },
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert [item["system_id"] for item in payload["systems"]] == ["FTX01", "FTX02", "FTX03"]
    assert payload["measurements"][0]["measured_value"] == "34.5"
    assert payload["measurements"][0]["designed_value"] == "40"
    assert payload["measurements"][0]["origin"] == "stated"
    assert payload["findings"][0]["description"] == "Filter i FTX02 är smutsigt"
    assert payload["review"][0]["reason"] == "unlabelled_airflow_value"
    assert "ovk-2025#page=4" in payload["review"][0]["evidence_ref"]


def test_import_preview_rejects_empty_input() -> None:
    response = make_client().post(
        "/api/ovk/projects/p1/import-preview",
        json={"observations": []},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_OVK_IMPORT"
