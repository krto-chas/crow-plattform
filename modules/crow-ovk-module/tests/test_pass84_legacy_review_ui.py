from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_module.ovk_legacy_surface import ovk_legacy_router


def test_legacy_review_page_and_client_are_served(tmp_path) -> None:
    app = FastAPI()
    app.include_router(ovk_legacy_router(tmp_path))
    client = TestClient(app)

    page = client.get("/ovk/legacy")
    script = client.get("/ovk/legacy/app.js")

    assert page.status_code == 200
    assert "Importera äldre OVK-protokoll" in page.text
    assert 'id="commitAll"' in page.text
    assert script.status_code == 200
    assert "reviewedFacts" in script.text
    assert "reviewAccepted" in script.text
    assert "/api/ovk/legacy/commit" in script.text


def test_legacy_review_ui_does_not_auto_accept_ambiguous_rows(tmp_path) -> None:
    app = FastAPI()
    app.include_router(ovk_legacy_router(tmp_path))
    script = TestClient(app).get("/ovk/legacy/app.js").text

    assert "reviewAccepted:data.review.map(()=>false)" in script
    assert "Godkänd reviewpost saknar fält eller värde" in script
