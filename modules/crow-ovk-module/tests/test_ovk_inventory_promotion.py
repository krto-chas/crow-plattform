from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk import OvkObject, VentilationSystemRef
from crow_ovk_module.ovk_fastighet_surface import ovk_fastighet_router
from crow_ovk_module.ovk_field_surface import ovk_field_router
from crow_ovk_module.ovk_inventory_promotion import plan_inventory_promotion
from crow_ovk_workflow import OvkWorkflowRepository, build_record


def test_promotion_is_additive_revision_bound_and_preserves_inspection(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(ovk_fastighet_router(tmp_path))
    app.include_router(ovk_field_router(tmp_path))
    client = TestClient(app)
    property_url = "/api/ovk/projects/p1/fastighet/f1"
    url = property_url + "/byggnad/hus-a/struktur"
    promotion = url + "/aterforing/ovk-1"
    sync = "/api/ovk/projects/p1/field/ovk-1/sync"
    assert (
        client.put(
            property_url,
            json={
                "fastighetsbeteckning": "Eken 1:1",
                "byggnader": [
                    {"byggnad_id": "hus-a", "internt_namn": "Hus A"},
                    {"byggnad_id": "hus-b", "internt_namn": "Hus B"},
                ],
            },
        ).status_code
        == 200
    )
    workflows = OvkWorkflowRepository(tmp_path)
    workflows.save(
        build_record(
            inspection_id="ovk-1",
            ovk_object=OvkObject("f1", "p1", "hus-a", "Eken 1:1"),
            systems=(VentilationSystemRef("LB01", "FTX", "LB01"),),
        )
    )
    original_workflow = workflows.load("p1", "ovk-1")
    existing = {
        "unit_id": "u1",
        "number": "1101",
        "kind": "apartment",
        "rooms": [{"room_id": "r1", "name": "Kök"}],
    }
    structure = {
        "units": [existing],
        "systems": [{"system_id": "LB01", "system_type": "FTX", "label": "LB01"}],
        "technical_spaces": [],
    }
    assert client.put(url, json=structure).status_code == 200
    base = client.get(url)
    revision = base.headers["X-OVK-Inventory-Revision"]
    assert client.post(promotion + "/preview", json={}).status_code == 404

    payload: dict[str, Any] = {
        "inspection_id": "ovk-1",
        "units": [
            {"unit_id": "u1", "number": "1101", "kind": "apartment"},
            {"unit_id": "u2", "number": "1201", "kind": "apartment"},
            {"unit_id": "conflict", "number": "1101", "kind": "apartment"},
        ],
        "rooms": [
            {"room_id": "r1", "unit_id": "u1", "name": "Kök"},
            {"room_id": "r2", "unit_id": "u2", "name": "Badrum"},
        ],
        "measurements": [
            {
                "measurement_id": "m1",
                "unit_id": "u2",
                "room_id": "r2",
                "point_type": "franluftsdon",
                "point_label": "FL01",
                "designed_value": "15",
                "measured_value": "12",
                "measurable": True,
                "unit_of_measure": "l/s",
            }
        ],
    }
    saved = client.put(sync, json=payload)
    assert saved.status_code == 200, saved.text
    snapshot = client.get(sync).json()
    wrong_building = property_url + "/byggnad/hus-b/struktur/aterforing/ovk-1/preview"
    assert client.post(wrong_building, json={}).status_code == 409
    preview = client.post(promotion + "/preview", json={})
    assert preview.status_code == 200, preview.text
    assert preview.json()["unresolved"] == [{"point_id": "m1", "label": "1201 / Badrum / FL01"}]
    assert len(preview.json()["conflicts"]) == 2
    assert client.get(url).json() == structure
    assert (
        client.post(promotion + "/preview", json={"assignments": {"m1": "unknown"}}).status_code
        == 422
    )
    assignments = {"m1": "LB01"}
    plan = client.post(promotion + "/preview", json={"assignments": assignments}).json()
    assert [item["kind"] for item in plan["additions"]] == ["unit", "room", "point"]
    assert plan["structure"]["units"][0] == existing
    point = plan["structure"]["units"][1]["rooms"][0]["measurement_points"][0]
    assert point == {
        "point_id": "m1",
        "label": "FL01",
        "point_type": "franluftsdon",
        "system_id": "LB01",
        "designed_value": "15",
        "unit_of_measure": "l/s",
    }
    apply = {"assignments": assignments, "preview_token": plan["preview_token"]}
    assert client.post(promotion + "/apply", json=apply).status_code == 422

    # An intervening inventory edit invalidates the reviewed preview.
    updated = {
        **structure,
        "units": [
            existing,
            {"unit_id": "u3", "number": "1301", "kind": "apartment", "rooms": []},
        ],
    }
    assert (
        client.put(url, json=updated, headers={"X-OVK-Inventory-Revision": revision}).status_code
        == 200
    )
    assert client.post(promotion + "/apply", json={**apply, "confirmed": True}).status_code == 409
    plan = client.post(promotion + "/preview", json={"assignments": assignments}).json()
    apply["preview_token"] = plan["preview_token"]

    # A new synced revision also invalidates the reviewed preview.
    changed_payload = {
        **payload,
        "measurements": [{**payload["measurements"][0], "measured_value": "13"}],
    }
    assert (
        client.put(
            sync,
            json=changed_payload,
            headers={"X-OVK-Base-Revision": snapshot["snapshot_sha256"]},
        ).status_code
        == 200
    )
    assert client.post(promotion + "/apply", json={**apply, "confirmed": True}).status_code == 409
    snapshot = client.get(sync).json()
    plan = client.post(promotion + "/preview", json={"assignments": assignments}).json()
    apply["preview_token"] = plan["preview_token"]
    committed = client.post(promotion + "/apply", json={**apply, "confirmed": True})
    assert committed.status_code == 200, committed.text
    assert client.get(url).json() == plan["structure"]
    assert client.get(sync).json() == snapshot
    assert workflows.load("p1", "ovk-1") == original_workflow
    assert client.post(promotion + "/apply", json={**apply, "confirmed": True}).status_code == 409
    assert (
        client.put(url, json=structure, headers={"X-OVK-Inventory-Revision": revision}).status_code
        == 409
    )
    assert client.get(url).json() == plan["structure"]
    repeat = client.post(promotion + "/preview", json={"assignments": assignments}).json()
    assert repeat["additions"] == []


def test_promotion_editor_is_served(tmp_path: Path) -> None:
    app = FastAPI()
    app.include_router(ovk_fastighet_router(tmp_path))
    client = TestClient(app)
    page = client.get("/ovk/fastighet").text
    script = client.get("/ovk/fastighet/app.js").text
    for element_id in (
        "promotionPanel",
        "promotionSource",
        "promotionPreview",
        "promotionResult",
        "promotionConfirm",
        "promotionApply",
    ):
        assert page.count(f'id="{element_id}"') == 1
    assert "plan.inventory_revision!==inventoryServerRevision" in script
    assert "preview_token:plan.preview_token,confirmed:true" in script
    assert "X-OVK-Inventory-Revision" in script
    assert "inventoryBusy||inventoryDirty" in script


def test_promotion_leaves_existing_design_and_conflicting_rooms_unchanged() -> None:
    inventory = {
        "systems": [{"system_id": "LB01", "label": "LB01", "system_type": "FTX"}],
        "units": [
            {
                "unit_id": "u1",
                "number": "1101",
                "kind": "apartment",
                "rooms": [
                    {
                        "room_id": "r1",
                        "name": "Kök",
                        "measurement_points": [
                            {
                                "point_id": "m1",
                                "label": "FL01",
                                "point_type": "franluftsdon",
                                "system_id": "LB01",
                                "designed_value": "15",
                                "unit_of_measure": "l/s",
                            }
                        ],
                    }
                ],
            }
        ],
        "technical_spaces": [],
    }
    snapshot = {
        "units": [
            {"unit_id": "u1", "number": "1101", "kind": "apartment"},
            {"unit_id": "u2", "number": "1201", "kind": "apartment", "status": "bom"},
        ],
        "rooms": [
            {"room_id": "r1", "unit_id": "u1", "name": "Kök"},
            {"room_id": "r2", "unit_id": "u1", "name": "Kök"},
            {"room_id": "r3", "unit_id": "u2", "name": "Hall"},
        ],
        "measurements": [
            {
                "measurement_id": "m1",
                "unit_id": "u1",
                "room_id": "r1",
                "point_type": "franluftsdon",
                "point_label": "FL01",
                "system_id": "LB01",
                "designed_value": "20",
                "measured_value": "18",
                "unit_of_measure": "l/s",
            }
        ],
    }
    before = deepcopy(inventory)
    source_before = deepcopy(snapshot)
    plan = plan_inventory_promotion(inventory, snapshot, {})
    assert inventory == before
    assert snapshot == source_before
    assert plan["structure"]["units"][0] == inventory["units"][0]
    assert plan["structure"]["units"][1] == {
        "unit_id": "u2",
        "number": "1201",
        "kind": "apartment",
        "rooms": [],
    }
    assert plan["additions"] == [{"kind": "unit", "id": "u2", "label": "1201"}]
    assert len(plan["conflicts"]) == 3
