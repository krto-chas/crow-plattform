from __future__ import annotations

from decimal import Decimal

import pytest

from crow_benchmark_pricing import (
    ORIGIN_INFERRED,
    SCHEMA_VERSION,
    BenchmarkRange,
    ComparisonVerdict,
    compare_detailed_total,
    compare_takeoff_pricing,
    comparison_to_payload,
    estimate_to_payload,
    load_benchmarks,
    quick_estimate,
)


def test_lexicon_loads_vent_benchmarks() -> None:
    book = load_benchmarks()
    benchmarks = book.benchmarks("vent")
    assert len(benchmarks) >= 6
    units = {b.unit for b in benchmarks}
    assert {"lgh", "rum", "m2_bta", "st"} <= units


def test_quick_estimate_scales_range_by_quantity() -> None:
    book = load_benchmarks()
    benchmark = book.lookup("vent", "flerbostadshus_ftx_lgh")
    estimate = quick_estimate(benchmark, Decimal(33), book.currency)
    assert estimate.low_total == Decimal(33) * benchmark.unit_range.low
    assert estimate.normal_total == Decimal(33) * benchmark.unit_range.normal
    assert estimate.high_total == Decimal(33) * benchmark.unit_range.high
    assert estimate.low_total < estimate.normal_total < estimate.high_total


def test_quick_estimate_is_always_inferred() -> None:
    book = load_benchmarks()
    benchmark = book.lookup("vent", "hotell_rum")
    estimate = quick_estimate(benchmark, Decimal(80), book.currency)
    assert estimate.origin == ORIGIN_INFERRED
    payload = estimate_to_payload(estimate)
    assert payload["origin"] == ORIGIN_INFERRED
    assert payload["schema_version"] == SCHEMA_VERSION


def test_unknown_benchmark_lists_available_ids() -> None:
    book = load_benchmarks()
    with pytest.raises(ValueError, match="flerbostadshus_ftx_lgh"):
        book.lookup("vent", "finns_inte")


def test_range_ordering_is_validated() -> None:
    with pytest.raises(ValueError, match="low <= normal <= high"):
        BenchmarkRange(low=Decimal(100), normal=Decimal(90), high=Decimal(200))
    with pytest.raises(ValueError, match="low <= normal <= high"):
        BenchmarkRange(low=Decimal(0), normal=Decimal(90), high=Decimal(200))


def test_comparison_within_range() -> None:
    book = load_benchmarks()
    benchmark = book.lookup("vent", "flerbostadshus_ftx_lgh")
    comparison = compare_detailed_total(benchmark, Decimal(30), detailed_total=Decimal(2_100_000), currency=book.currency)
    assert comparison.verdict is ComparisonVerdict.WITHIN_RANGE
    assert not comparison.flagged
    assert comparison.deviation_percent == Decimal("0.0")


def test_comparison_flags_above_range() -> None:
    book = load_benchmarks()
    benchmark = book.lookup("vent", "flerbostadshus_ftx_lgh")
    comparison = compare_detailed_total(benchmark, Decimal(30), detailed_total=Decimal(3_000_000), currency=book.currency)
    assert comparison.verdict is ComparisonVerdict.ABOVE_RANGE
    assert comparison.flagged
    assert comparison.deviation_percent > 0


def test_comparison_flags_below_range() -> None:
    book = load_benchmarks()
    benchmark = book.lookup("vent", "flerbostadshus_ftx_lgh")
    comparison = compare_detailed_total(benchmark, Decimal(30), detailed_total=Decimal(1_000_000), currency=book.currency)
    assert comparison.verdict is ComparisonVerdict.BELOW_RANGE
    assert comparison.flagged
    assert comparison.deviation_percent < 0


def test_takeoff_pricing_adapter_reads_grand_total() -> None:
    book = load_benchmarks()
    benchmark = book.lookup("vent", "flerbostadshus_ftx_lgh")
    payload = {"schema_version":"crow-takeoff-pricing-v0.1","currency":"SEK","grand_total":2050000.0,"unpriced_line_count":0,"reservation_count":0}
    comparison = compare_takeoff_pricing(benchmark, Decimal(30), payload)
    assert comparison.detailed_total == Decimal("2050000.00")
    assert comparison.verdict is ComparisonVerdict.WITHIN_RANGE
    assert comparison.caveats == ()


def test_takeoff_pricing_adapter_carries_incompleteness_caveats() -> None:
    book = load_benchmarks()
    benchmark = book.lookup("vent", "flerbostadshus_ftx_lgh")
    payload = {"schema_version":"crow-takeoff-pricing-v0.1","currency":"SEK","grand_total":1200000.0,"unpriced_line_count":4,"reservation_count":2}
    comparison = compare_takeoff_pricing(benchmark, Decimal(30), payload)
    assert comparison.verdict is ComparisonVerdict.BELOW_RANGE
    assert len(comparison.caveats) == 2
    assert "undre gräns" in comparison.caveats[0]
    serialised = comparison_to_payload(comparison)
    assert serialised["caveats"] == list(comparison.caveats)


def test_takeoff_pricing_adapter_rejects_wrong_schema() -> None:
    book = load_benchmarks()
    benchmark = book.lookup("vent", "flerbostadshus_ftx_lgh")
    with pytest.raises(ValueError, match="crow-takeoff-pricing"):
        compare_takeoff_pricing(benchmark, Decimal(30), {"schema_version":"crow-ovk-pricing-v0.2"})


def test_quantities_and_totals_are_validated() -> None:
    book = load_benchmarks()
    benchmark = book.lookup("vent", "hotell_rum")
    with pytest.raises(ValueError, match="quantity must be positive"):
        quick_estimate(benchmark, Decimal(0), book.currency)
    with pytest.raises(ValueError, match="detailed_total must be non-negative"):
        compare_detailed_total(benchmark, Decimal(10), Decimal(-1), book.currency)


def test_comparison_is_deterministic() -> None:
    book = load_benchmarks()
    benchmark = book.lookup("vent", "lokal_ftx_m2")
    a = compare_detailed_total(benchmark, Decimal("2400"), Decimal(1_150_000), book.currency)
    b = compare_detailed_total(benchmark, Decimal("2400"), Decimal(1_150_000), book.currency)
    assert a == b
