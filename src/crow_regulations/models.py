from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class RuleStatus(StrEnum):
    CURRENT = "current"
    HISTORICAL = "historical"
    GUIDANCE = "guidance"


@dataclass(frozen=True)
class RuleReference:
    reference_id: str
    locator: str
    topics: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class RuleSource:
    source_id: str
    title: str
    issuer: str
    status: RuleStatus
    source_url: str
    effective_from: date | None
    effective_to: date | None
    verified_on: date
    supersedes: tuple[str, ...]
    amended_by: tuple[str, ...]
    topics: tuple[str, ...]
    references: tuple[RuleReference, ...]
    note: str

    def active_on(self, when: date) -> bool:
        if self.effective_from is not None and when < self.effective_from:
            return False
        return self.effective_to is None or when <= self.effective_to
