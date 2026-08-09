from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from crow_entitlements.api import configure_entitlement_shell
from crow_module_sdk.module_registry import ModuleRegistry
from crow_module_sdk.web import CrowWebModule

from .app import create_app as create_core_app


def create_app(data_root: Path | None = None) -> FastAPI:
    app = create_core_app(data_root)
    root = data_root or Path.cwd() / ".crow-workbench"

    registry = ModuleRegistry()
    for registered in registry.discover():
        plugin = registered.plugin
        if isinstance(plugin, CrowWebModule):
            for router in plugin.routers(root):
                app.include_router(router)

    configure_entitlement_shell(app, config_root=root / "config")
    return app


app = create_app()
