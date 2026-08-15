from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class TimeCategory(StrEnum):
    FIELD = "field"
    REVIEW = "review"
    PROTOCOL = "protocol"


@dataclass(frozen=True, slots=True)
class TimeSegment:
    segment_id: str
    category: TimeCategory
    started_at: str
    ended_at: str


@dataclass(frozen=True, slots=True)
class TimeAdjustment:
    adjustment_id: str
    hours: Decimal
    reason: str
    changed_by: str
    changed_at: str


@dataclass(frozen=True, slots=True)
class InspectionTimeLedger:
    inspection_id: str
    project_id: str
    inspection_date: str
    segments: tuple[TimeSegment, ...] = ()
    adjustments: tuple[TimeAdjustment, ...] = ()


@dataclass(frozen=True, slots=True)
class CertificationProfile:
    profile_id: str
    inspector_name: str
    certification_body: str
    certificate_number: str
    authorization: str
    reporting_period_start: str
    reporting_period_end: str


@dataclass(frozen=True, slots=True)
class AnnualReportRow:
    inspection_id: str
    project_id: str
    inspection_date: str
    calculated_hours: Decimal
    adjustment_hours: Decimal
    reported_hours: Decimal
