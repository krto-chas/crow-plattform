"""Modeller för prissättning av OVK-besiktning.

Prisgrunden följer branschpraxis:

- Flerbostadshus prissätts per lägenhet.
- Småhus (en- och tvåbostadshus) prissätts med fast pris per hus.
- Hotell, vandrarhem och liknande prissätts per rum.
- Lokaler, kontor, industri, skolor, vård m.m. prissätts per m² där
  à-priset beror på ventilationssystemtyp (S, F, FX, FT, FTX).

En förfrågan består av en eller flera delposter (``OvkObjectPart``) med
samma besiktningstyp — t.ex. ett hotell med rum per styck och
restaurang/konferens per m² — som prissätts i en gemensam kvot med en
grundavgift och en minimidebitering för hela uppdraget. Storlek är
obligatorisk endast där prisgrunden kräver den; för småhus är
storleksuppgift frivillig och påverkar inte priset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

SCHEMA_VERSION = "crow-ovk-pricing-v0.2"


class InspectionType(StrEnum):
    """Typ av OVK-besiktning enligt BFS 2011:16."""

    FORSTAGANG = "forstagang"
    ATERKOMMANDE = "aterkommande"


class BuildingCategory(StrEnum):
    """Objektkategori som styr prisgrunden."""

    FLERBOSTADSHUS = "flerbostadshus"
    SMAHUS = "smahus"
    HOTELL = "hotell"
    LOKAL = "lokal"


class VentilationSystemType(StrEnum):
    """Systemtyper enligt OVK-regelverket."""

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
    """En delpost i objektet: kategori, systemtyp och storlek.

    ``system_type`` krävs för lokaldelar (styr à-priset per m²) och är
    frivillig för övriga, där den endast används för intervallupplysning.
    ``school_or_care`` markerar förskola, skola, vårdlokal eller
    liknande verksamhet i delposten (3-årsintervall oavsett systemtyp).
    ``label`` är en frivillig egen benämning, t.ex. "Restaurang och kök".
    """

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
    """Användarens val: besiktningstyp och objektets delposter."""

    inspection_type: InspectionType
    parts: tuple[OvkObjectPart, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class OvkQuoteLine:
    """Prissatt delpost med egen prisgrund och intervallupplysning."""

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
    """Determinerat prisförslag: samma förfrågan och taxa ger samma kvot.

    ``base_fee`` (grundavgift för etablering, protokoll och
    intygshantering) adderas en gång per uppdrag. ``minimum_applied``
    anger att totalen lyfts till taxans minimidebitering.
    ``next_inspection_interval_years`` är det kortaste kända intervallet
    över delposterna — ``None`` när ingen delpost har återkommande
    besiktningsplikt med känd systemtyp; Crow gissar inte intervall.
    """

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
