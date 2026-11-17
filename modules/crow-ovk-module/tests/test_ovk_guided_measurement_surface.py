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
    assert 'id="ovkMeasureNav"' in page
    assert 'id="ovkMeasurePrev"' in page
    assert 'id="ovkMeasureNext"' in page
    assert 'id="ovkNextRoom"' in page
    assert "measurementRoomId !== roomId" in page
    assert "ovk-measure-hidden" in page
    assert "state.activeRoomId = rooms[index + 1].room_id;" in page
    assert "await persist();" in page
    assert ".ovk-measure-nav[hidden]" in page
