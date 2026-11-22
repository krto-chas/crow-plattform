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
from pytest import MonkeyPatch
from test_ovk_workflow import _client as _workbench_client
from test_ovk_workflow import _workflow_payload

from crow_ovk import OvkObject, VentilationSystemRef
from crow_ovk_module.ovk_fastighet_surface import _validate_structure, ovk_fastighet_router
from crow_ovk_module.ovk_field_surface import ovk_field_router
from crow_ovk_module.ovk_inventory_promotion import plan_inventory_promotion
from crow_ovk_module.ovk_trapphus import (
    display_number,
    split_display_number,
    structure_for_inspection,
    trapphus_names,
)
from crow_ovk_workflow import OvkWorkflowRepository, build_record

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


# Revisionen för strukturen nedan, uträknad med koden före trapphus (78d6bd7).
_REVISION_BEFORE_TRAPPHUS = "fc1657d3a59da9f0c0788cf7f98849ebd72d7c9767ccbbaf09bd974d0cff6a1a"


def test_structure_without_trapphus_is_stored_as_before(tmp_path: Path) -> None:
    client = _client(tmp_path)
    structure = {
        "units": [
            {
                "unit_id": "u1",
                "number": "1001",
                "kind": "apartment",
                "rooms": [
                    {
                        "room_id": "r1",
                        "name": "Kök",
                        "measurement_points": [
                            {
                                "point_id": "p1",
                                "label": "FL01",
                                "point_type": "franluftsdon",
                                "system_id": "LB01",
                                "designed_value": "15",
                            }
                        ],
                    }
                ],
            },
            {"unit_id": "u3", "number": "0901", "kind": "premises", "label": "Frisör"},
        ],
        "systems": [{"system_id": "LB01", "system_type": "F", "label": "LB01"}],
        "technical_spaces": [{"space_id": "s1", "label": "Fläktrum", "system_id": "LB01"}],
    }

    for payload in (structure, {**structure, "trapphus": []}):
        saved = client.put(URL, json=payload)

        # Ingen ny nyckel på någon nivå, och samma revision som före trapphus fanns.
        assert set(saved.json()) == {"units", "systems", "technical_spaces"}
        assert all("trapphus_id" not in unit for unit in saved.json()["units"])
        assert saved.headers["X-OVK-Inventory-Revision"] == _REVISION_BEFORE_TRAPPHUS


def test_null_means_no_trapphus() -> None:
    structure = _structure()
    structure["units"][0]["trapphus_id"] = None

    assert "trapphus_id" not in _validate_structure(structure)["units"][0]


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


def test_promotion_route_works_on_a_stored_structure_with_trapphus(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(ovk_fastighet_router(tmp_path))
    app.include_router(ovk_field_router(tmp_path))
    client = TestClient(app)
    assert (
        client.put(
            PROPERTY_URL,
            json={
                "fastighetsbeteckning": "Eken 1:1",
                "byggnader": [{"byggnad_id": "hus-a", "internt_namn": "Gathus"}],
            },
        ).status_code
        == 200
    )
    OvkWorkflowRepository(tmp_path).save(
        build_record(
            inspection_id="ovk-1",
            ovk_object=OvkObject("f1", "p1", "hus-a", "Eken 1:1"),
            systems=(VentilationSystemRef("LB01", "F", "LB01"),),
        )
    )
    stored = client.put(URL, json=_structure()).json()
    synced = client.put(
        "/api/ovk/projects/p1/field/ovk-1/sync",
        json={
            "inspection_id": "ovk-1",
            "units": [
                {"unit_id": "u1", "number": "1001", "kind": "apartment"},
                {"unit_id": "u9", "number": "1101", "kind": "apartment"},
            ],
            "rooms": [{"room_id": "r9", "unit_id": "u9", "name": "Kök"}],
            "measurements": [],
        },
    )
    assert synced.status_code == 200, synced.text
    promotion = URL + "/aterforing/ovk-1"

    plan = client.post(promotion + "/preview", json={})
    assert plan.status_code == 200, plan.text
    applied = client.post(
        promotion + "/apply",
        json={"assignments": {}, "preview_token": plan.json()["preview_token"], "confirmed": True},
    )

    assert applied.status_code == 200, applied.text
    after = client.get(URL).json()
    assert after["trapphus"] == stored["trapphus"]
    by_id = {unit["unit_id"]: unit for unit in after["units"]}
    assert by_id["u1"]["trapphus_id"] == "t-a"
    assert by_id["u2"]["trapphus_id"] == "t-b"
    # Enheten från fält saknar trapphus och placeras på kontoret.
    assert "trapphus_id" not in by_id["u9"]


def test_inspection_freezes_a_structure_with_trapphus_and_readers_still_work(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = _workbench_client(tmp_path, monkeypatch)
    assert (
        client.put(
            "/api/ovk/projects/p1/fastighet/object-1",
            json={
                "fastighetsbeteckning": "Björken 12",
                "byggnader": [{"byggnad_id": "building-1", "internt_namn": "Hus A"}],
            },
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/ovk/registry/besiktningsman/person-1",
            json={
                "namn": "Test Kontrollant",
                "behorighet": "K",
                "certifieringsorgan": "Test",
                "certnummer": "123",
                "giltig_till": "2030-12-31",
            },
        ).status_code
        == 200
    )
    structure_url = "/api/ovk/projects/p1/fastighet/object-1/byggnad/building-1/struktur"
    structure: dict[str, Any] = {
        "trapphus": [{"trapphus_id": "t-a", "namn": "A", "adress": "Storgatan 1A"}],
        "units": [
            {
                "unit_id": "u1",
                "number": "1203",
                "kind": "apartment",
                "trapphus_id": "t-a",
                "rooms": [{"room_id": "r1", "name": "Kök"}],
            }
        ],
        "systems": [{"system_id": "FTX01", "system_type": "FTX", "label": "LB01"}],
        "technical_spaces": [],
    }
    assert client.put(structure_url, json=structure).status_code == 200
    url = "/api/ovk/projects/p1/inspections/ovk-001"
    payload = _workflow_payload()
    payload["planning"] = {
        "inspector_id": "person-1",
        "planned_date": "2027-01-15",
        "inspection_type": "aterkommande",
    }

    assert client.put(url, json=payload).status_code == 200

    frozen = client.get(url).json()
    # Enheten fryses med visat nummer; registret behåller numret i trapphuset.
    expected = deepcopy(structure)
    expected["units"][0]["number"] = "A-1203"
    assert frozen["building_structure"] == expected
    assert client.get(structure_url).json()["units"][0]["number"] == "1203"
    # Det fältappen läser ur den frysta strukturen finns kvar som förut:
    # tre listor, och på enheten id, nummer, typ och rum.
    assert {"units", "systems", "technical_spaces"} <= set(frozen["building_structure"])
    unit = frozen["building_structure"]["units"][0]
    assert (unit["unit_id"], unit["number"], unit["kind"]) == ("u1", "A-1203", "apartment")
    assert unit["rooms"] == [{"room_id": "r1", "name": "Kök"}]
    # Posten med frysta trapphus går att spara om (checksumman stämmer), och
    # ändringar i registret efteråt når inte den redan skapade besiktningen.
    assert client.put(url, json=frozen).status_code == 200
    assert (
        client.put(structure_url, json={**structure, "trapphus": [], "units": []}).status_code
        == 200
    )
    again = client.get(url).json()
    assert again["building_structure"] == expected
    assert again["building_structure_sha256"] == frozen["building_structure_sha256"]
    # Fältappens sida och översikten svarar för uppdraget.
    assert client.get("/api/ovk/projects/p1/inspections").status_code == 200
    assert client.get("/api/ovk/uppdrag").status_code == 200


def test_same_number_may_exist_in_two_trapphus_but_not_twice_in_one(tmp_path: Path) -> None:
    client = _client(tmp_path)
    structure = _structure()
    structure["units"][1]["number"] = "1001"

    assert client.put(URL, json=structure).status_code == 200

    structure["units"][1]["trapphus_id"] = "t-a"
    refused = client.put(URL, json=structure)
    assert refused.status_code == 422
    assert "duplicate unit number in trapphus" in refused.json()["detail"]["message"]
    # Blanktecken och skiftläge skiljer inte två nummer åt.
    structure["units"][1]["number"] = " 1001 "
    assert client.put(URL, json=structure).status_code == 422


@pytest.mark.parametrize(
    "change",
    [
        # En enhet utan trapphus heter redan som det visade numret.
        lambda s: s["units"][2].update(number="A-1001"),
        lambda s: s["units"][2].update(number="a-1001"),
        # Två trapphus ger samma visade nummer.
        lambda s: (
            s["trapphus"][1].update(namn="A-1"),
            s["units"][0].update(number="1-7"),
            s["units"][1].update(number="7"),
        ),
    ],
)
def test_shown_number_must_not_be_ambiguous(tmp_path: Path, change: Any) -> None:
    client = _client(tmp_path)
    structure = _structure()
    change(structure)

    refused = client.put(URL, json=structure)

    assert refused.status_code == 422
    assert "ambiguous unit number" in refused.json()["detail"]["message"]


def test_duplicate_numbers_without_trapphus_are_stored_as_before(tmp_path: Path) -> None:
    client = _client(tmp_path)
    structure = {
        "units": [
            {"unit_id": "u1", "number": "1001", "kind": "apartment"},
            {"unit_id": "u2", "number": "1001", "kind": "apartment"},
        ],
        "systems": [],
        "technical_spaces": [],
    }

    # Ingen ny regel för strukturer som inte använder trapphus.
    assert client.put(URL, json=structure).status_code == 200


def test_shown_number_is_composed_and_read_back() -> None:
    names = {"t-54": "54", "t-5": "5", "t-up": "Uppgång 2"}

    assert display_number({"number": " 1101 ", "trapphus_id": "t-54"}, names) == "54-1101"
    assert display_number({"number": "1101"}, names) == "1101"
    assert display_number({"number": "1101", "trapphus_id": "okant"}, names) == "1101"
    assert split_display_number("54-1101", names) == ("t-54", "1101")
    assert split_display_number("5-1101", names) == ("t-5", "1101")
    assert split_display_number("uppgång 2-1101", names) == ("t-up", "1101")
    # Utan träff, eller utan nummer efter namnet, hör numret inte till något trapphus.
    assert split_display_number("1101", names) == (None, "1101")
    assert split_display_number("56-1101", names) == (None, "56-1101")
    assert split_display_number("54-", names) == (None, "54-")
    assert split_display_number("541101", names) == (None, "541101")
    # Längsta namnet vinner.
    assert split_display_number("5-4-1", {"a": "5", "b": "5-4"}) == ("b", "1")


def test_structure_for_inspection_leaves_the_register_untouched() -> None:
    structure = _validate_structure(_structure())
    before = deepcopy(structure)

    frozen = structure_for_inspection(structure)

    assert structure == before
    assert [unit["number"] for unit in frozen["units"]] == ["A-1001", "B-1002", "0901"]
    assert frozen["trapphus"] == structure["trapphus"]
    assert trapphus_names(frozen) == {"t-a": "A", "t-b": "B"}
    # Utan trapphus lämnas strukturen precis som den är.
    plain = {"units": [{"unit_id": "u", "number": "1", "kind": "apartment"}], "systems": []}
    assert structure_for_inspection(plain) is plain
    assert structure_for_inspection({"trapphus": "fel", "units": []}) == {
        "trapphus": "fel",
        "units": [],
    }


def test_promotion_reads_shown_numbers_from_the_field() -> None:
    inventory = _validate_structure(_structure())
    snapshot = {
        "units": [
            # Känd enhet med visat nummer, som besiktningen frös den.
            {"unit_id": "u1", "number": "A-1001", "kind": "apartment"},
            # Känd enhet från en besiktning som skapades före trapphuset.
            {"unit_id": "u2", "number": "1002", "kind": "apartment"},
            # Ny i fält, skriven med port: hamnar i trapphus B.
            {"unit_id": "u7", "number": "B-1101", "kind": "apartment"},
            # Samma nummer som u2 men i trapphus A är en annan lägenhet.
            {"unit_id": "u8", "number": "A-1002", "kind": "apartment"},
            # Visat nummer som redan hör till u1.
            {"unit_id": "u9", "number": "a-1001", "kind": "apartment"},
            # Okänd port: läggs in utan trapphus, med numret som det skrevs.
            {"unit_id": "u10", "number": "56-1101", "kind": "apartment"},
        ],
        "rooms": [],
        "measurements": [],
    }

    plan = plan_inventory_promotion(deepcopy(inventory), snapshot, {})

    by_id = {unit["unit_id"]: unit for unit in plan["structure"]["units"]}
    assert by_id["u1"] == inventory["units"][0]
    assert by_id["u2"] == inventory["units"][1]
    assert (by_id["u7"]["number"], by_id["u7"]["trapphus_id"]) == ("1101", "t-b")
    assert (by_id["u8"]["number"], by_id["u8"]["trapphus_id"]) == ("1002", "t-a")
    assert "u9" not in by_id
    assert by_id["u10"]["number"] == "56-1101"
    assert "trapphus_id" not in by_id["u10"]
    # Två fältenheter delar det visade numret A-1001 (oavsett skiftläge) och
    # lämnas därför båda; u1 finns redan och ändras inte.
    assert [c for c in plan["conflicts"] if "tvetydigt nummer" in c] == [
        "Enhet A-1001: ogiltigt ID eller tvetydigt nummer.",
        "Enhet a-1001: ogiltigt ID eller tvetydigt nummer.",
    ]
    assert sorted(item["id"] for item in plan["additions"]) == ["u10", "u7", "u8"]
    assert _validate_structure(plan["structure"]) == plan["structure"]


def test_promotion_refuses_a_shown_number_that_belongs_to_another_unit() -> None:
    inventory = _validate_structure(_structure())
    snapshot = {
        "units": [{"unit_id": "u9", "number": "A-1001", "kind": "apartment"}],
        "rooms": [],
        "measurements": [],
    }

    plan = plan_inventory_promotion(deepcopy(inventory), snapshot, {})

    assert plan["additions"] == []
    assert plan["conflicts"] == ["Enhet A-1001: numret finns med annat ID."]
