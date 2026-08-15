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
    return ProductModule(
        id=str(payload["id"]),
        name=str(payload["name"]),
        status=ProductModuleStatus(str(payload["status"])),
        route=str(payload["route"]),
        api_prefixes=api_prefixes,
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
