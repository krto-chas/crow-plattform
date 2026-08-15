"""Modeller för prissättning av OVK-besiktning."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

SCHEMA_VERSION = "crow-ovk-pricing-v0.2"


class InspectionType(StrEnum):
    FORSTAGANG = "forstagang"
    ATERKOMMANDE = "aterkommande"


class BuildingCategory(StrEnum):
    FLERBOSTADSHUS = "flerbostadshus"
    SMAHUS = "smahus"
    HOTELL = "hotell"
    LOKAL = "lokal"


class VentilationSystemType(StrEnum):
    S = "S"
    F = "F"
    FX = "FX"
    FT = "FT"
    FTX = "FTX"


class PricingBasis(StrEnum):
    PER_APARTMENT = "per_apartment"
    PER_ROOM = "per_room"
    FLAT_PER_UNIT = "flat_per_unit"
    PER_AREA = "per_area"


@dataclass(frozen=True, slots=True)
class OvkObjectPart:
    category: BuildingCategory
    system_type: VentilationSystemType | None = None
    apartment_count: int | None = None
    room_count: int | None = None
    area_m2: Decimal | None = None
    unit_count: int = 1
    school_or_care: bool = False
    label: str | None = None


@dataclass(frozen=True, slots=True)
class OvkQuoteRequest:
    inspection_type: InspectionType
    parts: tuple[OvkObjectPart, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class OvkQuoteLine:
    category: BuildingCategory
    pricing_basis: PricingBasis
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    amount: Decimal
    recurring_interval_years: int | None


@dataclass(frozen=True, slots=True)
class OvkQuote:
    schema_version: str
    inspection_type: InspectionType
    lines: tuple[OvkQuoteLine, ...]
    base_fee: Decimal
    subtotal: Decimal
    minimum_total: Decimal
    minimum_applied: bool
    total: Decimal
    currency: str
    next_inspection_interval_years: int | None
