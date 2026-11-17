from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_field.validation import validate_field_data
from crow_ovk_module.ovk_field_context_page import ovk_field_context_page_router
from crow_ovk_module.ovk_field_surface import _field_data_from_payload, _field_data_to_payload


def _payload() -> dict[str, Any]:
    return {
        "inspection_id": "i1",
        "units": [{"unit_id": "u1", "number": "1001", "kind": "apartment"}],
        "rooms": [{"room_id": "r1", "unit_id": "u1", "name": "Badrum"}],
        "visual_checks": [
            {
                "check_id": "v1",
                "unit_id": "u1",
                "room_id": "r1",
                "don": "yes",
                "clean": "dirty",
                "transfer": "no",
                "fresh": "yes",
            }
        ],
    }


def test_visual_checks_survive_server_round_trip() -> None:
    original = _payload()
    data = _field_data_from_payload(original)
    validate_field_data(data)
    serialized = _field_data_to_payload(data)
    assert serialized["visual_checks"] == original["visual_checks"]
    round_trip = _field_data_to_payload(_field_data_from_payload(serialized))
    assert round_trip["visual_checks"] == original["visual_checks"]


def test_legacy_payload_without_visual_checks_is_supported() -> None:
    payload = _payload()
    del payload["visual_checks"]
    data = _field_data_from_payload(payload)
    validate_field_data(data)
    assert _field_data_to_payload(data)["visual_checks"] == []


@pytest.mark.parametrize(
    "updates",
    [
        {"room_id": "unknown"},
        {"unit_id": "unknown"},
        {"don": "maybe"},
        {"don": "no", "clean": "dirty"},
        {"transfer": "yes", "fresh": "yes"},
    ],
)
def test_invalid_visual_checks_are_rejected(updates: dict[str, str]) -> None:
    payload = _payload()
    payload["visual_checks"][0].update(updates)
    with pytest.raises(ValueError):
        data = _field_data_from_payload(payload)
        validate_field_data(data)


def test_duplicate_visual_room_is_rejected() -> None:
    payload = _payload()
    payload["visual_checks"].append({**payload["visual_checks"][0], "check_id": "v2"})
    with pytest.raises(ValueError, match="duplicate room visual check"):
        validate_field_data(_field_data_from_payload(payload))


def test_two_pass_ui_persists_visual_answers() -> None:
    app = FastAPI()
    app.include_router(ovk_field_context_page_router())
    client = TestClient(app)
    page = client.get("/ovk/falt")
    script = client.get("/ovk/falt/app.js")
    assert page.status_code == 200
    assert script.status_code == 200
    assert "state.visual_checks.find(" in page.text
    assert "await persist();" in page.text
    assert "state.visual_checks" in script.text
    assert "visual_checks:draft.visual_checks||[]" in script.text
    assert "field_progress:draft.field_progress||{}" in script.text
    assert "state.field_progress[state.activeUnitId]" in page.text
    assert "ovkVisualAddRoom" in page.text
    assert "ovkVisualFinding" in page.text
