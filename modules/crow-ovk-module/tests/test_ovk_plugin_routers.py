from __future__ import annotations

from pathlib import Path

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
    assert "/api/ovk/field/sync/{inspection_id}" in paths
    assert "/api/ovk/field/context/{inspection_id}" in paths
    assert "/api/ovk/field/history" in paths
