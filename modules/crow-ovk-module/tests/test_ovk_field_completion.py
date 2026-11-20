"""Avslutat fältarbete i synkkontraktet."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from crow_ovk_field import FieldInspectionData
from crow_ovk_module.ovk_field_surface import _field_data_to_payload, _validated_payload

_AT = "2026-11-20T15:30:00.000Z"


def _payload(**extra: Any) -> dict[str, Any]:
    return {
        "inspection_id": "insp-1",
        "units": [{"unit_id": "u1", "number": "1001", "kind": "apartment"}],
        **extra,
    }


def test_completion_round_trips_with_note() -> None:
    data = _validated_payload(
        _payload(field_work_completed_at=_AT, field_work_note="1002 ej tillgänglig.")
    )
    assert data.field_work_completed_at == _AT
    stored = _field_data_to_payload(data)
    assert stored["field_work_completed_at"] == _AT
    assert stored["field_work_note"] == "1002 ej tillgänglig."


def test_completion_without_note_omits_the_note() -> None:
    stored = _field_data_to_payload(_validated_payload(_payload(field_work_completed_at=_AT)))
    assert stored["field_work_completed_at"] == _AT
    assert "field_work_note" not in stored


def test_ongoing_inspection_serializes_as_before() -> None:
    stored = _field_data_to_payload(_validated_payload(_payload()))
    assert "field_work_completed_at" not in stored
    assert "field_work_note" not in stored
    explicit = _field_data_to_payload(
        _validated_payload(_payload(field_work_completed_at=None, field_work_note=""))
    )
    assert explicit == stored


def test_model_rejects_invalid_completion() -> None:
    with pytest.raises(ValueError, match="ISO timestamp"):
        FieldInspectionData(inspection_id="i1", field_work_completed_at="i går")
    with pytest.raises(ValueError, match="time zone"):
        FieldInspectionData(inspection_id="i1", field_work_completed_at="2026-11-20T15:30:00")
    with pytest.raises(ValueError, match="requires completed field work"):
        FieldInspectionData(inspection_id="i1", field_work_note="Begränsning")
    with pytest.raises(ValueError, match="too long"):
        FieldInspectionData(
            inspection_id="i1", field_work_completed_at=_AT, field_work_note="x" * 2001
        )


@pytest.mark.parametrize(
    "extra",
    [
        {"field_work_completed_at": "i går"},
        {"field_work_completed_at": "2026-11-20T15:30:00"},
        {"field_work_completed_at": 1763652600},
        {"field_work_completed_at": True},
        {"field_work_note": "Begränsning utan avslut"},
        {"field_work_completed_at": _AT, "field_work_note": 7},
        {"field_work_completed_at": _AT, "field_work_note": "   "},
        {"field_work_completed_at": _AT, "field_work_note": "x" * 2001},
    ],
)
def test_sync_rejects_invalid_completion(extra: dict[str, Any]) -> None:
    with pytest.raises(HTTPException) as caught:
        _validated_payload(_payload(**extra))
    assert caught.value.status_code == 422
