from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from crow_module_sdk.module_registry import ModuleRegistry

from .audit import write_audit_event
from .catalog import load_product_module_catalog
from .context import current_customer_from_request
from .entitlements import load_customer_entitlements
from .models import (
    CustomerContext,
    EntitlementEntry,
    ProductModuleCatalog,
    ProductModuleStatus,
)

_ADMIN_ROLE = "platform-admin"
_CUSTOMER_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,119}$")


class CustomerCreate(BaseModel):
    customer_id: str = Field(min_length=1, max_length=120)


class EntitlementUpdateEntry(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    active: bool
    valid_until: date | None = None


class EntitlementUpdate(BaseModel):
    modules: list[EntitlementUpdateEntry]


def management_router(config_root: Path) -> APIRouter:
    router = APIRouter()
    catalog = load_product_module_catalog()

    @router.get("/api/session", response_model=None)
    def session(request: Request) -> dict[str, Any]:
        customer = _current_customer(request)
        destination = "/admin" if _is_admin(customer) else "/app"
        return {
            "customer_id": customer.customer_id,
            "user_id": customer.user_id,
            "roles": list(customer.roles),
            "destination": destination,
            "auth_mode": os.getenv("CROW_AUTH_MODE", "environment").strip().lower(),
        }

    @router.get("/api/admin/modules", response_model=None)
    def admin_modules(request: Request) -> dict[str, Any]:
        _require_admin(request)
        registry = ModuleRegistry()
        discovered = registry.discover()
        runtime = {
            item.module_id: {
                "module_id": item.module_id,
                "version": item.version,
                "origin": item.origin,
            }
            for item in discovered
        }
        modules = [
            {
                "id": module.id,
                "name": module.name,
                "status": module.status.value,
                "route": module.route,
                "requires_modules": list(module.requires_modules),
                "runtime_module_id": module.runtime_module_id,
                "runtime_installed": (
                    module.runtime_module_id in runtime if module.runtime_module_id else None
                ),
            }
            for module in catalog.modules
        ]
        return {
            "catalog_version": catalog.version,
            "modules": modules,
            "runtime_modules": list(runtime.values()),
        }

    @router.get("/api/admin/customers", response_model=None)
    def admin_customers(request: Request) -> dict[str, Any]:
        _require_admin(request)
        customers_root = config_root / "customers"
        customer_ids = (
            sorted(path.name for path in customers_root.iterdir() if path.is_dir())
            if customers_root.is_dir()
            else []
        )
        customers = [
            _customer_summary(config_root, customer_id, catalog) for customer_id in customer_ids
        ]
        return {"customers": customers}

    @router.post("/api/admin/customers", status_code=201, response_model=None)
    def create_customer(payload: CustomerCreate, request: Request) -> dict[str, Any]:
        administrator = _require_admin(request)
        customer_id = _normalize_customer_id(payload.customer_id)
        target = config_root / "customers" / customer_id / "entitlements.json"
        if target.exists():
            raise HTTPException(status_code=409, detail="Customer already exists")
        document = {"customer_id": customer_id, "modules": []}
        target.parent.mkdir(parents=True, exist_ok=False)
        target.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        write_audit_event(
            config_root,
            actor=administrator,
            action="customer.created",
            target_type="customer",
            target_id=customer_id,
            customer_id=customer_id,
            after=document,
        )
        return _customer_summary(config_root, customer_id, catalog)

    @router.get("/api/admin/customers/{customer_id}/entitlements", response_model=None)
    def admin_customer_entitlements(customer_id: str, request: Request) -> dict[str, Any]:
        _require_admin(request)
        normalized = _normalize_customer_id(customer_id)
        entitlements = load_customer_entitlements(config_root, normalized, catalog=catalog)
        return _entitlement_payload(entitlements.customer_id, entitlements.entries)

    @router.put("/api/admin/customers/{customer_id}/entitlements", response_model=None)
    def update_customer_entitlements(
        customer_id: str, payload: EntitlementUpdate, request: Request
    ) -> dict[str, Any]:
        administrator = _require_admin(request)
        normalized = _normalize_customer_id(customer_id)
        _validate_update(payload, catalog)
        target = config_root / "customers" / normalized / "entitlements.json"
        before = (
            json.loads(target.read_text(encoding="utf-8"))
            if target.is_file()
            else {"customer_id": normalized, "modules": []}
        )
        document = {
            "customer_id": normalized,
            "modules": [
                {
                    "id": entry.id,
                    "active": entry.active,
                    **(
                        {"valid_until": entry.valid_until.isoformat()}
                        if entry.valid_until is not None
                        else {}
                    ),
                }
                for entry in payload.modules
            ],
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(target)
        write_audit_event(
            config_root,
            actor=administrator,
            action="entitlements.updated",
            target_type="customer",
            target_id=normalized,
            customer_id=normalized,
            before=before,
            after=document,
        )
        entitlements = load_customer_entitlements(config_root, normalized, catalog=catalog)
        return _entitlement_payload(entitlements.customer_id, entitlements.entries)

    return router


def _current_customer(request: Request) -> CustomerContext:
    try:
        return current_customer_from_request(request)
    except RuntimeError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


def _is_admin(customer: CustomerContext) -> bool:
    return _ADMIN_ROLE in customer.roles


def _require_admin(request: Request) -> CustomerContext:
    customer = _current_customer(request)
    if not _is_admin(customer):
        raise HTTPException(status_code=403, detail="Platform administrator role required")
    return customer


def _normalize_customer_id(customer_id: str) -> str:
    normalized = customer_id.strip().lower()
    if not _CUSTOMER_ID.fullmatch(normalized):
        raise HTTPException(status_code=400, detail="Invalid customer id")
    return normalized


def _validate_update(payload: EntitlementUpdate, catalog: ProductModuleCatalog) -> None:
    module_ids = [entry.id for entry in payload.modules]
    if len(module_ids) != len(set(module_ids)):
        raise HTTPException(status_code=400, detail="Duplicate product module id")
    known = {module.id for module in catalog.modules}
    unknown = sorted(set(module_ids) - known)
    if unknown:
        raise HTTPException(
            status_code=400, detail=f"Unknown product modules: {', '.join(unknown)}"
        )

    active_ids = {entry.id for entry in payload.modules if entry.active}
    for module_id in sorted(active_ids):
        module = catalog.get(module_id)
        if module.status is not ProductModuleStatus.ACTIVE:
            raise HTTPException(
                status_code=400, detail=f"Product module is not active: {module_id}"
            )
        missing = sorted(set(module.requires_modules) - active_ids)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"{module_id} requires active modules: {', '.join(missing)}",
            )


def _customer_summary(
    config_root: Path, customer_id: str, catalog: ProductModuleCatalog
) -> dict[str, Any]:
    entitlements = load_customer_entitlements(config_root, customer_id, catalog=catalog)
    return {
        "customer_id": customer_id,
        "active_modules": sorted(entitlements.active_module_ids(today=date.today())),
        "configured_modules": len(entitlements.entries),
    }


def _entitlement_payload(customer_id: str, entries: tuple[EntitlementEntry, ...]) -> dict[str, Any]:
    return {
        "customer_id": customer_id,
        "modules": [
            {
                "id": entry.module_id,
                "active": entry.active,
                "valid_until": entry.valid_until.isoformat() if entry.valid_until else None,
            }
            for entry in entries
        ],
    }
