from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from crow_takeoff_consolidation import SourceKind, SourceLine, SourceTakeoff
from crow_takeoff_consolidation.models import LineKind

from .models import RiserConfiguration, RiserModelResult


def to_source_takeoff(
    result: RiserModelResult,
    config: RiserConfiguration,
    source_id: str,
) -> SourceTakeoff:
    """Materialsida: strängarna som kanalrader (kind/kod/dimension, meter).

    Rader per (medium, dimension) så konsolideringen kan korsläsa mot
    geometri- och tabellkällor med befintlig (kind, code, dimension)-nyckel.
    """
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    apartments: dict[tuple[str, str], set[str]] = defaultdict(set)
    for item in result.strings:
        key = (config.medium_code_for(item.kind), item.dimension)
        grouped[key].append(float(item.length_m))
        apartments[key].add(item.apartment_id)
    lines = tuple(
        SourceLine(
            source_id=source_id,
            source_kind=SourceKind.TEXT,
            kind=LineKind.DUCT,
            code=code,
            label=f"Schaktkanal {code}",
            dimension=dimension,
            quantity=round(sum(lengths), 2),
            unit="m",
            confidence=0.85,
            evidence={
                "derived_from": "riser_model",
                "string_count": len(lengths),
                "apartment_count": len(apartments[(code, dimension)]),
            },
        )
        for (code, dimension), lengths in sorted(grouped.items())
    )
    skipped = tuple(dict(item) for item in result.skipped)
    return SourceTakeoff(
        source_id=source_id, source_kind=SourceKind.TEXT, lines=lines, skipped=skipped
    )


def pressure_test_service_quantities(
    result: RiserModelResult,
    scope_percent: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Offertsida: provtryckningsmängder per trapphus ur strängmodellen.

    scope_percent följer provningsomfattningens klartext (schakt: 100).
    Delprovning avrundas alltid uppåt — man kan inte prova en halv sträng.
    """
    schakt_percent = int((scope_percent or {}).get("schakt", 100))
    if not 0 < schakt_percent <= 100:
        raise ValueError(f"schakt percent must be 1-100, got {schakt_percent}")
    per_stairwell = [
        {
            "stairwell_id": summary.stairwell_id,
            "apartment_count": summary.apartment_count,
            "string_count": summary.string_count,
            "strings_to_test": math.ceil(summary.string_count * schakt_percent / 100),
            "total_length_m": str(summary.total_length_m),
        }
        for summary in result.summaries
    ]
    return {
        "schema_version": "crow-riser-service-v0.1",
        "scope_percent": {"schakt": schakt_percent},
        "stairwells": per_stairwell,
        "totals": {
            "apartment_count": sum(item["apartment_count"] for item in per_stairwell),
            "string_count": result.string_count,
            "strings_to_test": sum(item["strings_to_test"] for item in per_stairwell),
            "total_length_m": str(result.total_length_m),
        },
    }
