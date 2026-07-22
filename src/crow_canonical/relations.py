from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from typing import Any

from .assembly import CanonicalAssembly
from .models import CanonicalEvidence, CanonicalRelation


class CanonicalRelationType(StrEnum):
    FEEDS = "feeds"
    RETURNS_FROM = "returns_from"
    PASSES_THROUGH = "passes_through"
    CONTAINS = "contains"
    LOCATED_IN = "located_in"


@dataclass(frozen=True)
class ExplicitRelationAssertion:
    source_id: str
    relation_type: CanonicalRelationType
    target_id: str
    evidence: CanonicalEvidence
    confidence: float = 1.0
    assertion_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CanonicalRelationshipEngine:
    """Create relations only from explicit, evidence-bearing assertions.

    This engine deliberately performs no geometric, lexical, or AI inference.
    """

    def apply(
        self,
        assembly: CanonicalAssembly,
        assertions: list[ExplicitRelationAssertion],
    ) -> CanonicalAssembly:
        object_ids = {item.canonical_id for item in assembly.objects}
        relations = list(assembly.relations)
        existing_ids = {item.canonical_id for item in relations}

        for assertion in assertions:
            self._validate(assertion, object_ids)
            assertion_id = assertion.assertion_id or self._stable_assertion_id(assertion)
            relation_id = self._stable_relation_id(assertion, assertion_id)
            if relation_id in existing_ids:
                continue
            relations.append(
                CanonicalRelation(
                    canonical_id=relation_id,
                    source_id=assertion.source_id,
                    relation_type=assertion.relation_type.value,
                    target_id=assertion.target_id,
                    confidence=assertion.confidence,
                    evidence=assertion.evidence,
                    metadata={
                        **assertion.metadata,
                        "derivation": "explicit_relation_assertion",
                        "assertion_id": assertion_id,
                        "inference_performed": False,
                    },
                )
            )
            existing_ids.add(relation_id)

        return CanonicalAssembly(objects=assembly.objects, relations=tuple(relations))

    @staticmethod
    def _validate(assertion: ExplicitRelationAssertion, object_ids: set[str]) -> None:
        if assertion.source_id not in object_ids:
            raise KeyError(assertion.source_id)
        if assertion.target_id not in object_ids:
            raise KeyError(assertion.target_id)
        if assertion.source_id == assertion.target_id:
            raise ValueError("Självrelationer är inte tillåtna")
        if not 0 <= assertion.confidence <= 1:
            raise ValueError("Confidence måste ligga mellan 0 och 1")

    @staticmethod
    def _stable_assertion_id(assertion: ExplicitRelationAssertion) -> str:
        digest = sha256(
            "|".join(
                (
                    assertion.source_id,
                    assertion.relation_type.value,
                    assertion.target_id,
                    assertion.evidence.source_id,
                    assertion.evidence.locator or "",
                )
            ).encode("utf-8")
        ).hexdigest()[:20]
        return f"ccm:assertion:{digest}"

    @staticmethod
    def _stable_relation_id(
        assertion: ExplicitRelationAssertion,
        assertion_id: str,
    ) -> str:
        digest = sha256(
            "|".join(
                (
                    assertion.source_id,
                    assertion.relation_type.value,
                    assertion.target_id,
                    assertion_id,
                )
            ).encode("utf-8")
        ).hexdigest()[:20]
        return f"ccm:relation:{digest}"
