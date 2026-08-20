from __future__ import annotations

from dataclasses import dataclass

from .models import CanonicalObject, CanonicalRelation


@dataclass(frozen=True)
class CanonicalAssembly:
    """Domain-neutral collection of canonical objects and explicit relations."""

    objects: tuple[CanonicalObject, ...]
    relations: tuple[CanonicalRelation, ...]
