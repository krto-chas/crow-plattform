from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

from .models import (
    ApartmentLike,
    LevelTable,
    RiserConfiguration,
    RiserModelResult,
    RiserString,
    StairwellSummary,
)

_LENGTH_QUANTUM = Decimal("0.01")


def build_riser_model(
    apartments: Iterable[ApartmentLike],
    levels: LevelTable,
    config: RiserConfiguration,
) -> RiserModelResult:
    """Bygger vertikala strängar per lägenhet ur planhöjder och konfiguration.

    Lägenheter vars plan saknar plushöjd hoppas inte tyst över utan hamnar i
    `skipped` med orsak — samma ärlighetsprincip som takeoff-konsolideringen.
    """
    strings: list[RiserString] = []
    skipped: list[dict[str, str]] = []
    seen: set[str] = set()
    for apartment in apartments:
        if apartment.apartment_id in seen:
            continue
        seen.add(apartment.apartment_id)
        height = levels.height_to(apartment.plan, config.top_plan)
        if height is None:
            skipped.append(
                {
                    "apartment_id": apartment.apartment_id,
                    "plan": apartment.plan,
                    "reason": "missing_or_inverted_level",
                }
            )
            continue
        length = (height + config.attic_allowance_m).quantize(
            _LENGTH_QUANTUM, rounding=ROUND_HALF_UP
        )
        for kind in config.string_kinds:
            strings.append(
                RiserString(
                    apartment_id=apartment.apartment_id,
                    stairwell_id=apartment.stairwell_id,
                    kind=kind,
                    plan=apartment.plan,
                    dimension=config.dimension_for(kind),
                    length_m=length,
                    evidence={
                        "top_plan": config.top_plan,
                        "attic_allowance_m": str(config.attic_allowance_m),
                    },
                )
            )
    grouped: dict[str, list[RiserString]] = defaultdict(list)
    for item in strings:
        grouped[item.stairwell_id].append(item)
    summaries = tuple(
        StairwellSummary(
            stairwell_id=stairwell,
            apartment_count=len({item.apartment_id for item in members}),
            string_count=len(members),
            total_length_m=sum((item.length_m for item in members), Decimal("0")),
        )
        for stairwell, members in sorted(grouped.items())
    )
    return RiserModelResult(strings=tuple(strings), summaries=summaries, skipped=tuple(skipped))
