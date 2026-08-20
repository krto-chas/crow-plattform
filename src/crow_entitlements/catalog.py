from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, cast

from .models import ProductModule, ProductModuleCatalog, ProductModuleStatus


def load_product_module_catalog() -> ProductModuleCatalog:
    resource = files("crow_entitlements").joinpath("product_modules.json")
    payload = cast(dict[str, Any], json.loads(resource.read_text(encoding="utf-8")))
    meta = cast(dict[str, Any], payload["meta"])
    raw_modules = cast(list[dict[str, Any]], payload["modules"])
    modules = tuple(_module_from_payload(item) for item in raw_modules)
    ids = [module.id for module in modules]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate product module id")
    exact_route_owners: dict[str, str] = {}
    for module in modules:
        for route in module.api_routes:
            previous = exact_route_owners.get(route)
            if previous is not None:
                raise ValueError(
                    f"API route {route!r} is assigned to both {previous!r} and {module.id!r}"
                )
            exact_route_owners[route] = module.id
    known = set(ids)
    for module in modules:
        unknown = sorted(set(module.requires_modules) - known)
        if unknown:
            raise ValueError(
                f"Product module {module.id!r} requires unknown modules: {', '.join(unknown)}"
            )
        if module.id in module.requires_modules:
            raise ValueError(f"Product module {module.id!r} cannot require itself")
    return ProductModuleCatalog(version=str(meta["version"]), modules=modules)


def _module_from_payload(payload: dict[str, Any]) -> ProductModule:
    api_prefixes = tuple(str(item) for item in cast(list[Any], payload.get("api_prefixes", [])))
    if not api_prefixes:
        raise ValueError(f"Product module {payload.get('id')!r} must define api_prefixes")
    api_routes = tuple(str(item) for item in cast(list[Any], payload.get("api_routes", [])))
    invalid_routes = [route for route in api_routes if not route.startswith("/")]
    if invalid_routes:
        raise ValueError(
            f"Product module {payload.get('id')!r} has non-absolute api_routes: "
            + ", ".join(invalid_routes)
        )
    return ProductModule(
        id=str(payload["id"]),
        name=str(payload["name"]),
        status=ProductModuleStatus(str(payload["status"])),
        route=str(payload["route"]),
        api_prefixes=api_prefixes,
        api_routes=api_routes,
        data_dependencies=tuple(
            str(item) for item in cast(list[Any], payload.get("data_dependencies", []))
        ),
        requires_modules=tuple(
            str(item) for item in cast(list[Any], payload.get("requires_modules", []))
        ),
        runtime_module_id=(
            str(payload["runtime_module_id"]) if payload.get("runtime_module_id") else None
        ),
    )
