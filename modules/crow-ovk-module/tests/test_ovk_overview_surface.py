"""Uppdragsöversikten: härledd status, nästa steg och redovisade läsfel."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from crow_ovk_fastighet import (
    Adress,
    Behorighet,
    Besiktningsman,
    BesiktningsmanRepository,
    Byggnad,
    Fastighet,
    FastighetRepository,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from crow_entitlements.models import CustomerContext
from crow_ovk import CheckStatus, OvkCheckpoint, OvkObject, VentilationSystemRef
from crow_ovk_intyg import Behorighet as IntygBehorighet
from crow_ovk_intyg import (
    Byggnadsagare,
    Funktionskontrollant,
    OvkIntygRepository,
    build_intyg,
)
from crow_ovk_module.ovk_overview_surface import (
    STATUS_LABELS,
    derive_status,
    ovk_overview_router,
)
from crow_ovk_module.ovk_scope import visible_project_ids
from crow_ovk_module.plugin import CrowOvkModulePlugin
from crow_ovk_pricing import BuildingCategory, InspectionType
from crow_ovk_workflow import (
    AggregatCoverage,
    AggregatStatus,
    BekraftelseRoll,
    CaseStatus,
    InspectionCoverage,
    OvkWorkflowRecord,
    OvkWorkflowRepository,
    SystemForteckningBekraftelse,
    build_record,
)
from crow_ovk_workflow.models import InspectionPlanning

_PLANNING = InspectionPlanning("stina-b", date(2026, 12, 1), "aterkommande")


def _client(root: Path) -> TestClient:
    app = FastAPI()
    app.include_router(ovk_overview_router(root))
    return TestClient(app)


def _record(
    inspection_id: str,
    *,
    project_id: str = "p1",
    ready: bool = False,
    planning: InspectionPlanning | None = _PLANNING,
) -> OvkWorkflowRecord:
    systems = (VentilationSystemRef("FTX01", "FTX", "System FTX01"),)
    obj = OvkObject("object-1", project_id, "building-1", "Kv. Lärkan", address="Storgatan 1")
    if not ready:
        return build_record(
            inspection_id=inspection_id, ovk_object=obj, systems=systems, planning=planning
        )
    return build_record(
        inspection_id=inspection_id,
        ovk_object=obj,
        systems=systems,
        planning=planning,
        checkpoints=(
            OvkCheckpoint(
                checkpoint_id="cp1",
                label="Drift och funktion",
                status=CheckStatus.PASS,
                system_id="FTX01",
            ),
        ),
        coverage=InspectionCoverage(
            inspection_id=inspection_id,
            aggregat=(
                AggregatCoverage(
                    aggregat_id="agg-1", label="FTX01", status=AggregatStatus.BESIKTIGAD
                ),
            ),
            system_list_confirmation=SystemForteckningBekraftelse(
                confirmed_by="Stina Besiktning", role=BekraftelseRoll.BESIKTNINGSMAN
            ),
        ),
    )


def _snapshot(root: Path, inspection_id: str, *, completed: str | None = None) -> None:
    path = root / "projects" / "p1" / "ovk-field" / inspection_id / "snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"inspection_id": inspection_id, "units": []}
    if completed is not None:
        payload["field_work_completed_at"] = completed
    path.write_text(json.dumps(payload), encoding="utf-8")


def _by_id(root: Path) -> dict[str, dict[str, object]]:
    response = _client(root).get("/api/ovk/uppdrag")
    assert response.status_code == 200
    return {item["inspection_id"]: item for item in response.json()["uppdrag"]}


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({}, "ej_planerad"),
        ({"planned": True}, "planerad"),
        ({"planned": True, "has_snapshot": True}, "pagaende"),
        ({"has_snapshot": True, "field_completed": True}, "att_granska"),
        ({"has_snapshot": True, "field_completed": True, "protocol_ready": True}, "leveransklar"),
        ({"protocol_ready": True, "issued": True}, "utfardad"),
        ({"protocol_ready": True, "issued": True, "deficiencies": True}, "atgarder_oppna"),
        (
            {"issued": True, "deficiencies": True, "reinspection": CaseStatus.OPEN},
            "ombesiktning",
        ),
        (
            {"issued": True, "deficiencies": True, "reinspection": CaseStatus.READY},
            "ombesiktning",
        ),
        (
            {"issued": True, "deficiencies": True, "reinspection": CaseStatus.CLOSED},
            "utfardad",
        ),
    ],
)
def test_status_is_derived_from_existing_facts(flags: dict[str, object], expected: str) -> None:
    defaults: dict[str, object] = {
        "planned": False,
        "has_snapshot": False,
        "field_completed": False,
        "protocol_ready": False,
        "issued": False,
        "deficiencies": False,
        "reinspection": None,
    }
    assert derive_status(**{**defaults, **flags}) == expected  # type: ignore[arg-type]
    assert expected in STATUS_LABELS


def test_empty_data_root_is_a_complete_empty_overview(tmp_path: Path) -> None:
    body = _client(tmp_path).get("/api/ovk/uppdrag").json()
    assert body["uppdrag"] == []
    assert body["fullstandig"] is True
    assert body["ej_lasbara"] == []
    assert set(body["antal"]) == set(STATUS_LABELS)
    assert not any(body["antal"].values())


def test_overview_follows_the_assignment_through_the_field(tmp_path: Path) -> None:
    workflows = OvkWorkflowRepository(tmp_path)
    workflows.save(_record("ovk-planerad"))
    workflows.save(_record("ovk-pagaende"))
    workflows.save(_record("ovk-granska"))
    workflows.save(_record("ovk-klar", ready=True))
    workflows.save(_record("ovk-utkast", planning=None))
    _snapshot(tmp_path, "ovk-pagaende")
    _snapshot(tmp_path, "ovk-granska", completed="2026-11-20T15:30:00.000Z")

    items = _by_id(tmp_path)

    assert items["ovk-planerad"]["status"] == "planerad"
    assert items["ovk-planerad"]["falt"] == {
        "synkad": False,
        "senast_synkad": None,
        "avslutat": None,
    }
    assert items["ovk-pagaende"]["status"] == "pagaende"
    assert items["ovk-granska"]["status"] == "att_granska"
    assert items["ovk-granska"]["falt"]["avslutat"] == "2026-11-20T15:30:00.000Z"  # type: ignore[index]
    assert items["ovk-klar"]["status"] == "leveransklar"
    assert items["ovk-klar"]["tackning_klar"] is True
    assert items["ovk-utkast"]["status"] == "ej_planerad"
    assert items["ovk-utkast"]["planerat_datum"] is None

    body = _client(tmp_path).get("/api/ovk/uppdrag").json()
    assert body["antal"]["planerad"] == 1
    assert body["antal"]["leveransklar"] == 1
    assert sum(body["antal"].values()) == 5


def test_overview_shows_business_names_and_next_step(tmp_path: Path) -> None:
    OvkWorkflowRepository(tmp_path).save(_record("ovk-1"))
    FastighetRepository(tmp_path).save(
        Fastighet(
            fastighet_id="object-1",
            project_id="p1",
            fastighetsbeteckning="Lärkan 4",
            byggnadens_adress=Adress(gata="Storgatan 1", postnr="185 31", ort="Vaxholm"),
            byggnader=(Byggnad(byggnad_id="building-1", internt_namn="Hus A"),),
        )
    )
    BesiktningsmanRepository(tmp_path).save(
        Besiktningsman(
            besiktningsman_id="stina-b",
            namn="Stina Besiktning",
            behorighet=Behorighet.K,
            certifieringsorgan="RISE",
            certnummer="1234",
            giltig_till=date(2028, 1, 1),
        )
    )

    item = _by_id(tmp_path)["ovk-1"]

    assert item["fastighetsbeteckning"] == "Lärkan 4"
    assert item["adress"] == "Storgatan 1, 185 31 Vaxholm"
    assert item["byggnad"] == "Hus A"
    assert item["besiktningsman"] == "Stina Besiktning"
    assert item["system"] == ["FTX"]
    assert item["planerat_datum"] == "2026-12-01"
    assert item["status_text"] == "Planerad"
    assert item["nasta_steg"] == {
        "text": "Öppna i fält",
        "href": "/ovk/falt?project_id=p1&inspection_id=ovk-1",
    }


def test_unregistered_property_and_inspector_are_not_invented(tmp_path: Path) -> None:
    OvkWorkflowRepository(tmp_path).save(_record("ovk-1"))

    item = _by_id(tmp_path)["ovk-1"]

    assert item["fastighetsbeteckning"] is None
    assert item["byggnad"] is None
    assert item["besiktningsman"] is None
    assert item["adress"] == "Storgatan 1"


def test_issued_certificate_moves_the_assignment_to_utfardad(tmp_path: Path) -> None:
    record = _record("ovk-klar", ready=True)
    OvkWorkflowRepository(tmp_path).save(record)
    OvkIntygRepository(tmp_path).save(
        build_intyg(
            intyg_id="intyg-1",
            record=record,
            fastighetsbeteckning="Lärkan 4",
            byggnadsagare=Byggnadsagare(name="Brf Lärkan"),
            funktionskontrollant=Funktionskontrollant(
                name="Stina Besiktning",
                behorighet=IntygBehorighet.K,
                certification_body="RISE",
                certificate_number="K-1234",
                certificate_valid_to=date(2028, 12, 31),
            ),
            inspection_type=InspectionType.ATERKOMMANDE,
            inspection_date=date(2026, 12, 1),
            building_category=BuildingCategory.FLERBOSTADSHUS,
            issued_date=date(2026, 12, 2),
        )
    )

    item = _by_id(tmp_path)["ovk-klar"]

    assert item["status"] == "utfardad"
    assert item["intyg_id"] == "intyg-1"
    assert item["utfardat"] == "2026-12-02"
    assert item["nasta_steg"] == {"text": "Visa intyg", "href": "/ovk/intyg?project_id=p1"}


def test_unreadable_records_are_reported_not_hidden(tmp_path: Path) -> None:
    OvkWorkflowRepository(tmp_path).save(_record("ovk-1"))
    OvkWorkflowRepository(tmp_path).save(_record("ovk-2"))
    (tmp_path / "projects" / "p1" / "ovk" / "trasig.json").write_text("{", encoding="utf-8")
    broken = tmp_path / "projects" / "p1" / "ovk-field" / "ovk-2" / "snapshot.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("[]", encoding="utf-8")

    body = _client(tmp_path).get("/api/ovk/uppdrag").json()

    assert [item["inspection_id"] for item in body["uppdrag"]] == ["ovk-1"]
    assert body["fullstandig"] is False
    assert body["ej_lasbara"] == [
        {"project_id": "p1", "inspection_id": "ovk-2"},
        {"project_id": "p1", "inspection_id": "trasig"},
    ]


def test_unreadable_certificates_withhold_the_whole_project(tmp_path: Path) -> None:
    OvkWorkflowRepository(tmp_path).save(_record("ovk-1", ready=True))
    directory = tmp_path / "projects" / "p1" / "ovk-intyg"
    directory.mkdir(parents=True)
    (directory / "intyg-1.json").write_text("{", encoding="utf-8")

    body = _client(tmp_path).get("/api/ovk/uppdrag").json()

    assert body["uppdrag"] == []
    assert body["fullstandig"] is False
    assert body["ej_lasbara"] == [{"project_id": "p1", "inspection_id": ""}]


def test_overview_requires_a_session_in_session_mode(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_AUTH_MODE", "session")
    OvkWorkflowRepository(tmp_path).save(_record("ovk-1"))

    response = _client(tmp_path).get("/api/ovk/uppdrag")

    assert response.status_code == 401
    assert response.json() == {"detail": {"code": "AUTHENTICATION_REQUIRED"}}


def test_scope_lists_only_safely_named_project_directories(tmp_path: Path) -> None:
    actor = CustomerContext(customer_id="local-dev")
    assert visible_project_ids(tmp_path, actor) == ()
    for name in ("p2", "p1", "inte säker", ".dold"):
        (tmp_path / "projects" / name).mkdir(parents=True)
    (tmp_path / "projects" / "fil.json").write_text("{}", encoding="utf-8")

    assert visible_project_ids(tmp_path, actor) == ("p1", "p2")


def test_plugin_registers_the_overview(tmp_path: Path) -> None:
    paths = {
        getattr(route, "path", "")
        for router in CrowOvkModulePlugin().routers(tmp_path)
        for route in router.routes
    }
    assert "/api/ovk/uppdrag" in paths
