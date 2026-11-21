"""Gemensamt omfång för OVK:s skrivbordsrutter.

Alla nya skrivbordsrutter hämtar sina projekt härifrån (ADR-013 punkt 3). I dag
körs plattformen för en organisation, så funktionen returnerar samtliga projekt
under dataroten. När kundisoleringen införs (roadmapens R8) läggs filtret på
organisation här, och rutterna behöver inte skrivas om.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, Request

from crow_entitlements.context import current_customer_from_request
from crow_entitlements.models import CustomerContext

_SAFE_PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def current_actor(request: Request) -> CustomerContext:
    """Den inloggade användaren och dess organisation, annars 401."""
    try:
        return current_customer_from_request(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail={"code": "AUTHENTICATION_REQUIRED"}) from exc


def visible_project_ids(data_root: Path, actor: CustomerContext) -> tuple[str, ...]:
    """Projekt som ``actor`` får se, i stabil ordning.

    ``actor`` används inte ännu: projekt saknar ägare tills R8. Parametern finns
    med från början så att ingen anropare kan lista projekt utan att ha löst
    vem som frågar.
    """
    del actor
    projects_root = data_root / "projects"
    if not projects_root.is_dir():
        return ()
    return tuple(
        sorted(
            path.name
            for path in projects_root.iterdir()
            if path.is_dir() and _SAFE_PROJECT_ID.fullmatch(path.name)
        )
    )
