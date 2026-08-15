from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

from .models import CustomerEntitlements, EntitlementEntry, ProductModuleCatalog


def load_customer_entitlements(
    config_root: Path,
    customer_id: str,
    *,
    catalog: ProductModuleCatalog | None = None,
) -> CustomerEntitlements:
    path = config_root / "customers" / customer_id / "entitlements.json"
    if not path.exists():
        return CustomerEntitlements(customer_id=customer_id, entries=())
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    configured_customer = str(payload.get("customer_id", customer_id))
    if configured_customer != customer_id:
        raise ValueError("Entitlement customer_id does not match customer context")
    raw_entries = cast(list[dict[str, Any]], payload.get("modules", []))
    entries = tuple(_entry_from_payload(item) for item in raw_entries)
    if catalog is not None:
        known = {module.id for module in catalog.modules}
        unknown = sorted({entry.module_id for entry in entries} - known)
        if unknown:
            raise ValueError(f"Unknown product module ids in entitlements: {', '.join(unknown)}")
    return CustomerEntitlements(customer_id=customer_id, entries=entries)


def _entry_from_payload(payload: dict[str, Any]) -> EntitlementEntry:
    raw_valid_until = payload.get("valid_until")
    valid_until = date.fromisoformat(str(raw_valid_until)) if raw_valid_until else None
    return EntitlementEntry(
        module_id=str(payload["id"]),
        active=bool(payload.get("active", False)),
        valid_until=valid_until,
    )
