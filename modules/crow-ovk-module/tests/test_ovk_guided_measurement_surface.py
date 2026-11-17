from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_module.ovk_field_context_page import ovk_field_context_page_router


def test_guided_measurement_controls() -> None:
    app = FastAPI()
    app.include_router(ovk_field_context_page_router())
    response = TestClient(app).get("/ovk/falt")
    assert response.status_code == 200
    page = response.text
    for control in ("ovkMeasureNav", "ovkMeasurePrev", "ovkMeasureNext", "ovkNextRoom"):
        assert f'id="{control}"' in page
    assert "phase='measure'" in page
    assert "selectRoom(roomIndex+1)" in page
    assert "phase='review'" in page
    assert "await persist();" in page
    assert ".ovk-measure-nav[hidden]" in page
