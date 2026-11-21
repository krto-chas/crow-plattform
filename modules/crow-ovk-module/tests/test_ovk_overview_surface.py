"""Uppdragsöversikten: härledd status, nästa steg och redovisade läsfel."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

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
from crow_ovk import (
    CheckStatus,
    FindingSeverity,
    OvkCheckpoint,
    OvkFinding,
    OvkObject,
    VentilationSystemRef,
)
from crow_ovk_intyg import Behorighet as IntygBehorighet
from crow_ovk_intyg import (
    Byggnadsagare,
    Funktionskontrollant,
    OvkIntyg,
    OvkIntygRepository,
    build_intyg,
    intyg_to_payload,
)
from crow_ovk_module.ovk_overview_surface import (
    STATUS_LABELS,
    derive_status,
    ovk_overview_router,
)
from crow_ovk_module.ovk_protocol_source import save_protocol_source
from crow_ovk_module.ovk_scope import visible_project_ids
from crow_ovk_module.plugin import CrowOvkModulePlugin
from crow_ovk_pricing import BuildingCategory, InspectionType
from crow_ovk_workflow import (
    AggregatCoverage,
    AggregatStatus,
    BekraftelseRoll,
    CaseStatus,
    InspectionCoverage,
    OvkReinspectionRepository,
    OvkWorkflowRecord,
    OvkWorkflowRepository,
    SystemForteckningBekraftelse,
    build_record,
    open_case,
)
from crow_ovk_workflow.models import InspectionPlanning
from crow_workbench.shell import create_app

_PLANNING = InspectionPlanning("stina-b", date(2026, 12, 1), "aterkommande")
_DONE = "2026-11-20T15:30:00.000Z"


def _client(root: Path) -> TestClient:
    app = FastAPI()
    app.include_router(ovk_overview_router(root))
    return TestClient(app)


def _record(
    inspection_id: str,
    *,
    project_id: str = "p1",
    ready: bool = False,
    deficient: bool = False,
    planning: InspectionPlanning | None = _PLANNING,
) -> OvkWorkflowRecord:
    systems = (VentilationSystemRef("FTX01", "FTX", "System FTX01"),)
    obj = OvkObject("object-1", project_id, "building-1", "Kv. Lärkan", address="Storgatan 1")
    if not (ready or deficient):
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
                status=CheckStatus.FAIL if deficient else CheckStatus.PASS,
                system_id="FTX01",
            ),
        ),
        findings=(
            (
                OvkFinding(
                    finding_id="f1",
                    description="Otillräckligt frånluftsflöde i kök",
                    severity=FindingSeverity.MAJOR,
                    system_id="FTX01",
                ),
            )
            if deficient
            else ()
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


def _snapshot(
    root: Path, inspection_id: str, *, completed: str | None = None, project_id: str = "p1"
) -> Path:
    path = root / "projects" / project_id / "ovk-field" / inspection_id / "snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"inspection_id": inspection_id, "units": []}
    if completed is not None:
        payload["field_work_completed_at"] = completed
    path.write_text(json.dumps(payload), encoding="utf-8")
    (path.parent / "context.json").write_text(
        json.dumps({"inspection_id": inspection_id, "project_id": project_id}), encoding="utf-8"
    )
    return path


def _digest(intyg: OvkIntyg) -> str:
    canonical = json.dumps(
        intyg_to_payload(intyg), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _issue(root: Path, record: OvkWorkflowRecord, intyg_id: str = "intyg-1") -> OvkIntyg:
    """Utfärdar som produktionsvägen lämnar det: manifest först, sedan intyg."""
    inspection_id = record.inspection.inspection_id
    project_id = record.inspection.ovk_object.project_id
    intyg = build_intyg(
        intyg_id=intyg_id,
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
    manifest = root / "projects" / project_id / "ovk-issuance-manifest" / f"{inspection_id}.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "project_id": project_id,
                "inspection_id": inspection_id,
                "intyg_id": intyg_id,
                "intyg_sha256": _digest(intyg),
            }
        ),
        encoding="utf-8",
    )
    OvkIntygRepository(root).save(intyg)
    return intyg


def _body(root: Path) -> dict[str, Any]:
    response = _client(root).get("/api/ovk/uppdrag")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def _by_id(root: Path) -> dict[str, dict[str, Any]]:
    items: list[dict[str, Any]] = _body(root)["uppdrag"]
    return {str(item["inspection_id"]): item for item in items}


_DEFAULTS: dict[str, object] = {
    "planned": False,
    "has_snapshot": False,
    "field_completed": False,
    "ready_to_issue": False,
    "issuance_interrupted": False,
    "issued": False,
    "deficiencies": False,
    "reinspection": None,
}


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({}, "ej_planerad"),
        ({"planned": True}, "planerad"),
        ({"planned": True, "has_snapshot": True}, "pagaende"),
        ({"has_snapshot": True, "ready_to_issue": True}, "att_granska"),
        ({"has_snapshot": True, "field_completed": True}, "att_granska"),
        ({"has_snapshot": True, "field_completed": True, "ready_to_issue": True}, "leveransklar"),
        ({"ready_to_issue": True}, "leveransklar"),
        ({"ready_to_issue": True, "issuance_interrupted": True}, "utfardande_avbrutet"),
        ({"issued": True}, "utfardad"),
        ({"issued": True, "issuance_interrupted": True}, "utfardad"),
        ({"issued": True, "deficiencies": True}, "atgarder_oppna"),
        ({"issued": True, "deficiencies": True, "reinspection": CaseStatus.OPEN}, "ombesiktning"),
        ({"issued": True, "deficiencies": True, "reinspection": CaseStatus.READY}, "ombesiktning"),
        ({"issued": True, "deficiencies": True, "reinspection": CaseStatus.CLOSED}, "utfardad"),
    ],
)
def test_status_is_derived_from_existing_facts(flags: dict[str, object], expected: str) -> None:
    assert derive_status(**{**_DEFAULTS, **flags}) == expected  # type: ignore[arg-type]
    assert expected in STATUS_LABELS


def test_empty_data_root_is_a_complete_empty_overview(tmp_path: Path) -> None:
    body = _body(tmp_path)
    assert body["uppdrag"] == []
    assert body["fullstandig"] is True
    assert body["ej_lasbara"] == []
    counts: dict[str, int] = body["antal"]
    assert set(counts) == set(STATUS_LABELS)
    assert not any(counts.values())


def test_overview_follows_the_assignment_through_the_field(tmp_path: Path) -> None:
    workflows = OvkWorkflowRepository(tmp_path)
    for name in ("ovk-planerad", "ovk-pagaende", "ovk-granska"):
        workflows.save(_record(name))
    workflows.save(_record("ovk-klar", ready=True))
    workflows.save(_record("ovk-utkast", planning=None))
    _snapshot(tmp_path, "ovk-pagaende")
    _snapshot(tmp_path, "ovk-granska", completed=_DONE)

    items = _by_id(tmp_path)

    assert items["ovk-planerad"]["status"] == "planerad"
    assert items["ovk-planerad"]["falt"] == {
        "synkad": False,
        "ogonblicksbild_andrad": None,
        "avslutat": None,
    }
    assert items["ovk-pagaende"]["status"] == "pagaende"
    assert items["ovk-granska"]["status"] == "att_granska"
    assert items["ovk-granska"]["falt"]["avslutat"] == _DONE
    assert items["ovk-klar"]["status"] == "leveransklar"
    assert items["ovk-klar"]["tackning_klar"] is True
    assert items["ovk-utkast"]["status"] == "ej_planerad"
    assert items["ovk-utkast"]["planerat_datum"] is None

    counts: dict[str, int] = _body(tmp_path)["antal"]
    assert counts["planerad"] == 1
    assert counts["leveransklar"] == 1
    assert sum(counts.values()) == 5


def test_leveransklar_requires_a_current_protocol_source(tmp_path: Path) -> None:
    record = _record("ovk-1", ready=True)
    OvkWorkflowRepository(tmp_path).save(record)
    snapshot = _snapshot(tmp_path, "ovk-1", completed=_DONE)
    save_protocol_source(tmp_path, "p1", "ovk-1", record)

    assert _by_id(tmp_path)["ovk-1"]["status"] == "leveransklar"

    # Fältet synkar igen efter att protokollutkastet byggdes. Utfärdandet
    # skulle nu svara OVK_PROTOCOL_SOURCE_STALE.
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    payload["field_work_note"] = "1002 ej tillgänglig."
    snapshot.write_text(json.dumps(payload), encoding="utf-8")

    item = _by_id(tmp_path)["ovk-1"]
    assert item["status"] == "att_granska"
    assert item["nasta_steg"]["text"] == "Granska"


def test_protocol_ready_record_without_completed_field_work_goes_to_review(
    tmp_path: Path,
) -> None:
    record = _record("ovk-1", ready=True)
    OvkWorkflowRepository(tmp_path).save(record)
    _snapshot(tmp_path, "ovk-1")
    save_protocol_source(tmp_path, "p1", "ovk-1", record)

    item = _by_id(tmp_path)["ovk-1"]

    assert item["status"] == "att_granska"
    assert item["nasta_steg"]["text"] == "Granska"


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


def test_assignments_from_several_projects_are_listed_together(tmp_path: Path) -> None:
    workflows = OvkWorkflowRepository(tmp_path)
    workflows.save(_record("ovk-a", project_id="p1"))
    workflows.save(_record("ovk-b", project_id="p2"))
    _snapshot(tmp_path, "ovk-b", project_id="p2")

    items = _by_id(tmp_path)

    assert items["ovk-a"]["project_id"] == "p1"
    assert items["ovk-a"]["status"] == "planerad"
    assert items["ovk-b"]["project_id"] == "p2"
    assert items["ovk-b"]["status"] == "pagaende"


def test_issued_certificate_moves_the_assignment_to_utfardad(tmp_path: Path) -> None:
    record = _record("ovk-klar", ready=True)
    OvkWorkflowRepository(tmp_path).save(record)
    _issue(tmp_path, record)

    item = _by_id(tmp_path)["ovk-klar"]

    assert item["status"] == "utfardad"
    assert item["intyg_id"] == "intyg-1"
    assert item["utfardat"] == "2026-12-02"
    assert item["nasta_steg"] == {
        "text": "Visa intyg",
        "href": "/ovk/intyg?project_id=p1&inspection_id=ovk-klar",
    }


def test_corrected_certificate_is_the_one_shown(tmp_path: Path) -> None:
    record = _record("ovk-klar", ready=True)
    OvkWorkflowRepository(tmp_path).save(record)
    original = _issue(tmp_path, record)
    # Rättelseflödet ger ersättaren samma datum och ett id som sorteras före
    # originalets. Urvalet får inte bero på id-strängen.
    replacement = replace(original, intyg_id="correction-0001")
    OvkIntygRepository(tmp_path).save(replacement)
    root = tmp_path / "projects" / "p1"
    manifest = root / "ovk-issuance-manifest" / "ovk-klar.json"
    corrections = root / "ovk-correction-manifests"
    corrections.mkdir()
    (corrections / "intyg-1.json").write_text(
        json.dumps(
            {
                "project_id": "p1",
                "inspection_id": "ovk-klar",
                "original_intyg_id": "intyg-1",
                "original_sha256": _digest(original),
                "original_manifest_sha256": sha256(manifest.read_bytes()).hexdigest(),
                "replacement_intyg_id": "correction-0001",
                "replacement_sha256": _digest(replacement),
            }
        ),
        encoding="utf-8",
    )

    item = _by_id(tmp_path)["ovk-klar"]

    assert item["status"] == "utfardad"
    assert item["intyg_id"] == "correction-0001"


def test_certificate_without_valid_manifest_is_not_shown_as_issued(tmp_path: Path) -> None:
    record = _record("ovk-klar", ready=True)
    OvkWorkflowRepository(tmp_path).save(record)
    _issue(tmp_path, record)
    (tmp_path / "projects" / "p1" / "ovk-issuance-manifest" / "ovk-klar.json").unlink()

    body = _body(tmp_path)

    assert body["uppdrag"] == []
    assert body["ej_lasbara"] == [
        {"project_id": "p1", "inspection_id": "ovk-klar", "orsak": "intyg"}
    ]


def test_manifest_without_certificate_is_an_interrupted_issuance(tmp_path: Path) -> None:
    record = _record("ovk-klar", ready=True)
    OvkWorkflowRepository(tmp_path).save(record)
    manifest = tmp_path / "projects" / "p1" / "ovk-issuance-manifest" / "ovk-klar.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")

    item = _by_id(tmp_path)["ovk-klar"]

    assert item["status"] == "utfardande_avbrutet"
    assert item["nasta_steg"]["text"] == "Återuppta utfärdandet"


def test_deficiencies_follow_the_reinspection_case(tmp_path: Path) -> None:
    record = _record("ovk-brist", deficient=True)
    OvkWorkflowRepository(tmp_path).save(record)
    _issue(tmp_path, record)

    assert _by_id(tmp_path)["ovk-brist"]["status"] == "atgarder_oppna"

    cases = OvkReinspectionRepository(tmp_path)
    case = open_case(record, case_id="case-1", opened_at="2026-12-03T08:00:00+00:00")
    cases.save(case)

    item = _by_id(tmp_path)["ovk-brist"]
    assert item["status"] == "ombesiktning"
    assert item["nasta_steg"]["text"] == "Följ ombesiktning"

    # Det senast öppnade ärendet avgör, inte det första.
    cases.save(
        replace(case, closed_at="2026-12-10T08:00:00+00:00", result_inspection_id="ovk-ombes")
    )
    assert _by_id(tmp_path)["ovk-brist"]["status"] == "utfardad"
    cases.save(replace(case, case_id="case-2", opened_at="2026-12-11T08:00:00+00:00"))
    assert _by_id(tmp_path)["ovk-brist"]["status"] == "ombesiktning"


def test_unreadable_records_are_reported_not_hidden(tmp_path: Path) -> None:
    workflows = OvkWorkflowRepository(tmp_path)
    for name in ("ovk-1", "ovk-2", "ovk-3"):
        workflows.save(_record(name))
    (tmp_path / "projects" / "p1" / "ovk" / "trasig.json").write_text("{", encoding="utf-8")
    _snapshot(tmp_path, "ovk-2").write_text("[]", encoding="utf-8")
    legacy = tmp_path / "ovk-field-sync" / "ovk-3.json"
    legacy.parent.mkdir()
    legacy.write_text("{}", encoding="utf-8")

    body = _body(tmp_path)

    assert [item["inspection_id"] for item in body["uppdrag"]] == ["ovk-1"]
    assert body["fullstandig"] is False
    assert body["ej_lasbara"] == [
        {"project_id": "p1", "inspection_id": "ovk-2", "orsak": "falt"},
        {"project_id": "p1", "inspection_id": "ovk-3", "orsak": "omigrerad"},
        {"project_id": "p1", "inspection_id": "trasig", "orsak": "post"},
    ]


def test_legacy_field_data_of_another_project_does_not_hide_the_assignment(
    tmp_path: Path,
) -> None:
    workflows = OvkWorkflowRepository(tmp_path)
    workflows.save(_record("ovk-1", project_id="p1"))
    workflows.save(_record("ovk-1", project_id="p2"))
    legacy = tmp_path / "ovk-field-sync" / "ovk-1.json"
    legacy.parent.mkdir()
    legacy.write_text("{}", encoding="utf-8")
    context = tmp_path / "ovk-field-context" / "ovk-1.json"
    context.parent.mkdir()
    context.write_text(json.dumps({"project_id": "p2"}), encoding="utf-8")

    body = _body(tmp_path)

    assert [item["project_id"] for item in body["uppdrag"]] == ["p1"]
    assert body["ej_lasbara"] == [
        {"project_id": "p2", "inspection_id": "ovk-1", "orsak": "omigrerad"}
    ]


def test_snapshot_of_another_inspection_is_not_read_as_this_one(tmp_path: Path) -> None:
    OvkWorkflowRepository(tmp_path).save(_record("ovk-1"))
    _snapshot(tmp_path, "ovk-1").write_text(
        json.dumps({"inspection_id": "ovk-2", "field_work_completed_at": _DONE}),
        encoding="utf-8",
    )

    body = _body(tmp_path)

    assert body["uppdrag"] == []
    assert body["ej_lasbara"] == [{"project_id": "p1", "inspection_id": "ovk-1", "orsak": "falt"}]


def test_certificate_claiming_another_project_withholds_the_project(tmp_path: Path) -> None:
    record = _record("ovk-klar", ready=True)
    OvkWorkflowRepository(tmp_path).save(record)
    issued = _issue(tmp_path, record)
    path = tmp_path / "projects" / "p1" / "ovk-intyg" / "intyg-1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["project_id"] == issued.project_id
    payload["project_id"] = "p2"
    path.write_text(json.dumps(payload), encoding="utf-8")

    body = _body(tmp_path)

    assert body["uppdrag"] == []
    assert body["ej_lasbara"] == [{"project_id": "p1", "inspection_id": "", "orsak": "intyg"}]


def test_record_whose_content_points_elsewhere_is_not_followed(tmp_path: Path) -> None:
    OvkWorkflowRepository(tmp_path).save(_record("ovk-1"))
    OvkWorkflowRepository(tmp_path).save(_record("hemlig", project_id="p2"))
    _snapshot(tmp_path, "hemlig", completed=_DONE, project_id="p2")
    directory = tmp_path / "projects" / "p1" / "ovk"
    stored = json.loads((directory / "ovk-1.json").read_text(encoding="utf-8"))

    other_id = json.loads(json.dumps(stored))
    other_id["inspection"]["inspection_id"] = "../../p2/ovk-field/hemlig"
    (directory / "fel-id.json").write_text(json.dumps(other_id), encoding="utf-8")
    other_project = json.loads(json.dumps(stored))
    other_project["inspection"]["inspection_id"] = "fel-projekt"
    other_project["inspection"]["object"]["project_id"] = "p2"
    (directory / "fel-projekt.json").write_text(json.dumps(other_project), encoding="utf-8")

    body = _body(tmp_path)

    assert sorted(item["inspection_id"] for item in body["uppdrag"]) == [
        "hemlig",
        "ovk-1",
    ]
    assert body["ej_lasbara"] == [
        {"project_id": "p1", "inspection_id": "fel-id", "orsak": "identitet"},
        {"project_id": "p1", "inspection_id": "fel-projekt", "orsak": "identitet"},
    ]


@pytest.mark.parametrize(
    ("directory", "reason"),
    [("ovk-intyg", "projekt"), ("fastighet", "projekt"), ("ovk-ombesiktning", "projekt")],
)
def test_unreadable_project_registers_withhold_the_whole_project(
    tmp_path: Path, directory: str, reason: str
) -> None:
    OvkWorkflowRepository(tmp_path).save(_record("ovk-1", ready=True))
    OvkWorkflowRepository(tmp_path).save(_record("ovk-2", project_id="p2"))
    target = tmp_path / "projects" / "p1" / directory
    target.mkdir(parents=True)
    (target / "trasig.json").write_text("{", encoding="utf-8")

    body = _body(tmp_path)

    assert [item["inspection_id"] for item in body["uppdrag"]] == ["ovk-2"]
    assert body["fullstandig"] is False
    assert body["ej_lasbara"] == [{"project_id": "p1", "inspection_id": "", "orsak": reason}]


def test_overview_requires_a_session_in_session_mode(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_AUTH_MODE", "session")
    OvkWorkflowRepository(tmp_path).save(_record("ovk-1"))

    response = _client(tmp_path).get("/api/ovk/uppdrag")

    assert response.status_code == 401
    assert response.json() == {"detail": {"code": "AUTHENTICATION_REQUIRED"}}


def _entitle(root: Path, *, active: bool) -> None:
    target = root / "config" / "customers" / "acme"
    target.mkdir(parents=True, exist_ok=True)
    (target / "entitlements.json").write_text(
        json.dumps({"customer_id": "acme", "modules": [{"id": "ovk", "active": active}]}),
        encoding="utf-8",
    )


def test_overview_is_served_through_the_platform_shell(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.delenv("CROW_AUTH_MODE", raising=False)
    monkeypatch.setenv("CROW_MODE", "local")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    _entitle(tmp_path, active=True)
    OvkWorkflowRepository(tmp_path).save(_record("ovk-1"))

    response = TestClient(create_app(tmp_path)).get("/api/ovk/uppdrag")

    assert response.status_code == 200
    assert [item["inspection_id"] for item in response.json()["uppdrag"]] == ["ovk-1"]


def test_shell_refuses_the_overview_without_an_ovk_licence(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.delenv("CROW_AUTH_MODE", raising=False)
    monkeypatch.setenv("CROW_MODE", "local")
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    _entitle(tmp_path, active=False)

    response = TestClient(create_app(tmp_path)).get("/api/ovk/uppdrag")

    assert response.status_code == 403
    assert response.json()["detail"] == {"code": "MODULE_NOT_ACTIVE", "module": "ovk"}


def test_shell_refuses_the_overview_without_a_session(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_AUTH_MODE", "session")
    _entitle(tmp_path, active=True)

    response = TestClient(create_app(tmp_path)).get("/api/ovk/uppdrag")

    assert response.status_code == 401


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
