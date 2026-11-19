"""Nyckelloggens återlämningssätt och besiktningens huvudnyckel i synkkontraktet."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from crow_ovk_field import KeyLog
from crow_ovk_module.ovk_field_surface import _field_data_to_payload, _validated_payload

_RECEIVED = "2026-11-19T08:00:00Z"
_RETURNED = "2026-11-19T15:30:00Z"


def _payload(key: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "inspection_id": "insp-1",
        "units": [{"unit_id": "u1", "number": "1001", "kind": "apartment", "key": key}],
        **extra,
    }


def _key(**changes: Any) -> dict[str, Any]:
    return {
        "received": True,
        "received_at": _RECEIVED,
        "returned": True,
        "returned_at": _RETURNED,
        "master_key_used": False,
        "master_key_note": "",
        **changes,
    }


@pytest.mark.parametrize("method", ["hand", "mailbox"])
def test_return_method_round_trips(method: str) -> None:
    data = _validated_payload(_payload(_key(returned_method=method)))
    assert data.units[0].key is not None
    assert data.units[0].key.returned_method == method
    assert _field_data_to_payload(data)["units"][0]["key"]["returned_method"] == method


def test_key_without_return_method_serializes_as_before() -> None:
    data = _validated_payload(_payload(_key()))
    stored = _field_data_to_payload(data)
    assert "returned_method" not in stored["units"][0]["key"]
    assert "master_key" not in stored


def test_return_method_is_validated() -> None:
    with pytest.raises(ValueError, match="unsupported key return method"):
        KeyLog(
            received=True,
            received_at=_RECEIVED,
            returned=True,
            returned_at=_RETURNED,
            returned_method="fönster",
        )
    with pytest.raises(ValueError, match="requires a returned key"):
        KeyLog(received=True, received_at=_RECEIVED, returned_method="hand")


def test_inspection_master_key_round_trips() -> None:
    master = _key(returned=False, returned_at=None)
    data = _validated_payload(_payload(master_key=master))
    assert data.master_key is not None
    assert data.master_key.received_at == _RECEIVED
    assert data.master_key.returned is False
    stored = _field_data_to_payload(data)
    assert stored["master_key"]["received"] is True
    assert _validated_payload(stored).master_key == data.master_key


def test_inspection_master_key_rejects_per_unit_master_note() -> None:
    master = _key(master_key_used=True, master_key_note="lånad av vaktmästare")
    with pytest.raises(HTTPException) as caught:
        _validated_payload(_payload(master_key=master))
    assert caught.value.status_code == 422


def test_null_return_method_and_null_master_key_are_treated_as_absent() -> None:
    data = _validated_payload(_payload(_key(returned_method=None), master_key=None))
    assert data.master_key is None
    assert data.units[0].key is not None
    assert data.units[0].key.returned_method == ""


@pytest.mark.parametrize("master_key", ["hand", 1, ["x"]])
def test_master_key_must_be_an_object(master_key: Any) -> None:
    with pytest.raises(HTTPException) as caught:
        _validated_payload(_payload(master_key=master_key))
    assert caught.value.status_code == 422
