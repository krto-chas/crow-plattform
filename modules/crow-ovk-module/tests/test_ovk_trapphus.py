"""Trapphus i byggnadsregistret (D4c).

Trapphus är en egen lista i byggnaden och enheterna pekar på sitt trapphus.
Enhetslistan förblir platt, så att den frysta besiktningsstrukturen och
fältappen läser den som förut.
"""

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_module.ovk_fastighet_surface import _validate_structure, ovk_fastighet_router
from crow_ovk_module.ovk_inventory_promotion import inventory_revision, plan_inventory_promotion

PROPERTY_URL = "/api/ovk/projects/p1/fastighet/f1"
URL = PROPERTY_URL + "/byggnad/hus-a/struktur"


def _client(tmp_path: Path) -> TestClient:
    app = FastAPI()
    app.include_router(ovk_fastighet_router(tmp_path))
    client = TestClient(app)
    saved = client.put(
        PROPERTY_URL,
        json={
            "fastighetsbeteckning": "Eken 1:1",
            "byggnader": [{"byggnad_id": "hus-a", "internt_namn": "Gathus"}],
        },
    )
    assert saved.status_code == 200
    return client


def _structure() -> dict[str, Any]:
    return {
        "trapphus": [
            {"trapphus_id": "t-a", "namn": "A", "adress": "Storgatan 1A"},
            {"trapphus_id": "t-b", "namn": "B", "adress": "Storgatan 1B"},
        ],
        "units": [
            {"unit_id": "u1", "number": "1001", "kind": "apartment", "trapphus_id": "t-a"},
            {"unit_id": "u2", "number": "1002", "kind": "apartment", "trapphus_id": "t-b"},
            {"unit_id": "u3", "number": "0901", "kind": "premises", "label": "Frisör"},
        ],
        "systems": [{"system_id": "LB01", "system_type": "F", "label": "LB01"}],
        "technical_spaces": [],
    }


def test_trapphus_is_saved_and_units_point_at_it(tmp_path: Path) -> None:
    client = _client(tmp_path)

    saved = client.put(URL, json=_structure())

    assert saved.status_code == 200
    body = saved.json()
    assert body["trapphus"] == _structure()["trapphus"]
    assert [unit.get("trapphus_id") for unit in body["units"]] == ["t-a", "t-b", None]
    # En enhet utan trapphus har ingen nyckel alls, inte ett tomt värde.
    assert "trapphus_id" not in body["units"][2]
    assert client.get(URL).json() == body


def test_structure_without_trapphus_is_stored_as_before(tmp_path: Path) -> None:
    client = _client(tmp_path)
    structure = _structure()
    del structure["trapphus"]
    for unit in structure["units"]:
        unit.pop("trapphus_id", None)

    saved = client.put(URL, json={**structure, "trapphus": []})

    # Ingen ny nyckel, och därmed samma revision som före trapphus fanns.
    assert set(saved.json()) == {"units", "systems", "technical_spaces"}
    assert saved.headers["X-OVK-Inventory-Revision"] == inventory_revision(
        _validate_structure(structure)
    )


def test_trapphus_text_is_normalized() -> None:
    structure = _structure()
    structure["trapphus"][0] = {"trapphus_id": "t-a", "namn": "  Uppgång   A ", "adress": " x  1 "}

    result = _validate_structure(structure)

    assert result["trapphus"][0] == {"trapphus_id": "t-a", "namn": "Uppgång A", "adress": "x 1"}
    # Adressen är frivillig.
    del structure["trapphus"][1]["adress"]
    assert _validate_structure(structure)["trapphus"][1]["adress"] == ""


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s["units"][0].update(trapphus_id="okant"),
        lambda s: s["units"][0].update(trapphus_id=""),
        lambda s: s["units"][0].update(trapphus_id=7),
        lambda s: s["trapphus"][1].update(trapphus_id="t-a"),
        lambda s: s["trapphus"][1].update(namn=" a "),
        lambda s: s["trapphus"][0].update(namn="  "),
        lambda s: s["trapphus"][0].update(namn=None),
        lambda s: s["trapphus"][0].update(namn="A\u0007"),
        lambda s: s["trapphus"][0].update(namn="x" * 101),
        lambda s: s["trapphus"][0].update(adress=None),
        lambda s: s["trapphus"][0].update(adress="x" * 201),
        lambda s: s["trapphus"][0].update(trapphus_id="t a"),
        lambda s: s["trapphus"][0].update(trapphus_id="t" * 121),
        lambda s: s.update(trapphus={"t-a": "A"}),
        lambda s: s.update(trapphus=["A"]),
        lambda s: s.update(trapphus=[{"trapphus_id": f"t{i}", "namn": str(i)} for i in range(201)]),
    ],
)
def test_invalid_trapphus_is_refused_and_nothing_is_saved(tmp_path: Path, change: Any) -> None:
    client = _client(tmp_path)
    assert client.put(URL, json=_structure()).status_code == 200
    before = client.get(URL)
    structure = _structure()
    change(structure)

    refused = client.put(URL, json=structure)

    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "INVALID_OVK_STRUCTURE"
    after = client.get(URL)
    assert after.json() == before.json()
    assert after.headers["X-OVK-Inventory-Revision"] == before.headers["X-OVK-Inventory-Revision"]


def test_removing_a_trapphus_that_units_point_at_is_refused(tmp_path: Path) -> None:
    client = _client(tmp_path)
    structure = _structure()
    del structure["trapphus"][1]

    assert client.put(URL, json=structure).status_code == 422


def test_saving_trapphus_requires_the_current_revision(tmp_path: Path) -> None:
    client = _client(tmp_path)
    first = client.put(URL, json=_structure())
    stale = first.headers["X-OVK-Inventory-Revision"]
    changed = _structure()
    changed["trapphus"][0]["namn"] = "Uppgång A"
    assert (
        client.put(URL, json=changed, headers={"X-OVK-Inventory-Revision": stale}).status_code
        == 200
    )

    again = _structure()
    again["trapphus"][0]["namn"] = "Annat"
    conflict = client.put(URL, json=again, headers={"X-OVK-Inventory-Revision": stale})

    assert conflict.status_code == 409
    assert client.get(URL).json()["trapphus"][0]["namn"] == "Uppgång A"


def test_promotion_from_field_keeps_trapphus_and_adds_units_without_one() -> None:
    inventory = _validate_structure(_structure())
    snapshot = {
        "units": [
            {"unit_id": "u1", "number": "1001", "kind": "apartment"},
            {"unit_id": "u9", "number": "1101", "kind": "apartment"},
        ],
        "rooms": [{"room_id": "r9", "unit_id": "u9", "name": "Kök"}],
        "measurements": [],
    }

    plan = plan_inventory_promotion(deepcopy(inventory), snapshot, {})

    structure = plan["structure"]
    assert structure["trapphus"] == inventory["trapphus"]
    by_id = {unit["unit_id"]: unit for unit in structure["units"]}
    assert by_id["u1"]["trapphus_id"] == "t-a"
    assert "trapphus_id" not in by_id["u9"]
    # Resultatet är fortfarande en normaliserad struktur och går att spara.
    assert _validate_structure(structure) == structure
