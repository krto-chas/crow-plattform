from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .context import current_customer_from_request
from .models import CustomerContext

_ADMIN_ROLE = "platform-admin"


def write_audit_event(
    config_root: Path,
    *,
    actor: CustomerContext,
    action: str,
    target_type: str,
    target_id: str,
    customer_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "actor_user_id": actor.user_id,
        "actor_customer_id": actor.customer_id,
        "actor_roles": list(actor.roles),
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "customer_id": customer_id,
        "before": before,
        "after": after,
    }
    path = config_root / "audit" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def audit_router(config_root: Path) -> APIRouter:
    router = APIRouter()

    @router.get("/api/admin/audit", response_model=None)
    def list_audit(request: Request, limit: int = 200) -> dict[str, Any]:
        _require_admin(request)
        resolved_limit = max(1, min(limit, 1000))
        path = config_root / "audit" / "events.jsonl"
        if not path.is_file():
            return {"events": []}
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
        return {"events": list(reversed(events[-resolved_limit:]))}

    return router


def _require_admin(request: Request) -> CustomerContext:
    try:
        customer = current_customer_from_request(request)
    except RuntimeError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    if _ADMIN_ROLE not in customer.roles:
        raise HTTPException(status_code=403, detail="Platform administrator role required")
    return customer
