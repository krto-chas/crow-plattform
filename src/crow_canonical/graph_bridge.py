from __future__ import annotations

from typing import Any

from crow_building_graph import BuildingGraphService, stable_id

from .models import CanonicalObject


class CanonicalGraphBridge:
    """Persist CCM objects in Building Graph with evidence on object and properties."""

    def __init__(self, graph: BuildingGraphService) -> None:
        self._graph = graph

    def persist(self, canonical: CanonicalObject) -> dict[str, Any]:
        evidence_id = stable_id(
            "evidence",
            canonical.evidence.source_kind,
            canonical.evidence.source_id,
            canonical.evidence.locator or "",
            canonical.canonical_id,
        )
        evidence = self._graph.create_evidence(
            kind="text",
            source_id=canonical.evidence.source_id,
            locator=canonical.evidence.locator,
            confidence=canonical.evidence.confidence,
            metadata={
                **canonical.evidence.metadata,
                "canonical_id": canonical.canonical_id,
                "source_kind": canonical.evidence.source_kind,
            },
            evidence_id=evidence_id,
        )
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
