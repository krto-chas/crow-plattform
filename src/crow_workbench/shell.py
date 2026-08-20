from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from crow_deployment.runtime import platform_config_root, platform_data_root
from crow_entitlements.api import configure_entitlement_shell
from crow_entitlements.audit import audit_router
from crow_entitlements.auth_api import configure_auth
from crow_entitlements.context import current_customer_from_request
from crow_entitlements.management import management_router
from crow_entitlements.models import CustomerContext
from crow_entitlements.user_admin import user_admin_router
from crow_module_sdk.module_registry import ModuleRegistry
from crow_module_sdk.web import CrowWebModule

_ADMIN_ROLE = "platform-admin"


def create_app(data_root: Path | None = None, config_root: Path | None = None) -> FastAPI:
    root = data_root or platform_data_root()
    resolved_config_root = config_root or platform_config_root(root)
    app = _create_core_app(root)
    static_root = Path(__file__).parent / "static"

    _remove_core_index(app)

    registry = ModuleRegistry()
    for registered in registry.discover():
        plugin = registered.plugin
        if isinstance(plugin, CrowWebModule):
            for router in plugin.routers(root):
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
    def legacy_workbench() -> HTMLResponse:
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


app = create_app()
