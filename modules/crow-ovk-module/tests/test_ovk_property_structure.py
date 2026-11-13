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
    assert client.get(url).json() == saved.json()
    assert client.put(property_url, json=property_payload).status_code == 200
    assert client.get(url).json() == saved.json()
    invalid = {**inventory, "systems": []}
    assert client.put(url, json=invalid).status_code == 422
    assert client.get(url).json() == saved.json()
    assert client.get(property_url + "/byggnad/unknown/struktur").status_code == 404


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
