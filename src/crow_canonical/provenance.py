from __future__ import annotations

from dataclasses import dataclass

from .models import CanonicalObject, CanonicalRelation


@dataclass(frozen=True)
class ProvenanceStep:
    stage: str
    reference: str
    description: str


@dataclass(frozen=True)
class ProvenanceTrace:
    subject_id: str
    steps: tuple[ProvenanceStep, ...]


class CanonicalProvenanceService:
    """Expose the deterministic provenance already carried by CCM entities."""

    def for_object(self, item: CanonicalObject) -> ProvenanceTrace:
        steps = [
            ProvenanceStep("source", item.evidence.source_id, item.evidence.source_kind),
        ]
        interpretation_id = item.evidence.metadata.get("interpretation_id")
        if isinstance(interpretation_id, str):
            steps.append(ProvenanceStep("interpretation", interpretation_id, "vent_text"))
        steps.append(ProvenanceStep("canonical_object", item.canonical_id, item.object_type.value))
        return ProvenanceTrace(subject_id=item.canonical_id, steps=tuple(steps))

    def for_relation(self, item: CanonicalRelation) -> ProvenanceTrace:
        steps = [
            ProvenanceStep("source", item.evidence.source_id, item.evidence.source_kind),
        ]
        assertion_id = item.metadata.get("assertion_id")
        if isinstance(assertion_id, str):
            steps.append(ProvenanceStep("relation_assertion", assertion_id, item.relation_type))
        steps.append(ProvenanceStep("canonical_relation", item.canonical_id, item.relation_type))
        return ProvenanceTrace(subject_id=item.canonical_id, steps=tuple(steps))
