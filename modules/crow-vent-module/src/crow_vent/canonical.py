from __future__ import annotations

from hashlib import sha256
from typing import Any

from crow_canonical.assembly import CanonicalAssembly as CanonicalAssembly
from crow_canonical.models import (
    CanonicalEvidence,
    CanonicalObject,
    CanonicalObjectType,
    CanonicalRelation,
)

from .text_interpretation import VentTextInterpretation

_CATEGORY_MAP: tuple[tuple[str, CanonicalObjectType], ...] = (
    ("QAB_", CanonicalObjectType.AIR_HANDLING_UNIT),
    ("QE_", CanonicalObjectType.FAN),
    ("QF_", CanonicalObjectType.HEAT_EXCHANGER),
    ("QG_QH_", CanonicalObjectType.AIR_TREATMENT_COMPONENT),
    ("QJ_", CanonicalObjectType.DAMPER),
    ("QK_", CanonicalObjectType.SILENCER),
    ("QM_", CanonicalObjectType.AIR_TERMINAL),
    ("ovrigt_", CanonicalObjectType.ACCESSORY),
)


def _canonical_id(interpretation: VentTextInterpretation) -> str:
    digest = sha256(
        f"{interpretation.source_id}|{interpretation.interpretation_id}".encode()
    ).hexdigest()[:20]
    return f"ccm:vent:{digest}"


def _component_type(category: str) -> CanonicalObjectType:
    for prefix, object_type in _CATEGORY_MAP:
        if category.startswith(prefix):
            return object_type
    return CanonicalObjectType.ACCESSORY


class VentCanonicalAdapter:
    """Translate deterministic vent text interpretations into CCM objects."""

    def convert(self, interpretation: VentTextInterpretation) -> CanonicalObject | None:
        if interpretation.kind == "unknown":
            return None

        evidence_metadata: dict[str, Any] = dict(interpretation.evidence)
        evidence_metadata["interpretation_id"] = interpretation.interpretation_id
        evidence_metadata["raw_text"] = interpretation.raw_text
        evidence = CanonicalEvidence(
            source_id=interpretation.source_id,
            source_kind="drawing_text",
            locator=interpretation.evidence.get("entity_handle"),
            confidence=interpretation.confidence,
            metadata=evidence_metadata,
        )

        if interpretation.duct is not None:
            duct = interpretation.duct
            properties: dict[str, Any] = {
                "medium_code": duct.medium_code,
                "medium": duct.medium_label,
                "material_code": duct.material_code,
                "material": duct.material_label,
                "material_subgroup": duct.material_subgroup,
                "shape": duct.dimension.shape,
                "diameter_mm": duct.dimension.diameter_mm,
                "width_mm": duct.dimension.width_mm,
                "height_mm": duct.dimension.height_mm,
                "insulation_code": duct.insulation_code,
                "insulation": duct.insulation_label,
                "insulation_subgroup": duct.insulation_subgroup,
            }
            return CanonicalObject(
                canonical_id=_canonical_id(interpretation),
                object_type=CanonicalObjectType.DUCT,
                discipline="ventilation",
                name=interpretation.normalized_text,
                confidence=interpretation.confidence,
                properties=properties,
                evidence=evidence,
                status=interpretation.status,
                review_reasons=interpretation.review_reasons,
            )

        component = interpretation.component
        if component is None:
            return None
        return CanonicalObject(
            canonical_id=_canonical_id(interpretation),
            object_type=_component_type(component.category),
            discipline="ventilation",
            name=interpretation.normalized_text,
            confidence=interpretation.confidence,
            properties={
                "code": component.code,
                "number": component.number,
                "label": component.label,
                "category": component.category,
                "alternatives": list(component.alternatives),
            },
            evidence=evidence,
            status=interpretation.status,
            review_reasons=interpretation.review_reasons,
        )


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"ccm:{prefix}:{digest}"


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
