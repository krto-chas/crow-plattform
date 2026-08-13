from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, Response

from .catalog import load_product_module_catalog
from .context import current_customer_from_request
from .entitlements import load_customer_entitlements
from .models import CustomerContext, ProductModule, ProductModuleCatalog


def configure_entitlement_shell(
    app: FastAPI,
    *,
    config_root: Path,
    today_provider: Callable[[], date] = date.today,
) -> None:
    catalog = load_product_module_catalog()
    app.include_router(_router(config_root, catalog, today_provider))

    @app.middleware("http")
    async def entitlement_guard(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        module = catalog.module_for_api_path(request.url.path)
        if module is None:
            return await call_next(request)
        customer = _customer_or_error(request)
        if isinstance(customer, JSONResponse):
            return customer
        try:
            entitlements = load_customer_entitlements(
                config_root, customer.customer_id, catalog=catalog
            )
        except (OSError, ValueError) as error:
            return JSONResponse(
                status_code=500,
                content={"detail": {"code": "ENTITLEMENT_CONFIG_INVALID", "message": str(error)}},
            )
        today = today_provider()
        active_ids = entitlements.active_module_ids(today=today)
        if module.status.value != "active" or not _module_is_effectively_active(module, active_ids):
            return JSONResponse(
                status_code=403,
                content={"detail": {"code": "MODULE_NOT_ACTIVE", "module": module.id}},
            )
        request.state.customer = customer
        return await call_next(request)


def _router(
    config_root: Path,
    catalog: ProductModuleCatalog,
    today_provider: Callable[[], date],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/me/modules", response_model=None)
    def my_modules(request: Request) -> dict[str, Any] | JSONResponse:
        customer = _customer_or_error(request)
        if isinstance(customer, JSONResponse):
            return customer
        try:
            entitlements = load_customer_entitlements(
                config_root, customer.customer_id, catalog=catalog
            )
        except (OSError, ValueError) as error:
            return JSONResponse(
                status_code=500,
                content={"detail": {"code": "ENTITLEMENT_CONFIG_INVALID", "message": str(error)}},
            )
        today = today_provider()
        active_ids = entitlements.active_module_ids(today=today)
        modules = [
            {
                "id": module.id,
                "name": module.name,
                "route": module.route,
                "api_prefixes": list(module.api_prefixes),
                "data_dependencies": list(module.data_dependencies),
                "requires_modules": list(module.requires_modules),
                "runtime_module_id": module.runtime_module_id,
            }
            for module in catalog.active_modules()
            if _module_is_effectively_active(module, active_ids)
        ]
        return {
            "customer_id": customer.customer_id,
            "user_id": customer.user_id,
            "roles": list(customer.roles),
            "catalog_version": catalog.version,
            "modules": modules,
        }

    return router


def _module_is_effectively_active(module: ProductModule, active_ids: frozenset[str]) -> bool:
    return module.id in active_ids and set(module.requires_modules).issubset(active_ids)


def _customer_or_error(request: Request) -> CustomerContext | JSONResponse:
    try:
        return current_customer_from_request(request)
    except RuntimeError as error:
        return JSONResponse(
            status_code=401,
            content={"detail": {"code": "AUTHENTICATION_REQUIRED", "message": str(error)}},
        )
