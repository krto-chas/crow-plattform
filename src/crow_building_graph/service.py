from __future__ import annotations

from hashlib import sha256
from typing import Any

from .models import (
    CrowEvidence,
    CrowHistory,
    CrowObject,
    CrowProperty,
    CrowRelation,
    EvidenceKind,
    utc_now,
)
from .repository import GraphRepository

ALLOWED_RELATIONS = {
    "contains",
    "located_in",
    "belongs_to",
    "serves",
    "feeds",
    "returns_to",
    "connects_to",
    "references",
    "protects",
    "owns",
    "depends_on",
    "documents",
    "derived_from",
    "validated_by",
    "indirectly_served_by",
    "indirectly_located_in",
    "indirectly_depends_on",
}


def stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}:{digest}"


class BuildingGraphService:
    def __init__(self, repository: GraphRepository):
        self.repository = repository

    def create_evidence(
        self,
        *,
        kind: str,
        source_id: str,
        locator: str | None = None,
        checksum: str | None = None,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
        evidence_id: str | None = None,
    ) -> dict[str, Any]:
        self._confidence(confidence)
        entity = CrowEvidence(
            id=evidence_id or stable_id("evidence", kind, source_id, locator or "", checksum or ""),
            kind=EvidenceKind(kind),
            source_id=source_id,
            locator=locator,
            checksum=checksum,
            confidence=confidence,
            metadata=metadata or {},
        )
        return self.repository.add("evidence", entity)

    def create_object(
        self,
        *,
        object_type: str,
        discipline: str = "generic",
        name: str | None = None,
        evidence_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        object_id: str | None = None,
    ) -> dict[str, Any]:
        evidence = tuple(evidence_ids or ())
        self._require_evidence(evidence)
        entity = CrowObject(
            id=object_id or stable_id("object", discipline, object_type, name or utc_now()),
            object_type=object_type,
            discipline=discipline,
            name=name,
            evidence_ids=evidence,
            metadata=metadata or {},
        )
        payload = self.repository.add("objects", entity)
        self._history(entity.id, "object", "created", 1, payload)
        return payload

    def update_object(
        self,
        object_id: str,
        *,
        name: str | None = None,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        current = self.repository.get("objects", object_id)
        if current is None:
            raise KeyError(object_id)
        merged_metadata = dict(current.get("metadata") or {})
        if metadata:
            merged_metadata.update(metadata)
        entity = CrowObject(
            id=current["id"],
            object_type=current["object_type"],
            discipline=current["discipline"],
            name=name if name is not None else current.get("name"),
            status=status if status is not None else current.get("status", "active"),
            evidence_ids=tuple(current.get("evidence_ids") or ()),
            metadata=merged_metadata,
            revision=int(current.get("revision", 1)) + 1,
            created_at=current["created_at"],
            updated_at=utc_now(),
        )
        payload = self.repository.replace_object(entity)
        self._history(entity.id, "object", "updated", entity.revision, payload, actor)
        return payload

    def create_relation(
        self,
        *,
        source_id: str,
        relation_type: str,
        target_id: str,
        evidence_ids: list[str] | None = None,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
        relation_id: str | None = None,
    ) -> dict[str, Any]:
        if relation_type not in ALLOWED_RELATIONS:
            raise ValueError(f"Okänd relationstyp: {relation_type}")
        if source_id == target_id:
            raise ValueError("Självrelationer är inte tillåtna")
        self._require_object(source_id)
        self._require_object(target_id)
        evidence = tuple(evidence_ids or ())
        self._require_evidence(evidence)
        self._confidence(confidence)
        entity = CrowRelation(
            id=relation_id or stable_id("relation", source_id, relation_type, target_id),
            source_id=source_id,
            relation_type=relation_type,
            target_id=target_id,
            evidence_ids=evidence,
            confidence=confidence,
            metadata=metadata or {},
        )
        payload = self.repository.add("relations", entity)
        self._history(entity.id, "relation", "created", 1, payload)
        return payload

    def create_property(
        self,
        *,
        owner_id: str,
        name: str,
        value: Any,
        unit: str | None = None,
        evidence_ids: list[str] | None = None,
        confidence: float = 1.0,
        property_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_object(owner_id)
        evidence = tuple(evidence_ids or ())
        self._require_evidence(evidence)
        self._confidence(confidence)
        entity = CrowProperty(
            id=property_id or stable_id("property", owner_id, name, str(value), unit or ""),
            owner_id=owner_id,
            name=name,
            value=value,
            unit=unit,
            evidence_ids=evidence,
            confidence=confidence,
        )
        payload = self.repository.add("properties", entity)
        self._history(entity.id, "property", "created", 1, payload)
        return payload

    def graph(self) -> dict[str, Any]:
        data = self.repository.load()
        return {**data, "summary": {key: len(value) for key, value in data.items()}}

    def neighbors(self, object_id: str, relation_type: str | None = None) -> dict[str, Any]:
        self._require_object(object_id)
        data = self.repository.load()
        relations = [
            r
            for r in data["relations"]
            if (r["source_id"] == object_id or r["target_id"] == object_id)
            and (relation_type is None or r["relation_type"] == relation_type)
        ]
        ids = {r["target_id"] if r["source_id"] == object_id else r["source_id"] for r in relations}
        return {
            "object_id": object_id,
            "relations": relations,
            "objects": [o for o in data["objects"] if o["id"] in ids],
        }

    def _require_object(self, object_id: str) -> None:
        if self.repository.get("objects", object_id) is None:
            raise KeyError(object_id)

    def _require_evidence(self, evidence_ids: tuple[str, ...]) -> None:
        missing = [eid for eid in evidence_ids if self.repository.get("evidence", eid) is None]
        if missing:
            raise KeyError(",".join(missing))

    @staticmethod
    def _confidence(value: float) -> None:
        if not 0 <= value <= 1:
            raise ValueError("Confidence måste ligga mellan 0 och 1")

    def _history(
        self,
        entity_id: str,
        entity_kind: str,
        action: str,
        revision: int,
        snapshot: dict[str, Any],
        actor: str = "system",
    ) -> None:
        history = CrowHistory(
            id=stable_id("history", entity_id, str(revision), action),
            entity_id=entity_id,
            entity_kind=entity_kind,
            action=action,
            revision=revision,
            snapshot=snapshot,
            actor=actor,
        )
        self.repository.add("history", history)
