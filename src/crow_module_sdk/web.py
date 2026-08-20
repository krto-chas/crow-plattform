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

    def __post_init__(self) -> None:
        method = self.method.strip().upper()
        path = self.path.strip()
        if not method:
            raise ValueError("Core route claim method must not be empty")
        if not path.startswith("/"):
            raise ValueError("Core route claim path must be absolute")
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "path", path)


@runtime_checkable
class CrowWebModule(Protocol):
    """Optional Workbench extension implemented by installable domain modules."""

    def routers(self, data_root: Path) -> tuple[APIRouter, ...]: ...


@runtime_checkable
class CrowCoreRouteOwner(Protocol):
    """Optional transition contract for modules taking ownership of legacy core routes."""

    def replaces_core_routes(self) -> tuple[CoreRouteClaim, ...]: ...
