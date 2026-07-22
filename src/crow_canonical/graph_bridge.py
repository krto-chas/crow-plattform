from __future__ import annotations

from typing import Any

from crow_building_graph import BuildingGraphService, stable_id

from .assembly import CanonicalAssembly
from .models import CanonicalEvidence, CanonicalObject, CanonicalRelation


class CanonicalGraphBridge:
    """Persist CCM objects and relations in Building Graph with shared evidence."""

    def __init__(self, graph: BuildingGraphService) -> None:
        self._graph = graph

    def _persist_evidence(self, canonical_id: str, evidence: CanonicalEvidence) -> dict[str, Any]:
        evidence_id = stable_id(
            "evidence",
            evidence.source_kind,
            evidence.source_id,
            evidence.locator or "",
            canonical_id,
        )
        return self._graph.create_evidence(
            kind="text",
            source_id=evidence.source_id,
            locator=evidence.locator,
            confidence=evidence.confidence,
            metadata={
                **evidence.metadata,
                "canonical_id": canonical_id,
                "source_kind": evidence.source_kind,
            },
            evidence_id=evidence_id,
        )

    def persist(self, canonical: CanonicalObject) -> dict[str, Any]:
        evidence = self._persist_evidence(canonical.canonical_id, canonical.evidence)
        graph_object = self._graph.create_object(
            object_type=canonical.object_type.value,
            discipline=canonical.discipline,
            name=canonical.name,
            evidence_ids=[evidence["id"]],
            metadata={
                "canonical_id": canonical.canonical_id,
                "confidence": canonical.confidence,
                "status": canonical.status,
                "review_reasons": list(canonical.review_reasons),
            },
            object_id=canonical.canonical_id,
        )
        properties = []
        for name, value in canonical.properties.items():
            if value is None:
                continue
            properties.append(
                self._graph.create_property(
                    owner_id=graph_object["id"],
                    name=name,
                    value=value,
                    evidence_ids=[evidence["id"]],
                    confidence=canonical.confidence,
                )
            )
        return {"object": graph_object, "evidence": evidence, "properties": properties}

    def persist_relation(self, relation: CanonicalRelation) -> dict[str, Any]:
        evidence = self._persist_evidence(relation.canonical_id, relation.evidence)
        graph_relation = self._graph.create_relation(
            source_id=relation.source_id,
            relation_type=relation.relation_type,
            target_id=relation.target_id,
            evidence_ids=[evidence["id"]],
            confidence=relation.confidence,
            metadata={**relation.metadata, "canonical_id": relation.canonical_id},
            relation_id=relation.canonical_id,
        )
        return {"relation": graph_relation, "evidence": evidence}

    def persist_assembly(self, assembly: CanonicalAssembly) -> dict[str, Any]:
        objects = [self.persist(item) for item in assembly.objects]
        relations = [self.persist_relation(item) for item in assembly.relations]
        return {"objects": objects, "relations": relations}
