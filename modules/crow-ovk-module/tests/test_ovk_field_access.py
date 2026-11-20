"""Tillträde, återbesök och uttrycklig nyckelstatus i synkkontraktet."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from crow_ovk_field import FieldUnit, KeyLog
from crow_ovk_module.ovk_field_surface import _field_data_to_payload, _validated_payload

_AT = "2026-11-20T08:00:00Z"


def _payload(**unit: Any) -> dict[str, Any]:
    return {
        "inspection_id": "insp-1",
        "units": [{"unit_id": "u1", "number": "1001", "kind": "apartment", **unit}],
    }


def _key(**changes: Any) -> dict[str, Any]:
    return {
        "received": False,
        "received_at": None,
        "returned": False,
        "returned_at": None,
        "master_key_used": False,
        "master_key_note": "",
        **changes,
    }


@pytest.mark.parametrize("access", ["resident", "key", "master_key", "open"])
def test_access_round_trips(access: str) -> None:
    data = _validated_payload(_payload(access=access))
    assert data.units[0].access == access
    assert _field_data_to_payload(data)["units"][0]["access"] == access


def test_revisit_round_trips_together_with_bom() -> None:
    data = _validated_payload(
        _payload(status="bom", bom_at=_AT, bom_note="Ingen hemma", revisit_required=True)
    )
    assert data.units[0].revisit_required is True
    stored = _field_data_to_payload(data)["units"][0]
    assert stored["revisit_required"] is True
    assert stored["status"] == "bom"


def test_unused_fields_are_omitted_so_older_snapshots_serialize_unchanged() -> None:
    stored = _field_data_to_payload(_validated_payload(_payload(key=_key())))["units"][0]
    assert "access" not in stored
    assert "revisit_required" not in stored
    assert "state" not in stored["key"]
    explicit = _field_data_to_payload(
        _validated_payload(_payload(access="", revisit_required=False, key=_key(state="")))
    )["units"][0]
    assert explicit == stored


@pytest.mark.parametrize("state", ["missing", "not_applicable"])
def test_key_state_round_trips(state: str) -> None:
    data = _validated_payload(_payload(key=_key(state=state)))
    assert data.units[0].key is not None
    assert data.units[0].key.state == state
    assert _field_data_to_payload(data)["units"][0]["key"]["state"] == state


def test_a_missing_key_may_still_have_been_received() -> None:
    key = KeyLog(received=True, received_at=_AT, state="missing")
    assert key.state == "missing"


def test_model_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="unit access"):
        FieldUnit(unit_id="u1", inspection_id="i1", number="1001", access="fönster")
    with pytest.raises(ValueError, match="revisit_required must be a boolean"):
        FieldUnit(
            unit_id="u1",
            inspection_id="i1",
            number="1001",
            revisit_required="ja",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="unsupported key state"):
        KeyLog(state="borta")
    with pytest.raises(ValueError, match="not applicable cannot be received"):
        KeyLog(received=True, received_at=_AT, state="not_applicable")


@pytest.mark.parametrize(
    "unit",
    [
        {"access": "fönster"},
        {"revisit_required": "false"},
        {"revisit_required": 1},
        {"key": _key(state="borta")},
        {"key": _key(received=True, received_at=_AT, state="not_applicable")},
    ],
)
def test_sync_rejects_invalid_values(unit: dict[str, Any]) -> None:
    with pytest.raises(HTTPException) as caught:
        _validated_payload(_payload(**unit))
    assert caught.value.status_code == 422
