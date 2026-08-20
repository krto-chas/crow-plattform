from pathlib import Path

from fastapi import FastAPI

from crow_module_sdk.module_registry import ModuleRegistry
from crow_module_sdk.web import CrowWebModule
from crow_workbench.shell import create_app


def test_first_party_domain_modules_are_discoverable() -> None:
    registry = ModuleRegistry()
    registered = registry.discover()
    by_id = {item.module_id: item for item in registered}

    assert {"crow.vent", "crow.provtryckning", "crow.ovk"} <= set(by_id)
    for module_id in ("crow.vent", "crow.provtryckning", "crow.ovk"):
        assert isinstance(by_id[module_id].plugin, CrowWebModule)


def test_workbench_mounts_module_routes_from_registry(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    paths = set(app.openapi()["paths"])

    assert "/vent" in paths
    assert "/api/vent/registry" in paths
    assert "/api/vent/projects/{project_id}/drawings/{checksum}/model" in paths
    assert "/api/vent/projects/{project_id}/drawings/{checksum}/quantity.csv" in paths
    assert "/api/vent/projects/{project_id}/drawings/{checksum}/review" in paths
    assert "/api/vent/projects/{project_id}/takeoff" in paths
    assert "/api/vent/projects/{project_id}/quote" in paths
    assert "/provtryckning" in paths
    assert "/ovk" in paths
    assert "/ovk/besiktning" in paths
    assert "/ovk/falt" in paths


def test_platform_composes_vent_product_routes_from_module(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    expected = {
        ("GET", "/api/vent/registry"),
        ("GET", "/api/projects/{project_id}/vent/{checksum}"),
        ("POST", "/api/projects/{project_id}/takeoff"),
        ("GET", "/api/projects/{project_id}/vent/{checksum}/quantity.csv"),
        ("GET", "/api/projects/{project_id}/vent/{checksum}/review"),
    }

    for method, path in expected:
        matching = _matching_routes(app, method, path)
        assert len(matching) == 1
        assert matching[0].endpoint.__module__.startswith("crow_vent_module")


def _matching_routes(app: FastAPI, method: str, path: str) -> list[object]:
    return [
        route
        for route in app.router.routes
        if getattr(route, "path", None) == path
        and method in (getattr(route, "methods", None) or set())
    ]
