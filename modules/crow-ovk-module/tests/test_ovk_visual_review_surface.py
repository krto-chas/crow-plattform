from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_module.ovk_field_context_page import ovk_field_context_page_router


def test_guided_findings_and_final_review() -> None:
    app = FastAPI()
    app.include_router(ovk_field_context_page_router())
    response = TestClient(app).get("/ovk/falt")
    assert response.status_code == 200
    html = response.text
    assert 'id="ovkVisualFinding"' in html
    assert 'id="ovkVisualPhotoSlot"' in html
    assert 'id="ovkUnitReview"' in html
    assert 'id="note"' in html
    assert 'id="photo"' in html
    assert "const pending=state.measurements.filter" in html
    assert "pendingPoint(point)" in html
    assert "phase==='review'" in html
    assert "Slutför lägenhet" in html
