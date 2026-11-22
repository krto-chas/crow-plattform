from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_module.ovk_fastighet_surface import ovk_fastighet_router


def test_building_inventory_is_separate_and_validated(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(ovk_fastighet_router(tmp_path))
    client = TestClient(app)
    property_url = "/api/ovk/projects/p1/fastighet/f1"
    url = property_url + "/byggnad/hus-a/struktur"
    property_payload = {
        "fastighetsbeteckning": "Test 1:1",
        "byggnader": [{"byggnad_id": "hus-a", "internt_namn": "Hus A"}],
    }
    assert client.get(url).status_code == 404
    assert client.put(property_url, json=property_payload).status_code == 200
    assert client.get(url).json() == {"units": [], "systems": [], "technical_spaces": []}
    inventory = {
        "units": [
            {
                "unit_id": "u1",
                "number": "1203",
                "kind": "apartment",
                "rooms": [{"room_id": "r1", "name": "Badrum"}],
                "status": "passed",
            }
        ],
        "systems": [{"system_id": "LB01", "system_type": "FTX", "label": "Aggregat 1"}],
        "technical_spaces": [{"space_id": "s1", "label": "Fläktrum", "system_id": "LB01"}],
    }
    saved = client.put(url, json=inventory)
    assert saved.status_code == 200
    assert "status" not in saved.json()["units"][0]
    assert saved.json()["technical_spaces"][0]["kind"] == "unclassified"
    assert saved.json()["technical_spaces"][0]["location"] == ""
    assert client.get(url).json() == saved.json()
    assert client.put(property_url, json=property_payload).status_code == 200
    assert client.get(url).json() == saved.json()
    invalid = {**inventory, "systems": []}
    assert client.put(url, json=invalid).status_code == 422
    assert client.get(url).json() == saved.json()
    assert client.get(property_url + "/byggnad/unknown/struktur").status_code == 404
    for kind in ("flaktrum", "takflakt", "other"):
        space = {
            "space_id": "s1",
            "label": "LB01",
            "system_id": "LB01",
            "kind": kind,
            "location": " Plan 5 ",
            "status": "pass",
        }
        result = client.put(url, json={**inventory, "technical_spaces": [space]})
        assert result.status_code == 200
        assert result.json()["technical_spaces"][0] == {
            "space_id": "s1",
            "label": "LB01",
            "system_id": "LB01",
            "kind": kind,
            "location": "Plan 5",
        }
    invalid_space = {**space, "kind": "unknown"}
    assert (
        client.put(url, json={**inventory, "technical_spaces": [invalid_space]}).status_code == 422
    )
    assert client.get(url).json() == result.json()


def test_inventory_editor_is_served(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(ovk_fastighet_router(tmp_path))
    client = TestClient(app)
    page = client.get("/ovk/fastighet")
    script = client.get("/ovk/fastighet/app.js")
    assert page.status_code == 200
    assert script.status_code == 200
    assert 'id="inventoryBuilding"' in page.text
    assert 'id="inventoryFields" disabled' in page.text
    assert 'id="inventorySave"' in page.text
    assert "function inventoryCanLeave()" in script.text
    assert "revision!==inventoryRevision" in script.text
    assert "inventoryReset(saved.fastighet)" in script.text
    assert "inventory.technical_spaces.some" in script.text
    assert "Installationstyp" in script.text
    assert "space.kind" in script.text
    assert "space.location" in script.text


def test_bulk_inventory_editor_is_served(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(ovk_fastighet_router(tmp_path))
    client = TestClient(app)
    page = client.get("/ovk/fastighet")
    script = client.get("/ovk/fastighet/app.js")
    assert page.status_code == 200
    assert script.status_code == 200
    assert 'id="bulkPreview"' in page.text
    assert 'id="bulkApply" disabled' in page.text
    assert "function bulkPlan()" in script.text
    assert "numbers.filter(n=>existing.has(n))" in script.text
    assert "inventory.units.push(...additions)" in script.text
    assert "JSON.stringify(plan)!==JSON.stringify(bulkPreview)" in script.text


def test_registered_measurement_points_are_inventory_only(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(ovk_fastighet_router(tmp_path))
    client = TestClient(app)
    property_url = "/api/ovk/projects/p1/fastighet/f1"
    url = property_url + "/byggnad/hus-a/struktur"
    assert (
        client.put(
            property_url,
            json={
                "fastighetsbeteckning": "Test 1:1",
                "byggnader": [{"byggnad_id": "hus-a", "internt_namn": "Hus A"}],
            },
        ).status_code
        == 200
    )
    point = {
        "point_id": "p1",
        "label": "FL01",
        "point_type": "franluftsdon",
        "system_id": "LB01",
        "designed_value": "15.5",
        "unit_of_measure": "l/s",
    }

    def inventory(points: list[dict[str, str]]) -> dict[str, object]:
        return {
            "systems": [{"system_id": "LB01", "system_type": "FTX", "label": "LB01"}],
            "units": [
                {
                    "unit_id": "u1",
                    "number": "1203",
                    "kind": "apartment",
                    "rooms": [{"room_id": "r1", "name": "Kök", "measurement_points": points}],
                }
            ],
        }

    saved = client.put(url, json=inventory([{**point, "measured_value": "8"}]))
    assert saved.status_code == 200
    assert saved.json()["units"][0]["rooms"][0]["measurement_points"] == [point]
    assert client.get(url).json() == saved.json()
    for invalid in (
        [point, point],
        [{**point, "system_id": "unknown"}],
        [{**point, "designed_value": "NaN"}],
        [{**point, "unit_of_measure": "m3/h"}],
    ):
        assert client.put(url, json=inventory(invalid)).status_code == 422
    assert client.get(url).json() == saved.json()


def test_apartment_template_generator_is_served(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(ovk_fastighet_router(tmp_path))
    client = TestClient(app)
    page = client.get("/ovk/fastighet").text
    script = client.get("/ovk/fastighet/app.js").text
    assert 'id="templatePanel"' in page
    assert 'id="templateApply" disabled' in page
    assert "function templatePlan()" in script
    assert "suffixes.has(rule.suffix)" in script
    assert "if(existing.has(number)){" in script
    assert "if(fillEmpty&&target.kind==='apartment'&&!target.rooms.length)" in script
    assert "completions.push({unit_id:target.unit_id" in script
    assert "else skipped.push(number)" in script
    assert "JSON.stringify(plan)!==JSON.stringify(templatePreview)" in script
    assert "point_id:inventoryId('point')" in script
    assert "room_id:inventoryId('room')" in script
    assert "unit_id:inventoryId('unit')" in script


def test_apartment_template_completion_requires_preview_and_confirmation(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(ovk_fastighet_router(tmp_path))
    client = TestClient(app)
    page = client.get("/ovk/fastighet").text
    script = client.get("/ovk/fastighet/app.js").text

    assert 'id="templateFillEmpty"' in page
    assert 'id="templateConfirmSystems"' in page
    assert 'id="templateApply" disabled' in page
    assert "!$('templateConfirmSystems').checked" in script
    assert "$('templateConfirmSystems').checked=false" in script
    assert "clearBulkPreview();clearTemplatePreview();" in script
    assert "Dubbla enhetsnummer i byggnaden" in script
    assert "for(const item of completions)item.target.rooms=item.rooms" in script
    assert "item.unit_id===u.unit_id" in script
    assert "target.kind==='apartment'&&!target.rooms.length" in script
    assert "measurement_points:r.measurement_points.map" in script
    assert "return {revision:inventoryRevision,trapphus,additions,completions,skipped}" in script


def test_completed_inventory_roundtrip_keeps_existing_unit_identity(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(ovk_fastighet_router(tmp_path))
    client = TestClient(app)
    property_url = "/api/ovk/projects/p1/fastighet/f1"
    url = property_url + "/byggnad/hus-a/struktur"
    assert (
        client.put(
            property_url,
            json={
                "fastighetsbeteckning": "Test 1:1",
                "byggnader": [{"byggnad_id": "hus-a", "internt_namn": "Hus A"}],
            },
        ).status_code
        == 200
    )
    source_point = {
        "point_id": "p1",
        "label": "FL01",
        "point_type": "franluftsdon",
        "system_id": "LB01",
        "designed_value": "15.5",
        "unit_of_measure": "l/s",
    }
    source_room = {"room_id": "r1", "name": "Kök", "measurement_points": [source_point]}
    source = {
        "unit_id": "u1",
        "number": "1101",
        "kind": "apartment",
        "rooms": [source_room],
    }
    empty = {"unit_id": "u2", "number": "1201", "kind": "apartment", "rooms": []}
    individual = {
        "unit_id": "u3",
        "number": "1301",
        "kind": "apartment",
        "rooms": [{"room_id": "r3", "name": "Individuell planlösning"}],
    }
    inventory = {
        "units": [source, empty, individual],
        "systems": [{"system_id": "LB01", "system_type": "FTX", "label": "LB01"}],
        "technical_spaces": [],
    }
    assert client.put(url, json=inventory).status_code == 200
    completed = {
        **empty,
        "rooms": [
            {
                "room_id": "r2",
                "name": "Kök",
                "measurement_points": [{**source_point, "point_id": "p2"}],
            }
        ],
    }
    result = client.put(url, json={**inventory, "units": [source, completed, individual]})
    assert result.status_code == 200
    assert client.get(url).json()["units"] == [source, completed, individual]


def test_premises_name_is_separate_from_permanent_number(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(ovk_fastighet_router(tmp_path))
    client = TestClient(app)
    property_url = "/api/ovk/projects/p1/fastighet/f1"
    url = property_url + "/byggnad/hus-a/struktur"
    assert (
        client.put(
            property_url,
            json={
                "fastighetsbeteckning": "Test 1:1",
                "byggnader": [{"byggnad_id": "hus-a", "internt_namn": "Hus A"}],
            },
        ).status_code
        == 200
    )
    unit = {
        "unit_id": "stable-u1",
        "number": "A101",
        "kind": "premises",
        "label": "Restaurang Hov",
        "display_mode": "name",
        "rooms": [],
    }
    saved = client.put(url, json={"units": [unit]})
    assert saved.status_code == 200
    assert saved.json()["units"][0] == unit
    unit["label"] = "Butik A"
    renamed = client.put(url, json={"units": [unit]})
    assert renamed.status_code == 200
    assert renamed.json()["units"][0]["unit_id"] == "stable-u1"
    assert renamed.json()["units"][0]["number"] == "A101"
    assert renamed.json()["units"][0]["label"] == "Butik A"
    assert client.get(url).json()["units"][0] == unit

    for invalid in (
        {**unit, "number": ""},
        {**unit, "label": ""},
        {**unit, "display_mode": "unknown"},
    ):
        assert client.put(url, json={"units": [invalid]}).status_code == 422

    legacy = {"unit_id": "old-u1", "number": "1001", "kind": "premises", "rooms": []}
    response = client.put(url, json={"units": [legacy]})
    assert response.status_code == 200
    assert response.json()["units"][0]["number"] == "1001"
    assert response.json()["units"][0]["display_mode"] == "number"


def test_premises_editor_exposes_separate_name_and_number(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(ovk_fastighet_router(tmp_path))
    script = TestClient(app).get("/ovk/fastighet/app.js")
    assert script.status_code == 200
    assert "Permanent lokalnummer" in script.text
    assert "Lokalnamn (fritext)" in script.text
    assert "unit.display_mode" in script.text


def test_trapphus_editor_is_served(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(ovk_fastighet_router(tmp_path))
    client = TestClient(app)
    page = client.get("/ovk/fastighet")
    script = client.get("/ovk/fastighet/app.js")
    assert 'id="inventoryTrapphus"' in page.text
    assert 'id="inventoryAddTrapphus"' in page.text
    assert 'id="bulkTrapphus"' in page.text
    assert "function trapphusLabel(item)" in script.text
    assert "delete unit.trapphus_id" in script.text
    assert 'id="templateTrapphus"' in page.text
    assert "function unitDisplayNumber(unit)" in script.text
    assert "inventory.units.filter(u=>unitScope(u)===trapphus)" in script.text
    assert "inventory.units.some(u=>u.trapphus_id===item.trapphus_id)" in script.text
