"""Snabbindikation och rimlighetskontroll mot schablonspann.

Principer:

- Ett schablonresultat är alltid härlett (inferred) — det är
  erfarenhetstal, inte kalkyl, och payloaden bär det öppet.
- Rimlighetskontrollen jämför en detaljkalkyls totalsumma mot
  kvantitet × spann; utanför spannet flaggas avvikelsen med riktning
  och procent mot normalvärdet.
- Adaptern mot Pass 44-payloaden (crow-takeoff-pricing) lägger
  förbehåll när kalkylen innehåller oprissatta rader eller
  reservationer: en jämförelse mot en ofullständig kalkyl redovisas,
  men aldrig utan att ofullständigheten syns.
- Alla belopp är Decimal och kvantiseras till ören (ROUND_HALF_UP).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .models import (
    ORIGIN_INFERRED,
    SCHEMA_VERSION,
    Benchmark,
    BenchmarkComparison,
    ComparisonVerdict,
    QuickEstimate,
)

_MONEY_QUANTUM = Decimal("0.01")
_PERCENT_QUANTUM = Decimal("0.1")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _require_positive_quantity(quantity: Decimal) -> None:
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")


def quick_estimate(benchmark: Benchmark, quantity: Decimal, currency: str) -> QuickEstimate:
    _require_positive_quantity(quantity)
    r = benchmark.unit_range
    return QuickEstimate(
        schema_version=SCHEMA_VERSION,
        benchmark_id=benchmark.benchmark_id,
        discipline=benchmark.discipline,
        label=benchmark.label,
        quantity=quantity,
        unit=benchmark.unit,
        low_total=_money(quantity * r.low),
        normal_total=_money(quantity * r.normal),
        high_total=_money(quantity * r.high),
        currency=currency,
        origin=ORIGIN_INFERRED,
    )


def compare_detailed_total(
    benchmark: Benchmark,
    quantity: Decimal,
    detailed_total: Decimal,
    currency: str,
    caveats: tuple[str, ...] = (),
) -> BenchmarkComparison:
    _require_positive_quantity(quantity)
    if detailed_total < 0:
        raise ValueError(f"detailed_total must be non-negative, got {detailed_total}")
    r = benchmark.unit_range
    expected_low = _money(quantity * r.low)
    expected_normal = _money(quantity * r.normal)
    expected_high = _money(quantity * r.high)

    if detailed_total < expected_low:
        verdict = ComparisonVerdict.BELOW_RANGE
    elif detailed_total > expected_high:
        verdict = ComparisonVerdict.ABOVE_RANGE
    else:
        verdict = ComparisonVerdict.WITHIN_RANGE

    deviation = ((detailed_total - expected_normal) / expected_normal * 100).quantize(
        _PERCENT_QUANTUM, rounding=ROUND_HALF_UP
    )

    return BenchmarkComparison(
        schema_version=SCHEMA_VERSION,
        benchmark_id=benchmark.benchmark_id,
        discipline=benchmark.discipline,
        label=benchmark.label,
        quantity=quantity,
        unit=benchmark.unit,
        expected_low=expected_low,
        expected_normal=expected_normal,
        expected_high=expected_high,
        detailed_total=_money(detailed_total),
        deviation_percent=deviation,
        verdict=verdict,
        flagged=verdict is not ComparisonVerdict.WITHIN_RANGE,
        currency=currency,
        caveats=caveats,
    )


def compare_takeoff_pricing(
    benchmark: Benchmark, quantity: Decimal, pricing_payload: dict[str, Any]
) -> BenchmarkComparison:
    """Rimlighetskontroll av en Pass 44-kalkyl (crow-takeoff-pricing).

    Läser ``grand_total`` och lägger förbehåll när kalkylen har
    oprissatta rader eller reservationer — då är totalsumman en
    undre gräns, inte ett facit.
    """
    schema = str(pricing_payload.get("schema_version", ""))
    if not schema.startswith("crow-takeoff-pricing"):
        raise ValueError(f"expected a crow-takeoff-pricing payload, got schema_version={schema!r}")
    caveats: list[str] = []
    unpriced = int(pricing_payload.get("unpriced_line_count", 0))
    reservations = int(pricing_payload.get("reservation_count", 0))
    if unpriced:
        caveats.append(
            f"detaljkalkylen har {unpriced} oprissatta rader; totalsumman är en undre gräns"
        )
    if reservations:
        caveats.append(f"detaljkalkylen har {reservations} reservationer med olösta kvantiteter")
    return compare_detailed_total(
        benchmark=benchmark,
        quantity=quantity,
        detailed_total=Decimal(str(pricing_payload["grand_total"])),
        currency=str(pricing_payload.get("currency", "SEK")),
        caveats=tuple(caveats),
    )


def estimate_to_payload(estimate: QuickEstimate) -> dict[str, Any]:
    """JSON-vänlig payload; belopp serialiseras som strängar (ADR-0009-andan)."""
    return {
        "schema_version": estimate.schema_version,
        "benchmark_id": estimate.benchmark_id,
        "discipline": estimate.discipline,
        "label": estimate.label,
        "quantity": str(estimate.quantity),
        "unit": estimate.unit,
        "low_total": str(estimate.low_total),
        "normal_total": str(estimate.normal_total),
        "high_total": str(estimate.high_total),
        "currency": estimate.currency,
        "origin": estimate.origin,
    }


def comparison_to_payload(comparison: BenchmarkComparison) -> dict[str, Any]:
    return {
        "schema_version": comparison.schema_version,
        "benchmark_id": comparison.benchmark_id,
        "discipline": comparison.discipline,
        "label": comparison.label,
        "quantity": str(comparison.quantity),
        "unit": comparison.unit,
        "expected_low": str(comparison.expected_low),
        "expected_normal": str(comparison.expected_normal),
        "expected_high": str(comparison.expected_high),
        "detailed_total": str(comparison.detailed_total),
        "deviation_percent": str(comparison.deviation_percent),
        "verdict": comparison.verdict.value,
        "flagged": comparison.flagged,
        "currency": comparison.currency,
        "caveats": list(comparison.caveats),
    }
