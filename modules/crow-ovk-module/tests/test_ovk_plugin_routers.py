from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from crow_ovk_module.plugin import CrowOvkModulePlugin


def _registered_paths(data_root: Path) -> set[str]:
    plugin = CrowOvkModulePlugin()
    paths: set[str] = set()
    for router in plugin.routers(data_root):
        for route in router.routes:
            paths.add(getattr(route, "path", ""))
    return paths


def test_plugin_registers_export_surface(tmp_path: Path) -> None:
    """PDF-exporten (pass 100) föll ur plugin.py i en konfliktlösning.

    Detta test låser att sign/nedladdningsytan alltid är monterad.
    """
    paths = _registered_paths(tmp_path)
    assert "/api/ovk/projects/{project_id}/export/{kind}/{document_id}/sign" in paths
    assert "/api/ovk/export/{project_id}/{kind}/{document_id}.pdf" in paths


def test_plugin_registers_field_and_workflow_surfaces(tmp_path: Path) -> None:
    paths = _registered_paths(tmp_path)
    assert "/ovk/falt" in paths
    base = "/api/ovk/projects/{project_id}/field/{inspection_id}"
    for suffix in ("sync", "context", "history", "workbench", "media/{photo_id}"):
        assert f"{base}/{suffix}" in paths
    assert {path for path in paths if path.startswith("/api/ovk/field/")} == {
        "/api/ovk/field/checklists",
        "/api/ovk/field/defect-types",
        "/api/ovk/field/validate",
    }
    assert not any(path.endswith("/field-history") for path in paths)


def test_production_legacy_field_routes_are_unreachable(tmp_path: Path) -> None:
    app = FastAPI()
    for router in CrowOvkModulePlugin().routers(tmp_path):
        app.include_router(router)
    client = TestClient(app)
    for suffix in (
        "sync/ovk-1",
        "context/ovk-1",
        "media/ovk-1/photo-1",
        "media/ovk-1/photo-1/content",
        "workbench/ovk-1",
        "history/ovk-1",
        "history",
    ):
        url = f"/api/ovk/field/{suffix}"
        assert client.get(url).status_code == 404
        assert client.put(url, json={}).status_code == 404
    assert client.get("/api/ovk/field/checklists").status_code == 200


def test_plugin_registers_fastighet_surface(tmp_path: Path) -> None:
    paths = _registered_paths(tmp_path)
    assert "/ovk/fastighet" in paths
    assert "/api/ovk/projects/{project_id}/fastighet/{fastighet_id}" in paths
    assert "/api/ovk/registry/besiktningsman/{besiktningsman_id}" in paths


def test_plugin_registers_protokoll_surface(tmp_path: Path) -> None:
    paths = _registered_paths(tmp_path)
    assert "/api/ovk/projects/{project_id}/field/{inspection_id}/protokoll-utkast" in paths
