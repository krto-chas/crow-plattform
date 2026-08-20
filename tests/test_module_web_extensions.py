from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from crow_module_sdk.module_registry import ModuleRegistry
from crow_module_sdk.web import CoreRouteClaim, CrowCoreRouteOwner, CrowWebModule
from crow_workbench.shell import (
    _register_core_route_claims,
    _remove_core_routes,
    create_app,
)


def test_first_party_domain_modules_are_discoverable() -> None:
    registry = ModuleRegistry()
    registered = registry.discover()
    by_id = {item.module_id: item for item in registered}

    assert {"crow.vent", "crow.provtryckning", "crow.ovk"} <= set(by_id)
    for module_id in ("crow.vent", "crow.provtryckning", "crow.ovk"):
        assert isinstance(by_id[module_id].plugin, CrowWebModule)

    vent = by_id["crow.vent"].plugin
    assert isinstance(vent, CrowCoreRouteOwner)
    assert (
        CoreRouteClaim("POST", "/api/projects/{project_id}/takeoff") in vent.replaces_core_routes()
    )


def test_core_route_claim_normalizes_method() -> None:
    claim = CoreRouteClaim(" get ", "/probe")

    assert claim == CoreRouteClaim("GET", "/probe")


def test_core_route_claim_requires_absolute_path() -> None:
    with pytest.raises(ValueError, match="must be absolute"):
        CoreRouteClaim("GET", "probe")


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
    expected = (
        ("GET", "/api/vent/registry"),
        ("GET", "/api/projects/{project_id}/vent/{checksum}"),
        ("POST", "/api/projects/{project_id}/takeoff"),
        ("GET", "/api/projects/{project_id}/vent/{checksum}/quantity.csv"),
        ("GET", "/api/projects/{project_id}/vent/{checksum}/review"),
    )

    for method, path in expected:
        matching = _matching_routes(app, method, path)
        assert len(matching) == 1, (
            f"Missing composed route: {method} {path}; candidates={_route_debug(app, path)!r}"
        )
        assert matching[0].endpoint.__module__.startswith("crow_vent_module")


def test_core_route_claim_removes_only_claimed_method() -> None:
    app = FastAPI()

    @app.api_route("/probe", methods=["GET", "POST"])
    def probe() -> dict[str, bool]:
        return {"ok": True}

    _remove_core_routes(app, (CoreRouteClaim("GET", "/probe"),))

    assert _matching_routes(app, "GET", "/probe") == []
    assert len(_matching_routes(app, "POST", "/probe")) == 1


def test_unmatched_core_route_claim_is_rejected() -> None:
    app = FastAPI()

    @app.get("/probe")
    def probe() -> dict[str, bool]:
        return {"ok": True}

    with pytest.raises(RuntimeError, match="did not match an existing route"):
        _remove_core_routes(app, (CoreRouteClaim("DELETE", "/probe"),))


def test_duplicate_core_route_ownership_is_rejected() -> None:
    owners: dict[CoreRouteClaim, str] = {}
    claim = CoreRouteClaim("GET", "/probe")
    _register_core_route_claims(owners, "crow.first", (claim,))

    with pytest.raises(RuntimeError, match="claimed by both crow.first and crow.second"):
        _register_core_route_claims(owners, "crow.second", (claim,))


def _matching_routes(app: FastAPI, method: str, path: str) -> list[APIRoute]:
    return [
        route
        for route in app.router.routes
        if isinstance(route, APIRoute) and route.path == path and method in route.methods
    ]


def _route_debug(app: FastAPI, path: str) -> list[tuple[str, tuple[str, ...], str]]:
    result: list[tuple[str, tuple[str, ...], str]] = []
    for route in app.router.routes:
        if getattr(route, "path", None) != path:
            continue
        methods = tuple(sorted(getattr(route, "methods", None) or ()))
        endpoint = getattr(route, "endpoint", None)
        result.append((type(route).__name__, methods, getattr(endpoint, "__module__", "")))
    return result
