from __future__ import annotations

from hashlib import sha256
from typing import Any

from crow_vent import VentTextInterpretation

from .models import CanonicalEvidence, CanonicalObject, CanonicalObjectType

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
