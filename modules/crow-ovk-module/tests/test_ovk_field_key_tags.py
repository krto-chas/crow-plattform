"""Nyckelbrickans löpnummer i synkkontraktet."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from crow_ovk_field import KeyLog
from crow_ovk_module.ovk_field_surface import _field_data_to_payload, _validated_payload

_AT = "2026-11-21T07:30:00Z"


def _key(**changes: Any) -> dict[str, Any]:
    return {
        "received": True,
        "received_at": _AT,
        "returned": False,
        "returned_at": None,
        "master_key_used": False,
        "master_key_note": "",
        **changes,
    }


def _payload(*keys: dict[str, Any] | None, **extra: Any) -> dict[str, Any]:
    return {
        "inspection_id": "insp-1",
        "units": [
            {"unit_id": f"u{index}", "number": str(1001 + index), "kind": "apartment", "key": key}
            for index, key in enumerate(keys)
        ],
        **extra,
    }


def test_tags_round_trip_in_reception_order() -> None:
    data = _validated_payload(_payload(_key(tag=2), _key(tag=1), None))
    assert [unit.key.tag if unit.key else None for unit in data.units] == [2, 1, None]
    stored = _field_data_to_payload(data)["units"]
    assert [unit["key"]["tag"] if unit["key"] else None for unit in stored] == [2, 1, None]


def test_tag_is_kept_when_the_reception_is_undone() -> None:
    data = _validated_payload(_payload(_key(received=False, received_at=None, tag=4)))
    assert data.units[0].key is not None
    assert data.units[0].key.tag == 4


def test_keys_without_tag_serialize_as_before() -> None:
    stored = _field_data_to_payload(_validated_payload(_payload(_key())))["units"][0]["key"]
    assert "tag" not in stored
    explicit = _field_data_to_payload(_validated_payload(_payload(_key(tag=None))))
    assert explicit["units"][0]["key"] == stored


@pytest.mark.parametrize("tag", [0, -1, 1000, True, 1.5, "7"])
def test_model_rejects_invalid_tags(tag: Any) -> None:
    with pytest.raises(ValueError, match="key tag"):
        KeyLog(received=True, received_at=_AT, tag=tag)


@pytest.mark.parametrize("tag", [1, 999])
def test_model_accepts_the_whole_range(tag: int) -> None:
    assert KeyLog(received=True, received_at=_AT, tag=tag).tag == tag


@pytest.mark.parametrize(
    "payload",
    [
        _payload(_key(tag=0)),
        _payload(_key(tag=1000)),
        _payload(_key(tag="7")),
        _payload(_key(tag=True)),
        _payload(_key(tag=1.0)),
        # Två enheter får aldrig samma nummer.
        _payload(_key(tag=3), _key(tag=3)),
        # Huvudnyckeln hör till besiktningen och har ingen bricka.
        _payload(_key(tag=1), master_key=_key(tag=2)),
    ],
)
def test_sync_rejects_invalid_tags(payload: dict[str, Any]) -> None:
    with pytest.raises(HTTPException) as caught:
        _validated_payload(payload)
    assert caught.value.status_code == 422
