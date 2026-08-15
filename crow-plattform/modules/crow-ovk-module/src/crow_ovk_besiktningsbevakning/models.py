"""Modeller för besiktningsbevakning: härledd vy över kommande OVK-frister."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

SCHEMA_VERSION = "crow-ovk-bevakning-v0.1"


class WatchStatus(StrEnum):
    OK = "ok"
    PAMINNELSE = "paminnelse"
    FORSENAD = "forsenad"
    OMBESIKTNING_KRAVS = "ombesiktning_kravs"
    INGEN_FRIST = "ingen_frist"


class WatchSource(StrEnum):
    INTYG = "intyg"
    OMBESIKTNING = "ombesiktning"


@dataclass(frozen=True, slots=True)
class WatchItem:
    project_id: str
    building_id: str
    object_name: str
    source: WatchSource
    ref_id: str
    inspection_id: str
    status: WatchStatus
    basis: str
    due_date: date | None = None
    interval_years: int | None = None
    days_until: int | None = None

    def __post_init__(self) -> None:
        if not self.basis.strip():
            raise ValueError("watch item requires a written basis")
        if (self.due_date is None) != (self.days_until is None):
            raise ValueError("due_date and days_until must be set together")


@dataclass(frozen=True, slots=True)
class WatchList:
    project_id: str
    generated_at: date
    reminder_window_days: int
    items: tuple[WatchItem, ...]

    def __post_init__(self) -> None:
        if self.reminder_window_days < 0:
            raise ValueError("reminder_window_days must be non-negative")

    @property
    def overdue_count(self) -> int:
        return sum(
            item.status in (WatchStatus.FORSENAD, WatchStatus.OMBESIKTNING_KRAVS)
            for item in self.items
        )

    @property
    def reminder_count(self) -> int:
        return sum(item.status is WatchStatus.PAMINNELSE for item in self.items)
