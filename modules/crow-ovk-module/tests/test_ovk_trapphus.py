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
from crow_ovk_field import FieldUnit, UnitKind
from crow_ovk_module.ovk_fastighet_surface import _validate_structure, ovk_fastighet_router
from crow_ovk_module.ovk_field_surface import ovk_field_router
from crow_ovk_module.ovk_inventory_promotion import plan_inventory_promotion
from crow_ovk_module.ovk_trapphus import display_number, trapphus_names
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
    # Strukturen fryses som den står i registret: numret är oförändrat, och
    # trapphuset följer med som egen uppgift som fältappen gör till port.
    expected = deepcopy(structure)
    assert frozen["building_structure"] == expected
    # Det fältappen läser ur den frysta strukturen finns kvar som förut:
    # tre listor, och på enheten id, nummer, typ och rum.
    assert {"units", "systems", "technical_spaces"} <= set(frozen["building_structure"])
    unit = frozen["building_structure"]["units"][0]
    assert (unit["unit_id"], unit["number"], unit["kind"]) == ("u1", "1203", "apartment")
    assert unit["rooms"] == [{"room_id": "r1", "name": "Kök"}]
    assert unit["trapphus_id"] == "t-a"
    assert frozen["building_structure"]["trapphus"][0]["namn"] == "A"
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


def test_shown_number_puts_the_trapphus_first() -> None:
    names = trapphus_names({"trapphus": [{"trapphus_id": "t-54", "namn": " 54 "}, "skräp"]})

    assert names == {"t-54": "54"}
    assert display_number({"number": " 1101 ", "trapphus_id": "t-54"}, names) == "54-1101"
    assert display_number({"number": "1101"}, names) == "1101"
    assert display_number({"number": "1101", "trapphus_id": "okant"}, names) == "1101"
    assert trapphus_names(None) == {}
    assert trapphus_names({"trapphus": "fel"}) == {}


def test_field_unit_shows_the_port_before_the_number() -> None:
    assert FieldUnit("u1", "ovk-1", "1101", port="54").display_number == "54-1101"
    assert FieldUnit("u1", "ovk-1", "1101").display_number == "1101"
    # En namngiven lokal visas med sitt namn, med eller utan port.
    named = FieldUnit("u2", "ovk-1", "0901", kind=UnitKind.PREMISES, label="Frisör", port="54")
    assert named.display_number == "Frisör"
    for port in (" 54", "54  A", "x" * 101, "5\u00074"):
        with pytest.raises(ValueError, match="port"):
            FieldUnit("u1", "ovk-1", "1101", port=port)


def _field_client(tmp_path: Path) -> TestClient:
    app = FastAPI()
    app.include_router(ovk_fastighet_router(tmp_path))
    app.include_router(ovk_field_router(tmp_path))
    return TestClient(app)


def test_field_sync_keeps_the_port_and_old_snapshots_are_unchanged(tmp_path: Path) -> None:
    client = _field_client(tmp_path)
    OvkWorkflowRepository(tmp_path).save(
        build_record(
            inspection_id="ovk-1",
            ovk_object=OvkObject("f1", "p1", "hus-a", "Eken 1:1"),
            systems=(VentilationSystemRef("LB01", "F", "LB01"),),
        )
    )
    sync = "/api/ovk/projects/p1/field/ovk-1/sync"
    units = [
        {"unit_id": "u1", "number": "1101", "kind": "apartment", "port": "54"},
        {"unit_id": "u2", "number": "1101", "kind": "apartment", "port": "56"},
        {"unit_id": "u3", "number": "1201", "kind": "apartment"},
    ]

    saved = client.put(sync, json={"inspection_id": "ovk-1", "units": units})

    assert saved.status_code == 200, saved.text
    stored = client.get(sync).json()["payload"]["units"]
    assert [unit.get("port") for unit in stored] == ["54", "56", None]
    # En enhet utan port får ingen nyckel alls, som före portar fanns.
    assert "port" not in stored[2]
    for bad in (7, " 54", "x" * 101):
        refused = client.put(
            sync, json={"inspection_id": "ovk-1", "units": [{**units[0], "port": bad}]}
        )
        assert refused.status_code == 422, bad


def test_promotion_places_field_units_by_their_port() -> None:
    inventory = _validate_structure(_structure())
    snapshot = {
        "units": [
            # Känd enhet; registret avgör vilket trapphus den hör till.
            {"unit_id": "u1", "number": "1001", "kind": "apartment", "port": "A"},
            # Ny i fält i port B.
            {"unit_id": "u7", "number": "1101", "kind": "apartment", "port": "b"},
            # Samma nummer som u2 (i B) men i port A är en annan lägenhet.
            {"unit_id": "u8", "number": "1002", "kind": "apartment", "port": "A"},
            # Utan port: läggs in utan trapphus.
            {"unit_id": "u10", "number": "1301", "kind": "apartment"},
        ],
        "rooms": [{"room_id": "r1", "unit_id": "u1", "name": "Kök"}],
        "measurements": [],
    }

    plan = plan_inventory_promotion(deepcopy(inventory), snapshot, {})

    assert plan["conflicts"] == []
    by_id = {unit["unit_id"]: unit for unit in plan["structure"]["units"]}
    assert by_id["u1"]["rooms"] == [{"room_id": "r1", "name": "Kök"}]
    assert (by_id["u7"]["number"], by_id["u7"]["trapphus_id"]) == ("1101", "t-b")
    assert (by_id["u8"]["number"], by_id["u8"]["trapphus_id"]) == ("1002", "t-a")
    assert "trapphus_id" not in by_id["u10"]
    assert plan["structure"]["trapphus"] == inventory["trapphus"]
    assert [(item["kind"], item["label"]) for item in plan["additions"]] == [
        ("room", "A-1001 / Kök"),
        ("unit", "b-1101"),
        ("unit", "A-1002"),
        ("unit", "1301"),
    ]
    assert _validate_structure(plan["structure"]) == plan["structure"]


def test_promotion_refuses_a_number_already_in_the_port_and_ambiguous_field_numbers() -> None:
    inventory = _validate_structure(_structure())
    snapshot = {
        "units": [
            # 1001 finns redan i trapphus A med annat ID.
            {"unit_id": "u9", "number": "1001", "kind": "apartment", "port": "A"},
            # Två fältenheter med samma nummer i samma port.
            {"unit_id": "u11", "number": "1401", "kind": "apartment", "port": "B"},
            {"unit_id": "u12", "number": "1401", "kind": "apartment", "port": "b"},
            # Samma nummer i två olika portar är inte tvetydigt.
            {"unit_id": "u13", "number": "1501", "kind": "apartment", "port": "A"},
            {"unit_id": "u14", "number": "1501", "kind": "apartment", "port": "B"},
        ],
        "rooms": [],
        "measurements": [],
    }

    plan = plan_inventory_promotion(deepcopy(inventory), snapshot, {})

    assert plan["conflicts"] == [
        "Enhet A-1001: numret finns med annat ID.",
        "Enhet B-1401: ogiltigt ID eller tvetydigt nummer.",
        "Enhet b-1401: ogiltigt ID eller tvetydigt nummer.",
    ]
    assert sorted(item["id"] for item in plan["additions"]) == ["u13", "u14"]


def test_port_added_in_the_field_is_proposed_as_a_new_trapphus() -> None:
    inventory = _validate_structure(_structure())
    snapshot = {
        "units": [
            {"unit_id": "u20", "number": "1001", "kind": "apartment", "port": "56"},
            {"unit_id": "u21", "number": "1002", "kind": "apartment", "port": " 56 "},
        ],
        "rooms": [],
        "measurements": [],
    }

    plan = plan_inventory_promotion(deepcopy(inventory), snapshot, {})
    again = plan_inventory_promotion(deepcopy(inventory), snapshot, {})

    added = plan["structure"]["trapphus"][2]
    assert (added["namn"], added["adress"]) == ("56", "")
    assert added["trapphus_id"].startswith("trapphus-")
    # Samma förslag varje gång, så att en granskad förhandsvisning går att tillämpa.
    assert again["structure"] == plan["structure"]
    assert [(item["kind"], item["label"]) for item in plan["additions"]] == [
        ("trapphus", "Port 56"),
        ("unit", "56-1001"),
        ("unit", "56-1002"),
    ]
    assert {
        unit["trapphus_id"]
        for unit in plan["structure"]["units"]
        if unit["unit_id"] in {"u20", "u21"}
    } == {added["trapphus_id"]}
    assert _validate_structure(plan["structure"]) == plan["structure"]
    # Ett trapphus föreslås inte om ingen av portens enheter förs över.
    blocked = {
        "units": [
            {"unit_id": "u30", "number": "1", "kind": "apartment", "port": "58"},
            {"unit_id": "u31", "number": "1", "kind": "apartment", "port": "58"},
        ],
        "rooms": [],
        "measurements": [],
    }
    assert "trapphus" not in {
        item["kind"]
        for item in plan_inventory_promotion(deepcopy(inventory), blocked, {})["additions"]
    }


def test_renamed_trapphus_is_found_through_the_names_the_inspection_froze() -> None:
    frozen = _validate_structure(_structure())
    renamed = _structure()
    renamed["trapphus"][0]["namn"] = "54"
    inventory = _validate_structure(renamed)
    snapshot = {
        "units": [
            {"unit_id": "u1", "number": "1001", "kind": "apartment", "port": "A"},
            {"unit_id": "u7", "number": "1101", "kind": "apartment", "port": "A"},
        ],
        "rooms": [{"room_id": "r1", "unit_id": "u1", "name": "Kök"}],
        "measurements": [],
    }

    plan = plan_inventory_promotion(deepcopy(inventory), snapshot, {}, frozen)

    # Den nya enheten hamnar i samma trapphus, fast det nu heter 54, och inget
    # nytt trapphus föreslås.
    assert plan["conflicts"] == []
    by_id = {unit["unit_id"]: unit for unit in plan["structure"]["units"]}
    assert by_id["u1"]["rooms"] == [{"room_id": "r1", "name": "Kök"}]
    assert (by_id["u7"]["number"], by_id["u7"]["trapphus_id"]) == ("1101", "t-a")
    assert [item["namn"] for item in plan["structure"]["trapphus"]] == ["54", "B"]
    assert _validate_structure(plan["structure"]) == plan["structure"]


def test_unit_in_a_removed_trapphus_is_left_out_not_added_loose() -> None:
    frozen = _validate_structure(_structure())
    reduced = _structure()
    del reduced["trapphus"][1]
    del reduced["units"][1]
    inventory = _validate_structure(reduced)
    snapshot = {
        "units": [{"unit_id": "u7", "number": "1101", "kind": "apartment", "port": "B"}],
        "rooms": [],
        "measurements": [],
    }

    plan = plan_inventory_promotion(deepcopy(inventory), snapshot, {}, frozen)

    assert plan["additions"] == []
    assert plan["conflicts"] == ["Enhet B-1101: trapphuset finns inte längre i registret."]


def test_frozen_inspection_synced_from_field_is_promoted_and_shown_with_port(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    client = _workbench_client(tmp_path, monkeypatch)
    property_url = "/api/ovk/projects/p1/fastighet/object-1"
    structure_url = property_url + "/byggnad/building-1/struktur"
    assert (
        client.put(
            property_url,
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
    structure: dict[str, Any] = {
        "trapphus": [{"trapphus_id": "t-a", "namn": "54", "adress": ""}],
        "units": [
            {
                "unit_id": "u1",
                "number": "1203",
                "kind": "apartment",
                "trapphus_id": "t-a",
                "rooms": [],
            }
        ],
        "systems": [{"system_id": "FTX01", "system_type": "FTX", "label": "LB01"}],
        "technical_spaces": [],
    }
    assert client.put(structure_url, json=structure).status_code == 200
    payload = _workflow_payload()
    payload["planning"] = {
        "inspector_id": "person-1",
        "planned_date": "2027-01-15",
        "inspection_type": "aterkommande",
    }
    assert client.put("/api/ovk/projects/p1/inspections/ovk-001", json=payload).status_code == 200
    # Trapphuset byter namn efter att besiktningen skapats.
    structure["trapphus"][0]["namn"] = "54A"
    assert client.put(structure_url, json=structure).status_code == 200
    synced = client.put(
        "/api/ovk/projects/p1/field/ovk-001/sync",
        json={
            "inspection_id": "ovk-001",
            "units": [
                {"unit_id": "u1", "number": "1203", "kind": "apartment", "port": "54"},
                {"unit_id": "u2", "number": "1204", "kind": "apartment", "port": "54"},
                {"unit_id": "u3", "number": "1203", "kind": "apartment", "port": "56"},
            ],
            "rooms": [{"room_id": "r1", "unit_id": "u1", "name": "Kök"}],
            "measurements": [],
        },
    )
    assert synced.status_code == 200, synced.text
    promotion = structure_url + "/aterforing/ovk-001"

    plan = client.post(promotion + "/preview", json={})

    assert plan.status_code == 200, plan.text
    assert plan.json()["conflicts"] == []
    assert [(item["kind"], item["label"]) for item in plan.json()["additions"]] == [
        ("room", "54-1203 / Kök"),
        ("unit", "54-1204"),
        ("trapphus", "Port 56"),
        ("unit", "56-1203"),
    ]
    applied = client.post(
        promotion + "/apply",
        json={"assignments": {}, "preview_token": plan.json()["preview_token"], "confirmed": True},
    )
    assert applied.status_code == 200, applied.text
    after = client.get(structure_url).json()
    assert [item["namn"] for item in after["trapphus"]] == ["54A", "56"]
    by_id = {unit["unit_id"]: unit for unit in after["units"]}
    assert by_id["u1"]["rooms"] == [{"room_id": "r1", "name": "Kök"}]
    assert by_id["u2"]["trapphus_id"] == "t-a"
    assert by_id["u3"]["trapphus_id"] == after["trapphus"][1]["trapphus_id"]
