"""Modeller för schablonprissättning av entreprenader.

Ett schablonpris (nyckeltal) är ett erfarenhetsbaserat pris per enhet —
kr/lgh, kr/rum, kr/m² BTA, kr/hus — med ett spann låg/normal/hög som
bär osäkerheten öppet. Schabloner har två användningsfall:

- Snabbindikation innan handlingar finns: kvantitet × spann ger en
  grov prisbild, alltid markerad som härledd (inferred).
- Rimlighetskontroll av detaljkalkylen: hamnar den prissatta
  mängdförteckningen utanför spannet flaggas det som avvikelse i
  stället för att tystas.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

SCHEMA_VERSION = "crow-benchmark-pricing-v0.1"
ORIGIN_INFERRED = "inferred"


class ComparisonVerdict(StrEnum):
    """Utfall när en detaljkalkyl jämförs mot schablonspannet."""
    BELOW_RANGE = "below_range"
    WITHIN_RANGE = "within_range"
    ABOVE_RANGE = "above_range"


@dataclass(frozen=True, slots=True)
class BenchmarkRange:
    """Spann i kronor per enhet; låg ≤ normal ≤ hög krävs."""
    low: Decimal
    normal: Decimal
    high: Decimal

    def __post_init__(self) -> None:
        if not Decimal(0) < self.low <= self.normal <= self.high:
            raise ValueError(
                f"range must satisfy 0 < low <= normal <= high, "
                f"got low={self.low}, normal={self.normal}, high={self.high}"
            )


@dataclass(frozen=True, slots=True)
class Benchmark:
    benchmark_id: str
    discipline: str
    unit: str
    label: str
    unit_range: BenchmarkRange


@dataclass(frozen=True, slots=True)
class QuickEstimate:
    """Grov prisindikation: kvantitet × spann, alltid inferred."""
    schema_version: str
    benchmark_id: str
    discipline: str
    label: str
    quantity: Decimal
    unit: str
    low_total: Decimal
    normal_total: Decimal
    high_total: Decimal
    currency: str
    origin: str


@dataclass(frozen=True, slots=True)
class BenchmarkComparison:
    """Detaljkalkyl mot schablonspann; utanför spann = flaggad avvikelse."""
    schema_version: str
    benchmark_id: str
    discipline: str
    label: str
    quantity: Decimal
    unit: str
    expected_low: Decimal
    expected_normal: Decimal
    expected_high: Decimal
    detailed_total: Decimal
    deviation_percent: Decimal
    verdict: ComparisonVerdict
    flagged: bool
    currency: str
    caveats: tuple[str, ...]
