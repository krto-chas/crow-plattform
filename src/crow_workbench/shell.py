from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from crow_entitlements.api import configure_entitlement_shell
from crow_entitlements.management import management_router
from crow_module_sdk.module_registry import ModuleRegistry
from crow_module_sdk.web import CrowWebModule

from .app import create_app as create_core_app


def create_app(data_root: Path | None = None) -> FastAPI:
    app = create_core_app(data_root)
    root = data_root or Path.cwd() / ".crow-workbench"
    static_root = Path(__file__).parent / "static"

    _remove_core_index(app)

    registry = ModuleRegistry()
    for registered in registry.discover():
        plugin = registered.plugin
        if isinstance(plugin, CrowWebModule):
            for router in plugin.routers(root):
                app.include_router(router)

    configure_entitlement_shell(app, config_root=root / "config")
    app.include_router(management_router(root / "config"))

    @app.get("/", include_in_schema=False)
    def platform_landing() -> FileResponse:
        return FileResponse(static_root / "shell.html")

    @app.get("/app", include_in_schema=False)
    def customer_shell() -> FileResponse:
        return FileResponse(static_root / "shell.html")

    @app.get("/admin", include_in_schema=False)
    def admin_shell() -> FileResponse:
        return FileResponse(static_root / "shell.html")

    @app.get("/workbench", include_in_schema=False)
    def legacy_workbench() -> FileResponse:
        return FileResponse(static_root / "index.html")

    return app


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
