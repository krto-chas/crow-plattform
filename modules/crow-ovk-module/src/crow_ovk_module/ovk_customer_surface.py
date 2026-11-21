"""Kundregister för OVK:s skrivbordsarbetsplats.

Kunden är den som besiktningen görs åt (ADR-013). Registret är gemensamt för
organisationen. Sparande kräver att klienten anger vilken revision ändringen
utgår från, så att två som ändrar samma kund inte tyst skriver över varandra.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from crow_ovk_fastighet import (
    FastighetRepository,
    Kund,
    KundRepository,
    kund_from_payload,
    kund_to_payload,
)
from fastapi import APIRouter, HTTPException, Request

from .ovk_scope import current_actor, visible_project_ids

_READ_ERRORS = (OSError, ValueError, KeyError, TypeError)
_REVISION_HEADER = "X-OVK-Base-Revision"


def kund_revision(kund: Kund) -> str:
    """Kundpostens revision: checksumma över den kanoniska posten."""
    canonical = json.dumps(
        kund_to_payload(kund), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _public(kund: Kund) -> dict[str, Any]:
    return {**kund_to_payload(kund), "revision": kund_revision(kund)}


def ovk_customer_router(data_root: Path) -> APIRouter:
    router = APIRouter()
    customers = KundRepository(data_root)
    properties = FastighetRepository(data_root)

    def load(kund_id: str) -> Kund:
        try:
            return customers.load(kund_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail={"code": "KUND_NOT_FOUND"}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_KUND"}) from exc

    @router.get("/api/ovk/kunder", response_model=None)
    def list_customers(request: Request) -> dict[str, Any]:
        actor = current_actor(request)
        try:
            items = customers.list()
        except _READ_ERRORS as exc:
            raise HTTPException(
                status_code=500, detail={"code": "KUND_REGISTER_UNREADABLE"}
            ) from exc
        counts: dict[str, int] = {}
        complete = True
        for project_id in visible_project_ids(data_root, actor):
            try:
                for fastighet in properties.list(project_id):
                    if fastighet.kund_id is not None:
                        counts[fastighet.kund_id] = counts.get(fastighet.kund_id, 0) + 1
            except _READ_ERRORS:
                # Antalet fastigheter per kund går då inte att lita på.
                complete = False
        return {
            "kunder": [
                {
                    **_public(kund),
                    "antal_fastigheter": counts.get(kund.kund_id, 0) if complete else None,
                }
                for kund in sorted(items, key=lambda item: (item.namn.casefold(), item.kund_id))
            ],
            "fullstandig": complete,
        }

    @router.get("/api/ovk/kunder/{kund_id}", response_model=None)
    def get_customer(kund_id: str, request: Request) -> dict[str, Any]:
        current_actor(request)
        return _public(load(kund_id))

    @router.put("/api/ovk/kunder/{kund_id}", response_model=None)
    async def save_customer(kund_id: str, request: Request) -> dict[str, Any]:
        actor = current_actor(request)
        try:
            payload: Any = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "INVALID_JSON"}) from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail={"code": "INVALID_JSON"})
        expected = request.headers.get(_REVISION_HEADER)
        if expected is None:
            raise HTTPException(status_code=428, detail={"code": "KUND_REVISION_REQUIRED"})
        candidate = {
            **payload,
            "kund_id": kund_id,
            "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "updated_by": actor.user_id,
        }
        try:
            kund = kund_from_payload(candidate)
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=422, detail={"code": "INVALID_KUND", "message": str(exc)}
            ) from exc
        registry = data_root / "registry" / "kund"
        registry.mkdir(parents=True, exist_ok=True)
        # SQLite serialiserar skrivare över trådar och processer på samma datarot,
        # så att jämförelsen av revision och skrivningen sker som ett steg.
        with closing(sqlite3.connect(registry / ".write-lock.sqlite3", timeout=30)) as lock:
            lock.execute("BEGIN IMMEDIATE")
            try:
                current = kund_revision(load(kund_id)) if customers.exists(kund_id) else None
                if (current is None and expected != "new") or (
                    current is not None and expected != current
                ):
                    raise HTTPException(
                        status_code=409,
                        detail={"code": "KUND_REVISION_CONFLICT", "current_revision": current},
                    )
                customers.save(kund)
            finally:
                lock.rollback()
        return _public(kund)

    return router
