from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

_POINTS_PER_METRE_OF_PAPER = Decimal("2834.645669291339")  # 72 / 0.0254
_QUANTUM = Decimal("0.01")


def point_distance_m(
    first: tuple[float, float],
    second: tuple[float, float],
    scale_denominator: int,
) -> Decimal:
    """Verklig längd i meter mellan två PDF-punktkoordinater vid given skala.

    Avstånd i PDF-punkter (1 pt = 1/72 tum) × skalnämnare → verklighet.
    Används för längdbedömning ur etikettkoordinater (t.ex. rektangulära
    samlingskanalers dimensionstexter); tolerans dokumenteras av anroparen.
    """
    if scale_denominator <= 0:
        raise ValueError("scale_denominator must be positive")
    distance_pt = Decimal(str(math.hypot(second[0] - first[0], second[1] - first[1])))
    metres = distance_pt / _POINTS_PER_METRE_OF_PAPER * scale_denominator
    return metres.quantize(_QUANTUM, rounding=ROUND_HALF_UP)
