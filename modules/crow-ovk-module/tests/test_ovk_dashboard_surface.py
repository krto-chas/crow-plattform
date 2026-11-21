from __future__ import annotations

import json
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook

from crow_ovk_module.ovk_dashboard_surface import ovk_dashboard_router


def _client(root: Path) -> TestClient:
    app = FastAPI()
    app.include_router(ovk_dashboard_router(root))
    return TestClient(app)


def _legacy_xlsx() -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "OVK"
    worksheet.append(["OVK besiktning 2024-05-14"])
    worksheet.append(["System FTX01, uppmätt 34 l/s, projekterat 40 l/s"])
    worksheet.append(["Anmärkning: Smutsigt filter"])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_dashboard_is_operational_project_surface(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/ovk")

    assert response.status_code == 200
    assert "<h1>Översikt</h1>" in response.text
    assert "OVK-besiktningar" in response.text
    assert "Projektfiler" in response.text
    assert "/api/projects/" in response.text
    assert "/ovk/legacy?project_id=" in response.text
    assert 'id="newInspection"' in response.text
    assert 'id="inspectionSearch"' in response.text
    assert 'id="inspectionFilter"' in response.text
    assert 'id="readyCount"' in response.text


def test_overview_is_a_work_queue_fed_by_the_assignment_route(tmp_path: Path) -> None:
    client = _client(tmp_path)
    page = client.get("/ovk").text

    for element in (
        'id="queue"',
        'id="overviewSearch"',
        'id="overviewFilter"',
        'id="overviewStatus"',
        'id="overviewWarning"',
        'id="overviewItems"',
        'id="overviewEmpty"',
        'id="refreshOverview"',
    ):
        assert element in page
    assert page.index('<script src="/ovk/skal.js">') < page.index("ovkShell?.mount()")
    assert page.index('<script src="/ovk/oversikt.js">') < page.index("ovkOverview.init()")

    script = client.get("/ovk/oversikt.js")
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/javascript")
    assert "/api/ovk/uppdrag" in script.text
    # Den gamla översikten hämtade besiktningar projekt för projekt i webbläsaren.
    assert "/inspections" not in script.text
    assert "innerHTML" not in script.text


def test_desktop_overview_and_mobile_home_load_separately(tmp_path: Path) -> None:
    page = _client(tmp_path).get("/ovk").text

    assert (
        "return mobileView.matches||!window.ovkOverview?loadOverview():ovkOverview.load();" in page
    )
    # Byte av fönsterbredd laddar inget förrän init har hämtat projekten.
    assert "if(projectsReady)startOverview();" in page
    # Mobilens startsida behåller sin egen väg och sina element.
    for element in ('id="fieldHomeStatus"', 'id="fieldOngoing"', 'id="fieldPrepared"'):
        assert element in page
    assert "renderFieldHome(rows,revision,failed)" in page


def test_shell_navigation_has_the_eight_workspaces(tmp_path: Path) -> None:
    client = _client(tmp_path)
    page = client.get("/ovk").text
    script = client.get("/ovk/skal.js")

    # Kärnan ersätter sidans första <nav> med plattformens moduler; OVK:s
    # navigation måste därför vara en egen, andra <nav>.
    assert page.index("<nav>") < page.index('<nav aria-label="OVK-navigation" id="ovkNav">')
    assert script.status_code == 200
    labels = [
        "Översikt och arbetskö",
        "Uppdrag och planering",
        "Kunder och fastigheter",
        "Besiktningar och uppföljning",
        "Granskning",
        "Protokoll, intyg och bilagor",
        "Bevakning och ombesiktningar",
        "Administration och inställningar",
    ]
    positions = [script.text.index(f"text: '{label}'") for label in labels]
    assert positions == sorted(positions)
    assert script.text.count("{ id: '") == len(labels)


def test_workbench_import_can_be_previewed_without_reupload(tmp_path: Path) -> None:
    content = _legacy_xlsx()
    digest = sha256(content).hexdigest()
    project_id = "demo"
    filename = "gammalt-ovk.xlsx"

    source = tmp_path / "uploads" / project_id / filename
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(content)

    manifest = tmp_path / "projects" / project_id / "imports" / f"{digest}.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "filename": filename,
                "format_id": "xlsx",
                "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "checksum_sha256": digest,
            }
        ),
        encoding="utf-8",
    )

    response = _client(tmp_path).get(
        f"/api/ovk/projects/{project_id}/legacy-assets/{digest}/preview"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == project_id
    assert payload["filename"] == filename
    assert payload["source_sha256"] == digest
    assert any(item["field"] == "inspection_date" for item in payload["facts"])
    assert any(
        item["field"] == "system_id" and item["value"] == "FTX01" for item in payload["facts"]
    )
    assert any(item["field"] == "finding" for item in payload["facts"])


def test_mobile_home_preserves_field_and_project_entry_points(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/ovk")

    assert response.status_code == 200
    assert 'id="fieldHomeTitle">Besiktningar' in response.text
    assert 'href="/ovk/besiktning?new=1">+ Ny besiktning' in response.text
    assert 'href="/ovk/falt">Fortsätt besikta' in response.text
    assert 'id="fieldOngoing" hidden' in response.text
    assert 'id="fieldPrepared" hidden' in response.text
    assert 'id="desktopTools" open' in response.text
    assert "OVK_FIELD_SNAPSHOT_NOT_FOUND" in response.text
    assert "data.project_id===project.project_id" in response.text
    assert "data.inspection_id===item.inspection_id" in response.text
    assert "item.planning&&!item.protocol_ready" in response.text
