from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute

from crow_module_sdk.module_registry import ModuleRegistry
from crow_module_sdk.web import (
    CoreRouteClaim,
    CrowCoreRouteOwner,
    CrowGraphAuditProvider,
    CrowWebModule,
)
from crow_workbench.app import create_app as create_core_app
from crow_workbench.shell import (
    _register_core_route_claims,
    _remove_core_routes,
    create_app,
)

LEGACY_VENT_ROUTES = (
    CoreRouteClaim("GET", "/api/vent/registry"),
    CoreRouteClaim("GET", "/api/projects/{project_id}/vent/{checksum}"),
    CoreRouteClaim("POST", "/api/projects/{project_id}/takeoff"),
    CoreRouteClaim("GET", "/api/projects/{project_id}/vent/{checksum}/quantity.csv"),
    CoreRouteClaim("GET", "/api/projects/{project_id}/vent/{checksum}/review"),
)


def test_first_party_domain_modules_are_discoverable() -> None:
    registry = ModuleRegistry()
    registered = registry.discover()
    by_id = {item.module_id: item for item in registered}

    assert {"crow.vent", "crow.provtryckning", "crow.ovk"} <= set(by_id)
    for module_id in ("crow.vent", "crow.provtryckning", "crow.ovk"):
        assert isinstance(by_id[module_id].plugin, CrowWebModule)

    vent = by_id["crow.vent"].plugin
    assert isinstance(vent, CrowGraphAuditProvider)
    assert not isinstance(vent, CrowCoreRouteOwner)


def test_core_route_claim_normalizes_method() -> None:
    claim = CoreRouteClaim(" get ", "/probe")

    assert claim == CoreRouteClaim("GET", "/probe")


def test_core_route_claim_requires_absolute_path() -> None:
    with pytest.raises(ValueError, match="must be absolute"):
        CoreRouteClaim("GET", "probe")


def test_core_app_no_longer_defines_legacy_vent_routes(tmp_path: Path) -> None:
    app = create_core_app(tmp_path, graph_audit_profiles=())

    for claim in LEGACY_VENT_ROUTES:
        assert _matching_routes(app, claim.method, claim.path) == []


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


def test_vent_plugin_owns_legacy_product_routes_without_core_takeover(tmp_path: Path) -> None:
    by_id = {item.module_id: item for item in ModuleRegistry().discover()}
    vent = by_id["crow.vent"].plugin
    assert isinstance(vent, CrowWebModule)
    assert not isinstance(vent, CrowCoreRouteOwner)

    routers = vent.routers(tmp_path)

    for route in LEGACY_VENT_ROUTES:
        matching = _matching_router_routes(routers, route.method, route.path)
        assert len(matching) == 1, f"Vent module does not own {route.method} {route.path}"
        assert matching[0].endpoint.__module__.startswith("crow_vent_module")


def test_vent_contributes_graph_audit_profile() -> None:
    by_id = {item.module_id: item for item in ModuleRegistry().discover()}
    vent = by_id["crow.vent"].plugin
    assert isinstance(vent, CrowGraphAuditProvider)

    profiles = vent.graph_audit_profiles()
    assert len(profiles) == 1
    profile = profiles[0]
    assert profile.profile_id == "crow.vent.graph-audit"
    assert profile.audit_prefix == "vent"
    assert profile.ruleset_version == "0.1.0"
    assert {rule.metadata.rule_id for rule in profile.rules} == {
        "VENT-DQ-001",
        "VENT-DQ-002",
        "VENT-EVID-001",
        "VENT-EVID-002",
    }


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


def _matching_router_routes(
    routers: tuple[APIRouter, ...], method: str, path: str
) -> list[APIRoute]:
    return [
        route
        for router in routers
        for route in router.routes
        if isinstance(route, APIRoute) and route.path == path and method in route.methods
    ]
