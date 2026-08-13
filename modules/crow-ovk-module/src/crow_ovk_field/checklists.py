"""Checklistmallar för teknikutrymmen. Installationsdata, kundutbytbar JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources

from .models import TechnicalSpaceKind


@dataclass(frozen=True, slots=True)
class ChecklistItem:
    item_id: str
    label: str


def load_checklists() -> dict[TechnicalSpaceKind, tuple[ChecklistItem, ...]]:
    resource = resources.files("crow_ovk_field").joinpath("checklists.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    result: dict[TechnicalSpaceKind, tuple[ChecklistItem, ...]] = {}
    for kind_value, items in payload.get("checklists", {}).items():
        kind = TechnicalSpaceKind(kind_value)
        entries = tuple(
            ChecklistItem(item_id=str(item["id"]), label=str(item["label"])) for item in items
        )
        ids = [entry.item_id for entry in entries]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate checklist item ids for {kind_value!r}")
        result[kind] = entries
    return result
