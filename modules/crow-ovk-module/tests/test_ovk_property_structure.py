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
