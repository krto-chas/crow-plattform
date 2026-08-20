from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.routing import APIRoute

from crow_deployment.runtime import platform_config_root, platform_data_root
from crow_entitlements.api import configure_entitlement_shell
from crow_entitlements.audit import audit_router
from crow_entitlements.auth_api import configure_auth
from crow_entitlements.context import current_customer_from_request
from crow_entitlements.management import management_router
from crow_entitlements.models import CustomerContext
from crow_entitlements.user_admin import user_admin_router
from crow_module_sdk.module_registry import ModuleRegistry
from crow_module_sdk.web import CoreRouteClaim

_ADMIN_ROLE = "platform-admin"


def create_app(data_root: Path | None = None, config_root: Path | None = None) -> FastAPI:
    root = data_root or platform_data_root()
    resolved_config_root = config_root or platform_config_root(root)
    app = _create_core_app(root)
    static_root = Path(__file__).parent / "static"

    _remove_core_index(app)

    registry = ModuleRegistry()
    registered_modules = registry.discover()
    core_route_owners: dict[CoreRouteClaim, str] = {}
    for registered in registered_modules:
        claims_provider = getattr(registered.plugin, "replaces_core_routes", None)
        if callable(claims_provider):
            claims = claims_provider()
            _register_core_route_claims(core_route_owners, registered.module_id, claims)

    _remove_core_routes(app, tuple(core_route_owners))

    for registered in registered_modules:
        routers_provider = getattr(registered.plugin, "routers", None)
        if callable(routers_provider):
            for router in routers_provider(root):
                app.include_router(router)

    configure_auth(app, config_root=resolved_config_root)
    configure_entitlement_shell(app, config_root=resolved_config_root)
    app.include_router(management_router(resolved_config_root))
    app.include_router(user_admin_router(resolved_config_root))
    app.include_router(audit_router(resolved_config_root))

    @app.get("/", include_in_schema=False, response_model=None)
    def platform_landing(request: Request) -> Response:
        customer = _customer_for_shell(request)
        if customer is None:
            return FileResponse(static_root / "login.html")
        destination = "/admin" if _ADMIN_ROLE in customer.roles else "/app"
        return RedirectResponse(destination, status_code=303)

    @app.get("/login", include_in_schema=False, response_model=None)
    def login_shell(request: Request) -> Response:
        customer = _customer_for_shell(request)
        if customer is not None:
            destination = "/admin" if _ADMIN_ROLE in customer.roles else "/app"
            return RedirectResponse(destination, status_code=303)
        return FileResponse(static_root / "login.html")

    @app.get("/app", include_in_schema=False, response_model=None)
    def customer_shell(request: Request) -> Response:
        customer = _customer_for_shell(request)
        if customer is None:
            return RedirectResponse("/login", status_code=303)
        return FileResponse(static_root / "shell.html")

    @app.get("/admin", include_in_schema=False, response_model=None)
    def admin_shell(request: Request) -> Response:
        customer = _customer_for_shell(request)
        if customer is None:
            return RedirectResponse("/login", status_code=303)
        if _ADMIN_ROLE not in customer.roles:
            return RedirectResponse("/app", status_code=303)
        if request.query_params.get("view") == "access":
            return FileResponse(static_root / "shell.html")
        return FileResponse(static_root / "admin_home.html")

    @app.get("/admin/access", include_in_schema=False, response_model=None)
    def admin_access_shell(request: Request) -> Response:
        customer = _customer_for_shell(request)
        if customer is None:
            return RedirectResponse("/login", status_code=303)
        if _ADMIN_ROLE not in customer.roles:
            return RedirectResponse("/app", status_code=303)
        return RedirectResponse("/admin?view=access", status_code=303)

    @app.get("/admin/users", include_in_schema=False, response_model=None)
    def admin_users_shell(request: Request) -> Response:
        customer = _customer_for_shell(request)
        if customer is None:
            return RedirectResponse("/login", status_code=303)
        if _ADMIN_ROLE not in customer.roles:
            return RedirectResponse("/app", status_code=303)
        return FileResponse(static_root / "admin_users.html")

    @app.get("/admin/audit", include_in_schema=False, response_model=None)
    def admin_audit_shell(request: Request) -> Response:
        customer = _customer_for_shell(request)
        if customer is None:
            return RedirectResponse("/login", status_code=303)
        if _ADMIN_ROLE not in customer.roles:
            return RedirectResponse("/app", status_code=303)
        return FileResponse(static_root / "admin_audit.html")

    @app.get("/workbench", include_in_schema=False, response_model=None)
    def workbench_home(request: Request) -> Response:
        customer = _customer_for_shell(request)
        if customer is None:
            return RedirectResponse("/login", status_code=303)
        return FileResponse(static_root / "workbench_home.html")

    @app.get("/workbench/advanced", include_in_schema=False, response_model=None)
    def advanced_workbench(request: Request) -> Response:
        customer = _customer_for_shell(request)
        if customer is None:
            return RedirectResponse("/login", status_code=303)
        markup = (static_root / "index.html").read_text(encoding="utf-8")
        bridge = '<script src="/static/workbench-product-bridge.js"></script>'
        return HTMLResponse(markup.replace("</body>", f"{bridge}</body>", 1))

    return app


def _create_core_app(root: Path) -> FastAPI:
    original_cwd = Path.cwd()
    with TemporaryDirectory(prefix="crow-core-import-") as temporary_cwd:
        try:
            os.chdir(temporary_cwd)
            from .app import create_app as create_core_app
        finally:
            os.chdir(original_cwd)
    return create_core_app(root)


def _customer_for_shell(request: Request) -> CustomerContext | None:
    try:
        return current_customer_from_request(request)
    except RuntimeError:
        if os.getenv("CROW_AUTH_MODE", "environment").strip().lower() == "session":
            return None
        raise


def _remove_core_index(app: FastAPI) -> None:
    app.router.routes[:] = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == "/"
            and "GET" in (getattr(route, "methods", None) or set())
        )
    ]


def _register_core_route_claims(
    owners: dict[CoreRouteClaim, str],
    module_id: str,
    claims: tuple[CoreRouteClaim, ...],
) -> None:
    for claim in claims:
        previous = owners.get(claim)
        if previous is not None:
            raise RuntimeError(
                f"Core route {claim.method} {claim.path} is claimed by both "
                f"{previous} and {module_id}"
            )
        owners[claim] = module_id


def _remove_core_routes(app: FastAPI, claims: tuple[CoreRouteClaim, ...]) -> None:
    unmatched = set(claims)
    retained = []
    for route in app.router.routes:
        if not isinstance(route, APIRoute):
            retained.append(route)
            continue
        claimed_methods = {
            claim.method
            for claim in claims
            if claim.path == route.path and claim.method in route.methods
        }
        if not claimed_methods:
            retained.append(route)
            continue
        unmatched.difference_update(
            CoreRouteClaim(method, route.path) for method in claimed_methods
        )
        remaining_methods = set(route.methods) - claimed_methods
        if remaining_methods:
            route.methods = remaining_methods
            retained.append(route)
    if unmatched:
        missing = ", ".join(
            f"{claim.method} {claim.path}"
            for claim in sorted(unmatched, key=lambda item: (item.path, item.method))
        )
        raise RuntimeError(f"Core route ownership claim did not match an existing route: {missing}")
    app.router.routes[:] = retained
    app.openapi_schema = None


app = create_app()
