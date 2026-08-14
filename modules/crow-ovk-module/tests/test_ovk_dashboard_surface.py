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
    assert "OVK-arbetsyta" in response.text
    assert "OVK-besiktningar" in response.text
    assert "Projektfiler" in response.text
    assert "/api/projects/" in response.text
    assert "/ovk/legacy?project_id=" in response.text


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
