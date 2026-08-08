from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources


@dataclass(frozen=True, slots=True)
class DefectType:
    defect_id: str
    label: str
    description: str
    default_rule_refs: tuple[str, ...] = ()


def load_defect_types() -> tuple[DefectType, ...]:
    text = resources.files("crow_ovk_field").joinpath("defect_types.json").read_text(encoding="utf-8")
    payload = json.loads(text)
    items = payload.get("defect_types", [])
    result = tuple(
        DefectType(
            defect_id=str(item["id"]),
            label=str(item["label"]),
            description=str(item.get("description", "")),
            default_rule_refs=tuple(str(value) for value in item.get("default_rule_refs", [])),
        )
        for item in items
    )
    ids = [item.defect_id for item in result]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate defect type ids")
    return result


def defect_type_by_id(defect_id: str) -> DefectType:
    for item in load_defect_types():
        if item.defect_id == defect_id:
            return item
    raise KeyError(defect_id)
