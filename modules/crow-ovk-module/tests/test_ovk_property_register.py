"""Fastighetsregistret: organisationens fastigheter över alla projekt."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from crow_ovk_fastighet import Adress, Byggnad, Fastighet, FastighetRepository
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from test_ovk_overview_surface import _entitle, _issue, _record

from crow_ovk_module.ovk_property_register_surface import (
    normalize_designation,
    ovk_property_register_router,
)
from crow_ovk_module.plugin import CrowOvkModulePlugin
from crow_ovk_workflow import OvkWorkflowRecord, OvkWorkflowRepository
from crow_workbench.shell import create_app


def _client(root: Path) -> TestClient:
    app = FastAPI()
    app.include_router(ovk_property_register_router(root))
    return TestClient(app)


def _property(
    root: Path,
    *,
    project_id: str = "p1",
    fastighet_id: str = "object-1",
    beteckning: str = "Lärkan 4",
    ort: str = "Vaxholm",
) -> None:
    FastighetRepository(root).save(
        Fastighet(
            fastighet_id=fastighet_id,
            project_id=project_id,
            fastighetsbeteckning=beteckning,
            byggnadens_adress=Adress(gata="Storgatan 1", postnr="185 31", ort=ort),
            byggnadsagare_namn="Brf Lärkan",
            byggnader=(Byggnad(byggnad_id="building-1", internt_namn="Hus A"),),
        )
    )


def _body(root: Path) -> dict[str, Any]:
    response = _client(root).get("/api/ovk/fastigheter")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def test_empty_register_is_complete_and_empty(tmp_path: Path) -> None:
    assert _body(tmp_path) == {"fastigheter": [], "ej_lasbara": [], "fullstandig": True}


def test_register_lists_properties_from_all_projects(tmp_path: Path) -> None:
    _property(tmp_path, project_id="p2", fastighet_id="b", beteckning="Örnen 1")
    _property(tmp_path, project_id="p1", fastighet_id="a", beteckning="Lärkan 4")

    items = _body(tmp_path)["fastigheter"]

    assert [(item["project_id"], item["fastighetsbeteckning"]) for item in items] == [
        ("p1", "Lärkan 4"),
        ("p2", "Örnen 1"),
    ]
    assert items[0] == {
        "project_id": "p1",
        "fastighet_id": "a",
        "fastighetsbeteckning": "Lärkan 4",
        "gata": "Storgatan 1",
        "postnr": "185 31",
        "ort": "Vaxholm",
        "byggnadsagare": "Brf Lärkan",
        "fastighetstyp": "flerbostadshus",
        "byggnader": [{"byggnad_id": "building-1", "namn": "Hus A"}],
        "antal_besiktningar": 0,
        "senast_utfardat": None,
        "nasta_besiktning": None,
        "byggnader_utan_frist": 1,
        "intyg_oklart": False,
        "forekomster": 1,
    }


def test_same_designation_and_town_is_pointed_out_not_merged(tmp_path: Path) -> None:
    _property(tmp_path, project_id="p1", beteckning="Lärkan 4", ort="Vaxholm")
    _property(tmp_path, project_id="p2", beteckning=" lärkan  4 ", ort="vaxholm")
    _property(tmp_path, project_id="p3", beteckning="Lärkan 4", ort="Täby")

    items = _body(tmp_path)["fastigheter"]

    assert len(items) == 3
    assert {item["project_id"]: item["forekomster"] for item in items} == {
        "p1": 2,
        "p2": 2,
        "p3": 1,
    }


def test_designation_normalization_matches_the_search_in_new_inspection() -> None:
    assert normalize_designation("  Lärkan   4 ") == normalize_designation("lärkan 4")
    assert normalize_designation("Kv 1 : 23") == normalize_designation("kv 1:23")
    assert normalize_designation("Lärkan 4") != normalize_designation("Lärkan 40")


def test_register_shows_inspections_and_the_current_certificate(tmp_path: Path) -> None:
    _property(tmp_path)
    workflows = OvkWorkflowRepository(tmp_path)
    workflows.save(_record("ovk-planerad"))
    issued = _record("ovk-utfardad", ready=True)
    workflows.save(issued)
    intyg = _issue(tmp_path, issued)

    item = _body(tmp_path)["fastigheter"][0]

    assert item["antal_besiktningar"] == 2
    assert item["senast_utfardat"] == "2026-12-02"
    assert intyg.next_inspection.due_date is not None
    assert item["nasta_besiktning"] == intyg.next_inspection.due_date.isoformat()
    assert item["byggnader_utan_frist"] == 0
    assert item["intyg_oklart"] is False


def test_certificate_without_valid_manifest_is_flagged_not_dropped(tmp_path: Path) -> None:
    _property(tmp_path)
    issued = _record("ovk-utfardad", ready=True)
    OvkWorkflowRepository(tmp_path).save(issued)
    _issue(tmp_path, issued)
    (tmp_path / "projects" / "p1" / "ovk-issuance-manifest" / "ovk-utfardad.json").unlink()

    item = _body(tmp_path)["fastigheter"][0]

    assert item["antal_besiktningar"] == 1
    assert item["senast_utfardat"] is None
    assert item["nasta_besiktning"] is None
    # Intyget finns på disk: raden får inte se ut som en obesiktad fastighet.
    assert item["intyg_oklart"] is True


def _in_building(record: OvkWorkflowRecord, building_id: str) -> OvkWorkflowRecord:
    inspection = record.inspection
    return replace(
        record,
        inspection=replace(
            inspection, ovk_object=replace(inspection.ovk_object, building_id=building_id)
        ),
    )


def test_deadline_of_one_building_does_not_speak_for_the_whole_property(
    tmp_path: Path,
) -> None:
    FastighetRepository(tmp_path).save(
        Fastighet(
            fastighet_id="object-1",
            project_id="p1",
            fastighetsbeteckning="Lärkan 4",
            byggnader=(
                Byggnad(byggnad_id="building-1", internt_namn="Hus A"),
                Byggnad(byggnad_id="building-2", internt_namn="Hus B"),
                Byggnad(byggnad_id="building-3", internt_namn="Hus C"),
            ),
        )
    )
    workflows = OvkWorkflowRepository(tmp_path)
    approved = _record("ovk-a", ready=True)
    failed = _in_building(_record("ovk-b", deficient=True), "building-2")
    workflows.save(approved)
    workflows.save(failed)
    passed = _issue(tmp_path, approved, "intyg-a")
    assert _issue(tmp_path, failed, "intyg-b").next_inspection.due_date is None

    item = _body(tmp_path)["fastigheter"][0]

    assert passed.next_inspection.due_date is not None
    assert item["nasta_besiktning"] == passed.next_inspection.due_date.isoformat()
    # Hus B är underkänt och Hus C är aldrig besiktat.
    assert item["byggnader_utan_frist"] == 2


def test_certificate_claiming_another_project_withholds_the_project(tmp_path: Path) -> None:
    _property(tmp_path)
    issued = _record("ovk-utfardad", ready=True)
    OvkWorkflowRepository(tmp_path).save(issued)
    _issue(tmp_path, issued)
    path = tmp_path / "projects" / "p1" / "ovk-intyg" / "intyg-1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["project_id"] = "p2"
    path.write_text(json.dumps(payload), encoding="utf-8")

    body = _body(tmp_path)

    assert body["fastigheter"] == []
    assert body["ej_lasbara"] == [{"project_id": "p1", "orsak": "intyg"}]


def test_property_stored_under_another_name_withholds_the_project(tmp_path: Path) -> None:
    _property(tmp_path)
    directory = tmp_path / "projects" / "p1" / "fastighet"
    (directory / "object-1.json").rename(directory / "annat-namn.json")

    body = _body(tmp_path)

    assert body["fastigheter"] == []
    assert body["ej_lasbara"] == [{"project_id": "p1", "orsak": "identitet"}]


def test_unreadable_project_is_reported_not_hidden(tmp_path: Path) -> None:
    _property(tmp_path, project_id="p1")
    _property(tmp_path, project_id="p2", beteckning="Örnen 1")
    (tmp_path / "projects" / "p1" / "fastighet" / "trasig.json").write_text("{", encoding="utf-8")

    body = _body(tmp_path)

    assert [item["project_id"] for item in body["fastigheter"]] == ["p2"]
    assert body["fullstandig"] is False
    assert body["ej_lasbara"] == [{"project_id": "p1", "orsak": "projekt"}]


def test_property_claiming_another_project_withholds_the_project(tmp_path: Path) -> None:
    _property(tmp_path, project_id="p1")
    path = tmp_path / "projects" / "p1" / "fastighet" / "object-1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["project_id"] = "p2"
    path.write_text(json.dumps(payload), encoding="utf-8")

    body = _body(tmp_path)

    assert body["fastigheter"] == []
    assert body["ej_lasbara"] == [{"project_id": "p1", "orsak": "identitet"}]


def test_register_requires_a_session_in_session_mode(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_AUTH_MODE", "session")
    _property(tmp_path)

    response = _client(tmp_path).get("/api/ovk/fastigheter")

    assert response.status_code == 401
    assert response.json() == {"detail": {"code": "AUTHENTICATION_REQUIRED"}}


def test_shell_serves_the_register_only_with_an_ovk_licence(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_MODE", "local")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    monkeypatch.delenv("CROW_AUTH_MODE", raising=False)
    _property(tmp_path)

    _entitle(tmp_path, active=True)
    allowed = TestClient(create_app(tmp_path)).get("/api/ovk/fastigheter")
    assert allowed.status_code == 200
    assert len(allowed.json()["fastigheter"]) == 1

    _entitle(tmp_path, active=False)
    refused = TestClient(create_app(tmp_path)).get("/api/ovk/fastigheter")
    assert refused.status_code == 403
    assert refused.json()["detail"] == {"code": "MODULE_NOT_ACTIVE", "module": "ovk"}


def test_plugin_registers_the_register_and_its_script(tmp_path: Path) -> None:
    paths = {
        getattr(route, "path", "")
        for router in CrowOvkModulePlugin().routers(tmp_path)
        for route in router.routes
    }
    assert "/api/ovk/fastigheter" in paths
    assert "/ovk/fastigheter.js" in paths


def test_property_page_carries_the_register_and_the_shell(tmp_path: Path) -> None:
    app = FastAPI()
    for router in CrowOvkModulePlugin().routers(tmp_path):
        app.include_router(router)
    client = TestClient(app)
    page = client.get("/ovk/fastighet").text

    for element in (
        'id="registerSearch"',
        'id="registerStatus"',
        'id="registerWarning"',
        'id="registerItems"',
        'id="registerEmpty"',
        'id="registerRefresh"',
    ):
        assert element in page
    # Kärnan ersätter sidans första <nav>; OVK:s navigation är den andra.
    assert page.index("<nav>") < page.index('<nav aria-label="OVK-navigation" id="ovkNav"')
    scripts = [
        page.index('<script src="/ovk/skal.js">'),
        page.index('<script src="/ovk/fastigheter.js">'),
        page.index('<script src="/ovk/fastighet/app.js">'),
    ]
    assert scripts == sorted(scripts)

    script = client.get("/ovk/fastigheter.js")
    assert script.status_code == 200
    assert "/api/ovk/fastigheter" in script.text
    assert "innerHTML" not in script.text
    app_script = client.get("/ovk/fastighet/app.js").text
    assert "ovkProperties.init({onOpen:openRegisteredProperty})" in app_script
