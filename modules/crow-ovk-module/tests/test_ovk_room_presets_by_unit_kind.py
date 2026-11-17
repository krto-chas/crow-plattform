from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_module.ovk_field_context_page import ovk_field_context_page_router


def test_room_presets_follow_selected_unit_kind() -> None:
    app = FastAPI()
    app.include_router(ovk_field_context_page_router())
    response = TestClient(app).get("/ovk/falt/app.js")
    assert response.status_code == 200
    script = response.text
    assert "unit.kind==='premises'" in script
    assert "function roomPresets(){return isCommercial()?ROOMS_COMMERCIAL:ROOMS}" in script
    assert "const ROOMS = ['Kök', 'Badrum'" in script
    assert "const ROOMS_COMMERCIAL = ['Kontor', 'Vilorum'" in script
