from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from fastapi import APIRouter


@runtime_checkable
class CrowWebModule(Protocol):
    """Optional Workbench extension implemented by installable domain modules."""

    def routers(self, data_root: Path) -> tuple[APIRouter, ...]: ...


@runtime_checkable
class CrowCoreRouteOwner(Protocol):
    """Optional transition contract for modules taking ownership of legacy core routes."""

    def replaces_core_routes(self) -> tuple[str, ...]: ...
