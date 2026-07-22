from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from crow_vent import VentTextInterpretation

from .models import CanonicalEvidence, CanonicalObject, CanonicalObjectType, CanonicalRelation
from .vent_adapter import VentCanonicalAdapter


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"ccm:{prefix}:{digest}"


@dataclass(frozen=True)
class CanonicalAssembly:
    objects: tuple[CanonicalObject, ...]
    relations: tuple[CanonicalRelation, ...]


class VentCanonicalAssembler:
    """Build a small evidence-preserving CCM assembly from vent interpretations."""

    def __init__(self, adapter: VentCanonicalAdapter | None = None) -> None:
        self._adapter = adapter or VentCanonicalAdapter()

    def assemble(self, interpretations: list[VentTextInterpretation]) -> CanonicalAssembly:
        objects: list[CanonicalObject] = []
        relations: list[CanonicalRelation] = []
        systems: dict[str, CanonicalObject] = {}

        for interpretation in interpretations:
            canonical = self._adapter.convert(interpretation)
            if canonical is None:
                continue
            objects.append(canonical)
            raw_system = interpretation.evidence.get("system_context")
            if not isinstance(raw_system, str) or not raw_system.strip():
                continue
            system_name = raw_system.strip().upper()
            system = systems.get(system_name)
            if system is None:
                evidence = CanonicalEvidence(
                    source_id=interpretation.source_id,
                    source_kind="drawing_text",
                    locator=interpretation.evidence.get("entity_handle"),
                    confidence=interpretation.confidence,
                    metadata={
                        "derived_from": "system_context",
                        "system_context": system_name,
                        "interpretation_id": interpretation.interpretation_id,
                    },
                )
                system = CanonicalObject(
                    canonical_id=_stable_id("system", interpretation.source_id, system_name),
                    object_type=CanonicalObjectType.VENTILATION_SYSTEM,
                    discipline="ventilation",
                    name=system_name,
                    confidence=interpretation.confidence,
                    properties={"system_code": system_name},
                    evidence=evidence,
                )
                systems[system_name] = system
                objects.append(system)
            relations.append(
                CanonicalRelation(
                    canonical_id=_stable_id(
                        "relation", canonical.canonical_id, "belongs_to", system.canonical_id
                    ),
                    source_id=canonical.canonical_id,
                    relation_type="belongs_to",
                    target_id=system.canonical_id,
                    confidence=min(canonical.confidence, system.confidence),
                    evidence=canonical.evidence,
                    metadata={"derivation": "explicit_system_context"},
                )
            )
        return CanonicalAssembly(objects=tuple(objects), relations=tuple(relations))
