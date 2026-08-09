from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class VentComponentDefinition:
    code: str
    name_sv: str
    category: str
    airflow_role: str | None = None
    aliases: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class VentClassification:
    classification_id: str
    system_id: str
    candidate_group_id: str
    source_value: str
    component_code: str | None
    component_name: str | None
    category: str | None
    airflow_role: str | None
    confidence: float
    status: str
    evidence: dict[str, Any] = field(default_factory=dict)
