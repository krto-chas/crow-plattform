from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_module.ovk_field_context_page import ovk_field_context_page_router
from crow_ovk_module.ovk_field_surface import ovk_field_router


def _client(data_root: Path) -> TestClient:
    app = FastAPI()
    app.include_router(ovk_field_context_page_router())
    app.include_router(ovk_field_router(data_root))
    return TestClient(app)


def _field_payload() -> dict[str, object]:
    return {
        "inspection_id": "ovk-1",
        "units": [
            {
                "unit_id": "unit-1",
                "number": "1203",
                "kind": "apartment",
            }
        ],
        "rooms": [
            {
                "room_id": "room-1",
                "unit_id": "unit-1",
                "name": "Badrum",
            }
        ],
        "findings": [
            {
                "finding_id": "finding-1",
                "unit_id": "unit-1",
                "room_id": "room-1",
                "defect_type": "contaminated_extract_terminal",
                "description": "Smutsigt frånluftsdon",
                "severity": "minor",
                "origin": "observed",
            }
        ],
        "photos": [
            {
                "photo_id": "photo-1",
                "unit_id": "unit-1",
                "unit_number": "1203",
                "defect_type": "contaminated_extract_terminal",
                "captured_at": "2026-08-09T00:00:00+02:00",
                "captured_by": "Inspector",
                "local_uri": "indexeddb:image.jpg",
                "sha256": "a" * 64,
                "mime_type": "image/jpeg",
                "room_id": "room-1",
                "finding_id": "finding-1",
                "sync_status": "local",
            }
        ],
    }


def test_field_page_exposes_offline_app_shell(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/ovk/falt?project_id=p1&inspection_id=ovk-001")
    assert response.status_code == 200
    assert "Crow OVK · Fält" in response.text
    assert 'capture="environment"' in response.text
    assert "/ovk/falt/app.js" in response.text
    assert "/ovk/falt/context.js" in response.text
    assert "/ovk/falt/unit-flow.js" in response.text
    assert "/ovk/falt/auth.js" in response.text

    app = client.get("/ovk/falt/app.js")
    assert app.status_code == 200
    assert "indexedDB.open" in app.text
    assert "serviceWorker.register" in app.text
    assert "sync_status:'local'" in app.text
    assert "function crowRandomUuid()" in app.text
    assert "typeof api.getRandomValues==='function'" in app.text
    assert "crypto.randomUUID();" not in app.text
    assert "Typ av enhet: L = lägenhet, O = lokal" in app.text
    assert "Foto kräver HTTPS" in app.text

    context = client.get("/ovk/falt/context.js")
    assert context.status_code == 200
    assert "get('project_id')" in context.text
    assert "get('inspection_id')" in context.text
    assert "const originalRestoreLatest = restoreLatest" in context.text
    assert "const exact = await dbGet('drafts', requestedInspectionId)" in context.text
    assert "exact.project_id === requestedProjectId" in context.text
    assert "state.inspection_id = $('inspection').value.trim()" in context.text
    assert "await originalGenerateHandler()" in context.text
    assert "'/ovk/besiktning' + (query ? '?' + query : '')" in context.text

    unit_flow = client.get("/ovk/falt/unit-flow.js")
    assert unit_flow.status_code == 200
    assert "renderUnitPreview" in unit_flow.text
    assert "addFieldUnit('apartment')" in unit_flow.text
    assert "addFieldUnit('premises')" in unit_flow.text
    assert "openUnit(firstUnit.unit_id)" in unit_flow.text
    assert "confirm(" not in unit_flow.text

    auth = client.get("/ovk/falt/auth.js")
    assert auth.status_code == 200
    assert "class CrowAuthenticationRequired" in auth.text
    assert "credentials: 'same-origin'" in auth.text
    assert "cache: 'no-store'" in auth.text
    assert "'/api/auth/me'" in auth.text
    assert "Sessionen saknas eller har gått ut" in auth.text
    assert "Ronderingen är kvar lokalt" in auth.text

    worker = client.get("/ovk/falt/sw.js")
    assert worker.status_code == 200
    assert worker.headers["service-worker-allowed"] == "/ovk/"
    assert "crow-ovk-field-shell-" in worker.text
    assert "v8" in worker.text
    assert "v7" not in worker.text
    assert "Network-first" in worker.text
    assert worker.headers["cache-control"] == "no-cache"
    assert "const FIELD_PAGE='/ovk/falt'" in worker.text
    assert "'/ovk/falt/context.js'" in worker.text
    assert "'/ovk/falt/unit-flow.js'" in worker.text
    assert "'/ovk/falt/auth.js'" in worker.text
    assert "'/ovk/falt/time.js'" in worker.text
    assert "caches.keys()" in worker.text
    assert "url.pathname===FIELD_PAGE" in worker.text
    assert "response.redirected" in worker.text
    assert "cache.match(FIELD_PAGE)" in worker.text
    assert "STATIC_PATHS.has(url.pathname)" in worker.text
    assert "REFERENCE_PATHS.has(url.pathname)" in worker.text
    assert "/api/projects" not in worker.text


def test_defect_types_are_exposed(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/ovk/field/defect-types")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["defect_types"]}
    assert "contaminated_extract_terminal" in ids


def test_field_payload_validates_photo_unit_and_defect(tmp_path: Path) -> None:
    response = _client(tmp_path).post("/api/ovk/field/validate", json=_field_payload())
    assert response.status_code == 200
    assert response.json() == {
        "inspection_id": "ovk-1",
        "units": 1,
        "rooms": 1,
        "findings": 1,
        "photos": 1,
        "measurements": 0,
        "window_vents": 0,
        "unit_status_counts": {"ej_paborjad": 1, "ua": 0, "anmarkning": 0, "bom": 0},
        "technical_spaces": 0,
        "checkpoints": 0,
        "checkpoint_failures": 0,
        "nameplates_missing": [],
        "coverage_complete": False,
        "valid": True,
    }


def test_field_sync_persists_canonical_snapshot_with_stable_receipt(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = _field_payload()

    first = client.put("/api/ovk/field/sync/ovk-1", json=payload)
    second = client.put("/api/ovk/field/sync/ovk-1", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["snapshot_sha256"] == second.json()["snapshot_sha256"]
    assert first.json()["media_pending"] == 1
    assert first.json()["synced"] is True

    snapshot = tmp_path / "ovk-field-sync" / "ovk-1.json"
    assert snapshot.is_file()
    stored = json.loads(snapshot.read_text(encoding="utf-8"))
    assert stored["inspection_id"] == "ovk-1"
    assert stored["photos"][0]["sync_status"] == "local"

    loaded = client.get("/api/ovk/field/sync/ovk-1")
    assert loaded.status_code == 200
    assert loaded.json()["snapshot_sha256"] == first.json()["snapshot_sha256"]
    assert loaded.json()["payload"] == stored


def test_field_sync_rejects_identifier_mismatch(tmp_path: Path) -> None:
    response = _client(tmp_path).put(
        "/api/ovk/field/sync/ovk-2",
        json=_field_payload(),
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OVK_FIELD_INSPECTION_MISMATCH"


def test_field_payload_rejects_wrong_photo_unit_number(tmp_path: Path) -> None:
    payload = {
        "inspection_id": "ovk-1",
        "units": [{"unit_id": "unit-1", "number": "1203"}],
        "rooms": [],
        "findings": [],
        "photos": [
            {
                "photo_id": "photo-1",
                "unit_id": "unit-1",
                "unit_number": "1303",
                "defect_type": "contaminated_extract_terminal",
                "captured_at": "2026-08-09T00:00:00+02:00",
                "captured_by": "Inspector",
                "local_uri": "indexeddb:image.jpg",
                "sha256": "b" * 64,
                "mime_type": "image/jpeg",
            }
        ],
    }
    response = _client(tmp_path).post("/api/ovk/field/validate", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_OVK_FIELD_DATA"


def test_field_app_marks_visited_rooms_and_clears_bom_units(tmp_path: Path) -> None:
    client = _client(tmp_path)
    app = client.get("/ovk/falt/app.js")
    assert app.status_code == 200
    # Besökta rum: chip får done-klass och räknarbadge per rum.
    assert "function roomStats(roomId)" in app.text
    assert "' done'" in app.text
    assert 'class="rbadge"' in app.text
    # BOM rensar mätningar/anmärkningar lokalt så serverns
    # statuskonsistensvalidering inte avvisar snapshot-synken med 422.
    assert "BOM: '+meas.length+' mätningar" in app.text
    assert (
        "state.measurements=state.measurements.filter(item=>item.unit_id!==unit.unit_id)"
        in app.text
    )
    assert "state.findings=state.findings.filter(item=>item.unit_id!==unit.unit_id)" in app.text
    assert "photo.finding_id=null" in app.text
    # Restore bevarar laddade checklists i båda vägarna,
    # annars skapar "+ Fläktrum" noll kontrollpunkter efter återställning.
    assert app.text.count("checklists:state.checklists") >= 2
    # Läsbara synkfel i stället för rå JSON.
    assert "function crowErrorText(error)" in app.text
    assert "crowErrorText(error)" in app.text
    assert "'Synkfel: '+String(error)" not in app.text
    # Fönsterventilkontroll dedupliceras per rum.
    assert "function setWindowVent(roomId,present)" in app.text

    page = client.get("/ovk/falt")
    assert page.status_code == 200
    assert ".chip.done" in page.text
    assert ".rbadge" in page.text

    auth = client.get("/ovk/falt/auth.js")
    assert auth.status_code == 200
    assert "crowErrorText(error)" in auth.text


def test_field_sync_accepts_bom_unit_without_findings_or_measurements(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload: dict[str, object] = {
        "inspection_id": "ovk-bom",
        "units": [
            {
                "unit_id": "unit-1",
                "number": "1101",
                "kind": "apartment",
                "status": "bom",
                "bom_at": "2026-08-15T09:00:00+02:00",
                "bom_note": "Ingen hemma",
            }
        ],
    }
    response = client.put("/api/ovk/field/sync/ovk-bom", json=payload)
    assert response.status_code == 200
    assert response.json()["synced"] is True


def test_field_surfaces_disable_http_caching(tmp_path: Path) -> None:
    client = _client(tmp_path)
    assert client.get("/ovk/falt").headers["cache-control"] == "no-cache"
    for name in ("app.js", "context.js", "unit-flow.js", "auth.js"):
        assert client.get(f"/ovk/falt/{name}").headers["cache-control"] == "no-cache"


def test_field_app_presets_and_unit_system_override(tmp_path: Path) -> None:
    client = _client(tmp_path)
    app = client.get("/ovk/falt/app.js")
    assert app.status_code == 200
    # Badrum/WC/Kök får automatisk frånluftsmätpunkt när rummet skapas.
    assert "PRESET_EXTRACT_ROOMS=['badrum','wc','kök','hwc','vilorum']" in app.text
    # Avvikande system per enhet (vinds-/källarlägenhet) med fastigheten som default.
    assert "function unitSystem(unit)" in app.text
    assert "system_type:system_type||null" in app.text
    assert "unitSystemBtn" in app.text
    # Nytt besiktnings-ID startar tom session i stället för att ärva gammal data.
    assert "Starta ny tom besiktning" in app.text
    assert "updateViaCache:'none'" in app.text

    page = client.get("/ovk/falt")
    assert 'id="unitSystemBtn"' in page.text


def test_field_sync_roundtrips_unit_system_type(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = _field_payload()
    units = payload["units"]
    assert isinstance(units, list)
    units[0]["system_type"] = "FTX"
    response = client.put("/api/ovk/field/sync/ovk-1", json=payload)
    assert response.status_code == 200
    stored = client.get("/api/ovk/field/sync/ovk-1").json()
    assert stored["payload"]["units"][0]["system_type"] == "FTX"

    units[0]["system_type"] = "FTZ"
    rejected = client.put("/api/ovk/field/sync/ovk-1", json=payload)
    assert rejected.status_code == 422


def test_field_app_pass103_flows(tmp_path: Path) -> None:
    client = _client(tmp_path)
    app = client.get("/ovk/falt/app.js")
    assert app.status_code == 200
    # Besiktningsmannadropdown från registret, med offline-cache och fritext kvar.
    assert "function fillInspectors(persons)" in app.text
    assert "/api/ovk/registry/besiktningsman" in app.text
    # Objektstyp styr flödet: icke-flerbostadshus går direkt in i objektet.
    assert "object_type: 'flerbostadshus'" in app.text
    assert "state.object_type!=='flerbostadshus'" in app.text
    assert "async function prefillObjectType()" in app.text
    # 0/1/2-klassning vid anmärkning, klass styr severity (EG-logik).
    assert "const classification=severity==='major'?2:severity==='minor'?1:0;" in app.text
    assert "finding.classification=cls" in app.text
    # Banner för föregående besiktnings fel per enhet.
    assert "prevFindings" in app.text
    assert "anmärkning(ar) vid föregående besiktning" in app.text

    page = client.get("/ovk/falt")
    assert 'id="inspectorSelect"' in page.text
    assert 'id="objectType"' in page.text
    assert 'data-class="2"' in page.text
    assert 'id="prevFindings"' in page.text

    unit_flow = client.get("/ovk/falt/unit-flow.js")
    assert "parseSeries(text)" in unit_flow.text
    assert "1101-1104, 1201" in unit_flow.text


def test_field_sync_roundtrips_finding_classification(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = _field_payload()
    findings = payload.setdefault("findings", [])
    assert isinstance(findings, list)
    findings.append(
        {
            "finding_id": "f-cls",
            "unit_id": "unit-1",
            "defect_type": "contaminated_extract_terminal",
            "description": "Skitig ventil i bad",
            "severity": "minor",
            "classification": 1,
        }
    )
    response = client.put("/api/ovk/field/sync/ovk-1", json=payload)
    assert response.status_code == 200, response.text
    stored = client.get("/api/ovk/field/sync/ovk-1").json()
    saved = [item for item in stored["payload"]["findings"] if item["finding_id"] == "f-cls"]
    assert saved[0]["classification"] == 1

    findings[-1]["classification"] = 5
    rejected = client.put("/api/ovk/field/sync/ovk-1", json=payload)
    assert rejected.status_code == 422


def test_field_sync_accepts_pending_measurement_points(tmp_path: Path) -> None:
    """Synk är arbetsläge: preset-mätpunkt utan värde får aldrig fälla synken."""
    client = _client(tmp_path)
    payload = _field_payload()
    measurements = payload.setdefault("measurements", [])
    assert isinstance(measurements, list)
    measurements.append(
        {
            "measurement_id": "meas-pending",
            "unit_id": "unit-1",
            "point_type": "franluftsdon",
            "point_label": "Badrum 1",
            "measurable": True,
            "measured_value": None,
        }
    )
    response = client.put("/api/ovk/field/sync/ovk-1", json=payload)
    assert response.status_code == 200, response.text

    # Ej mätbar utan orsak avvisas fortfarande — det kravet är inte arbetsläge.
    measurements.append(
        {
            "measurement_id": "meas-bad",
            "unit_id": "unit-1",
            "point_type": "franluftsdon",
            "point_label": "Kök 1",
            "measurable": False,
            "not_measurable_reason": "",
        }
    )
    rejected = client.put("/api/ovk/field/sync/ovk-1", json=payload)
    assert rejected.status_code == 422


def test_field_app_shows_session_status(tmp_path: Path) -> None:
    client = _client(tmp_path)
    page = client.get("/ovk/falt")
    assert 'id="authStatus"' in page.text
    app = client.get("/ovk/falt/app.js")
    assert "/api/auth/me" in app.text
    assert "Ej inloggad" in app.text
    auth = client.get("/ovk/falt/auth.js")
    assert "Sessionen har gått ut" in auth.text
