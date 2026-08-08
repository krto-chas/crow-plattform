from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from crow_entitlements.api import configure_entitlement_shell

from .app import create_app as create_core_app
from .ovk_surface import ovk_router
from .pressure_test_integration_surface import pressure_test_integration_router
from .pressure_test_surface import pressure_test_router
from .vent_quote_surface import vent_quote_router
from .vent_surface import vent_router


def create_app(data_root: Path | None = None) -> FastAPI:
    app = create_core_app(data_root)
    root = data_root or Path.cwd() / ".crow-workbench"
    app.include_router(vent_router())
    app.include_router(vent_quote_router())
    app.include_router(pressure_test_router())
    app.include_router(pressure_test_integration_router())
    app.include_router(ovk_router())
    configure_entitlement_shell(app, config_root=root / "config")
    return app


app = create_app()
