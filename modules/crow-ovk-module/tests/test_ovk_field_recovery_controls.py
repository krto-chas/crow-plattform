from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_module.ovk_field_context_page import ovk_field_context_page_router


def test_room_creation_and_premises_label_are_accessible() -> None:
    app = FastAPI()
    app.include_router(ovk_field_context_page_router())
    response = TestClient(app).get("/ovk/falt")
    assert response.status_code == 200
    page = response.text
    for element_id in (
        "ovkRoomName",
        "ovkRoomSave",
        "ovkPremisesName",
        "ovkPremisesSave",
    ):
        assert f'id="{element_id}"' in page
    assert "state.rooms.push(room);" in page
    assert "unit.label=name;" in page
    assert "await persist();" in page


def test_existing_inspection_opens_room_flow_without_reset() -> None:
    app = FastAPI()
    app.include_router(ovk_field_context_page_router())
    page = TestClient(app).get("/ovk/falt").text
    assert "const progress=(state.field_progress||{})[id];" in page
    assert "phase:'rooms';" in page
    assert "state.activeRoomId=progress.room_id;" in page
    assert "state.field_progress[state.activeUnitId]" in page
