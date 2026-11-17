from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_module.ovk_field_context_page import ovk_field_context_page_router


def test_unit_stepper_shell() -> None:
    app = FastAPI()
    app.include_router(ovk_field_context_page_router())
    response = TestClient(app).get("/ovk/falt")
    assert response.status_code == 200
    page = response.text
    assert 'id="ovkStepCount"' in page
    assert 'id="ovkStepFill"' in page
    assert "Lägenhet och nycklar" in page
    for step in ("Välj anmärkning", "Kommentar", "Foto", "Slutkontroll"):
        assert step in page
    assert "body.ovk-unit-stepper{height:100dvh;overflow:hidden" in page
    assert "event.stopImmediatePropagation();" in page
    assert "originalOpenUnit(id);" in page
    assert "originalUpdateFooter(name);" in page
    assert "Slutför lägenhet" in page
