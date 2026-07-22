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
        identity_anchors: dict[tuple[str, str, str, str], CanonicalObject] = {}

        for interpretation in interpretations:
            canonical = self._adapter.convert(interpretation)
            if canonical is None:
                continue
            objects.append(canonical)
            raw_system = interpretation.evidence.get("system_context")
            if not isinstance(raw_system, str) or not raw_system.strip():
                continue
            system_name = raw_system.strip().upper()

            component = interpretation.component
            if component is not None and component.number is not None:
                identity_key = (
                    canonical.object_type.value,
                    component.code,
                    component.number,
                    system_name,
                )
                anchor = identity_anchors.get(identity_key)
                if anchor is None:
                    identity_anchors[identity_key] = canonical
                elif anchor.canonical_id != canonical.canonical_id:
                    relations.append(
                        CanonicalRelation(
                            canonical_id=_stable_id(
                                "relation",
                                canonical.canonical_id,
                                "same_as_candidate",
                                anchor.canonical_id,
                            ),
                            source_id=canonical.canonical_id,
                            relation_type="same_as_candidate",
                            target_id=anchor.canonical_id,
                            confidence=min(canonical.confidence, anchor.confidence),
                            evidence=canonical.evidence,
                            metadata={
                                "derivation": "exact_designation_and_system_context",
                                "identity_key": {
                                    "object_type": canonical.object_type.value,
                                    "code": component.code,
                                    "number": component.number,
                                    "system_context": system_name,
                                },
                                "status": "review_required",
                            },
                        )
                    )

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
