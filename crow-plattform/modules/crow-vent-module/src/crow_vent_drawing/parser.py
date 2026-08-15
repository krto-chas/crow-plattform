from __future__ import annotations

import re
from decimal import Decimal

from .models import ApartmentRecord, DrawingRef, LevelObservation

_DRAWING_NUMBER = re.compile(r"V-\d{2}-\d-(?P<series>[45])(?P<plan>\d{2})(?P<part>\d{2})")
_APARTMENT_ID = re.compile(r"(?P<stairwell>4[1-5])-(?P<plan>1\d)(?P<index>\d{2})")
_ROK = re.compile(r"(?P<rok>\d)\s*RoK", re.IGNORECASE)
_AREA = re.compile(r"A\s*:\s*(?P<area>\d{1,3},\d)\s*m2")
_LEVEL = re.compile(r"\+(?P<level>\d{2},\d{2})")
_WINDOW = 60

_STAIRWELL_LABELS = {
    "41": "trh-1",
    "42": "trh-2",
    "43": "trh-3",
    "44": "trh-4",
    "45": "radhus",
}


def parse_drawing_number(document_id: str) -> DrawingRef | None:
    match = _DRAWING_NUMBER.search(document_id)
    if match is None:
        return None
    return DrawingRef(
        number=match.group(0),
        series=match.group("series"),
        plan=match.group("plan"),
        part=match.group("part"),
    )


def stairwell_label(stairwell_code: str) -> str:
    return _STAIRWELL_LABELS[stairwell_code]


def extract_apartments(text: str, document_id: str) -> tuple[ApartmentRecord, ...]:
    drawing = parse_drawing_number(document_id)
    flattened = " ".join(text.split())
    matches = list(_APARTMENT_ID.finditer(flattened))
    records: dict[str, ApartmentRecord] = {}
    for position, match in enumerate(matches):
        window_end = (
            matches[position + 1].start()
            if position + 1 < len(matches)
            else min(len(flattened), match.end() + _WINDOW)
        )
        window = flattened[match.end() : window_end]
        rok_match = _ROK.search(window)
        area_match = _AREA.search(window)
        apartment_plan = match.group("plan")
        authoritative = drawing is not None and drawing.plan == apartment_plan
        apartment_id = match.group(0)
        area = Decimal(area_match.group("area").replace(",", ".")) if area_match else None
        record = ApartmentRecord(
            apartment_id=apartment_id,
            stairwell_id=stairwell_label(match.group("stairwell")),
            plan=apartment_plan,
            rok=int(rok_match.group("rok")) if rok_match else None,
            area_m2=area if authoritative else None,
            area_is_authoritative=authoritative and area is not None,
            source_document=document_id,
        )
        existing = records.get(apartment_id)
        upgrades = (
            existing is not None
            and record.area_is_authoritative
            and not existing.area_is_authoritative
        )
        if existing is None or upgrades:
            records[apartment_id] = record
    return tuple(records[key] for key in sorted(records))


def extract_levels(text: str, document_id: str) -> tuple[LevelObservation, ...]:
    seen: set[Decimal] = set()
    observations: list[LevelObservation] = []
    for match in _LEVEL.finditer(text):
        elevation = Decimal(match.group("level").replace(",", "."))
        if elevation in seen:
            continue
        seen.add(elevation)
        observations.append(LevelObservation(elevation_m=elevation, source_document=document_id))
    return tuple(sorted(observations, key=lambda item: item.elevation_m))
