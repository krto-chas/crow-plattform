from __future__ import annotations

import os
import re
from collections.abc import Awaitable, Callable
from datetime import date
from html import escape
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

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
        api_module = catalog.module_for_api_path(request.url.path)
        page_module = (
            catalog.module_for_route_path(request.url.path) if request.method == "GET" else None
        )
        module = api_module or page_module
        if module is None:
            return await call_next(request)

        customer = _customer_or_error(request)
        if isinstance(customer, JSONResponse):
            if page_module is not None and customer.status_code == 401:
                return RedirectResponse("/login", status_code=303)
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
            if page_module is not None:
                return RedirectResponse("/app", status_code=303)
            return JSONResponse(
                status_code=403,
                content={"detail": {"code": "MODULE_NOT_ACTIVE", "module": module.id}},
            )

        request.state.customer = customer
        response = await call_next(request)
        if page_module is None:
            return response
        return await _decorate_module_navigation(
            response,
            catalog=catalog,
            active_ids=active_ids,
            current_module=page_module,
        )


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


async def _decorate_module_navigation(
    response: Response,
    *,
    catalog: ProductModuleCatalog,
    active_ids: frozenset[str],
    current_module: ProductModule,
) -> Response:
    if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
        return response

    iterator = getattr(response, "body_iterator", None)
    if iterator is None:
        raw_body = getattr(response, "body", b"")
        body = raw_body if isinstance(raw_body, bytes) else bytes(raw_body)
    else:
        chunks: list[bytes] = []
        async for chunk in iterator:
            chunks.append(chunk.encode("utf-8") if isinstance(chunk, str) else bytes(chunk))
        body = b"".join(chunks)

    markup = body.decode("utf-8")
    navigation = _module_navigation_markup(catalog, active_ids, current_module)
    decorated = re.sub(r"<nav>.*?</nav>", navigation, markup, count=1, flags=re.DOTALL)

    headers = dict(response.headers)
    headers.pop("content-length", None)
    return Response(
        content=decorated,
        status_code=response.status_code,
        headers=headers,
        background=response.background,
    )


def _module_navigation_markup(
    catalog: ProductModuleCatalog,
    active_ids: frozenset[str],
    current_module: ProductModule,
) -> str:
    links = ['<a href="/app">Projekt</a>']
    for module in catalog.active_modules():
        if not _module_is_effectively_active(module, active_ids):
            continue
        label = module.name.split(" – ", maxsplit=1)[0]
        active = ' class="active"' if module.id == current_module.id else ""
        links.append(f'<a{active} href="{escape(module.route, quote=True)}">{escape(label)}</a>')
    return f"<nav>{''.join(links)}</nav>"


def _module_is_effectively_active(module: ProductModule, active_ids: frozenset[str]) -> bool:
    return module.id in active_ids and set(module.requires_modules).issubset(active_ids)


def _customer_or_error(request: Request) -> CustomerContext | JSONResponse:
    try:
        return current_customer_from_request(request)
    except RuntimeError as error:
        auth_mode = os.getenv("CROW_AUTH_MODE", "environment").strip().lower()
        if auth_mode == "session":
            return JSONResponse(
                status_code=401,
                content={"detail": {"code": "AUTHENTICATION_REQUIRED", "message": str(error)}},
            )
        return JSONResponse(
            status_code=503,
            content={"detail": {"code": "CUSTOMER_CONTEXT_UNAVAILABLE", "message": str(error)}},
        )
