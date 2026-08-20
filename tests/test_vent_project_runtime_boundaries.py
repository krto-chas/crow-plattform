from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crow_workbench.shell import create_app


def _enable_vent(root: Path) -> None:
    target = root / "config" / "customers" / "acme"
    target.mkdir(parents=True, exist_ok=True)
    (target / "entitlements.json").write_text(
        json.dumps({"customer_id": "acme", "modules": [{"id": "vent", "active": True}]}),
        encoding="utf-8",
    )


def test_vent_drawing_model_rejects_invalid_checksum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    _enable_vent(tmp_path)
    client = TestClient(create_app(tmp_path))

    response = client.get("/api/vent/projects/demo/drawings/not-a-checksum/model")

    assert response.status_code == 400
    assert response.json()["detail"] == "Ogiltig checksumma"


def test_vent_drawing_model_rejects_non_object_import_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CROW_CUSTOMER_ID", "acme")
    _enable_vent(tmp_path)
    checksum = "a" * 64
    project = tmp_path / "projects" / "demo"
    imports = project / "imports"
    imports.mkdir(parents=True)
    (project / "crow-project.json").write_text("{}", encoding="utf-8")
    (imports / f"{checksum}.json").write_text("[]", encoding="utf-8")
    client = TestClient(create_app(tmp_path))

    response = client.get(f"/api/vent/projects/demo/drawings/{checksum}/model")

    assert response.status_code == 500
    assert response.json()["detail"] == "Ogiltigt importmanifest"
