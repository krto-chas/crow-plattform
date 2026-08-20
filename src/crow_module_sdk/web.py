from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from fastapi import APIRouter


@dataclass(frozen=True, slots=True)
class CoreRouteClaim:
    """One legacy core API route that an installable module replaces."""

    method: str
    path: str


@runtime_checkable
class CrowWebModule(Protocol):
    """Optional Workbench extension implemented by installable domain modules."""

    def routers(self, data_root: Path) -> tuple[APIRouter, ...]: ...


@runtime_checkable
class CrowCoreRouteOwner(Protocol):
    """Optional transition contract for modules taking ownership of legacy core routes."""

    def replaces_core_routes(self) -> tuple[CoreRouteClaim, ...]: ...
