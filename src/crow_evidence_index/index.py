from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EvidenceReference:
    evidence_id: str
    entity_kind: str
    entity_id: str
    field: str = "evidence_ids"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceIndexEntry:
    evidence_id: str
    kind: str
    source_id: str
    locator: str | None
    checksum: str | None
    confidence: float
    reference_count: int
    references: tuple[EvidenceReference, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "references": [reference.to_dict() for reference in self.references],
        }


@dataclass(frozen=True)
class SourceChecksumConflict:
    source_id: str
    checksums: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceIndexResult:
    schema_version: str
    evidence_count: int
    reference_count: int
    entries: tuple[EvidenceIndexEntry, ...]
    unreferenced_evidence_ids: tuple[str, ...]
    missing_evidence_ids: tuple[str, ...]
    duplicate_evidence_ids: tuple[str, ...]
    source_checksum_conflicts: tuple[SourceChecksumConflict, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "evidence_count": self.evidence_count,
            "reference_count": self.reference_count,
            "entries": [entry.to_dict() for entry in self.entries],
            "unreferenced_evidence_ids": list(self.unreferenced_evidence_ids),
            "missing_evidence_ids": list(self.missing_evidence_ids),
            "duplicate_evidence_ids": list(self.duplicate_evidence_ids),
            "source_checksum_conflicts": [
                conflict.to_dict() for conflict in self.source_checksum_conflicts
            ],
            "graph_mutated": False,
            "evidence_mutated": False,
            "inference_performed": False,
        }


class EvidenceIndexBuilder:
    """Build a deterministic read-only index over graph evidence and its references."""

    _REFERENCE_COLLECTIONS = ("objects", "relations", "properties")

    @staticmethod
    def _as_evidence_ids(value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if not isinstance(value, (list, tuple)):
            raise ValueError("evidence_ids must be a list or tuple")
        if any(not isinstance(item, str) or not item for item in value):
            raise ValueError("evidence_ids must contain non-empty strings")
        return tuple(value)

    def build(self, graph: dict[str, Any]) -> EvidenceIndexResult:
        raw_evidence = graph.get("evidence", [])
        if not isinstance(raw_evidence, list):
            raise ValueError("graph.evidence must be a list")

        evidence_by_id: dict[str, dict[str, Any]] = {}
        duplicate_ids: set[str] = set()
        for item in raw_evidence:
            if not isinstance(item, dict):
                raise ValueError("graph.evidence entries must be objects")
            evidence_id = item.get("id")
            if not isinstance(evidence_id, str) or not evidence_id:
                raise ValueError("evidence entry is missing a non-empty id")
            if evidence_id in evidence_by_id:
                duplicate_ids.add(evidence_id)
                continue
            evidence_by_id[evidence_id] = item

        references_by_evidence: dict[str, list[EvidenceReference]] = {
            evidence_id: [] for evidence_id in evidence_by_id
        }
        missing_ids: set[str] = set()
        reference_count = 0

        for collection in self._REFERENCE_COLLECTIONS:
            entities = graph.get(collection, [])
            if not isinstance(entities, list):
                raise ValueError(f"graph.{collection} must be a list")
            entity_kind = collection[:-1]
            for entity in entities:
                if not isinstance(entity, dict):
                    raise ValueError(f"graph.{collection} entries must be objects")
                entity_id = entity.get("id")
                if not isinstance(entity_id, str) or not entity_id:
                    raise ValueError(f"graph.{collection} entry is missing a non-empty id")
                for evidence_id in self._as_evidence_ids(entity.get("evidence_ids", [])):
                    reference_count += 1
                    reference = EvidenceReference(
                        evidence_id=evidence_id,
                        entity_kind=entity_kind,
                        entity_id=entity_id,
                    )
                    if evidence_id in references_by_evidence:
                        references_by_evidence[evidence_id].append(reference)
                    else:
                        missing_ids.add(evidence_id)

        entries: list[EvidenceIndexEntry] = []
        for evidence_id in sorted(evidence_by_id):
            item = evidence_by_id[evidence_id]
            refs = tuple(
                sorted(
                    references_by_evidence[evidence_id],
                    key=lambda ref: (ref.entity_kind, ref.entity_id, ref.field),
                )
            )
            confidence = item.get("confidence", 1.0)
            if not isinstance(confidence, (int, float)):
                raise ValueError(f"evidence {evidence_id} has invalid confidence")
            entries.append(
                EvidenceIndexEntry(
                    evidence_id=evidence_id,
                    kind=str(item.get("kind", "unknown")),
                    source_id=str(item.get("source_id", "")),
                    locator=item.get("locator") if isinstance(item.get("locator"), str) else None,
                    checksum=(
                        item.get("checksum") if isinstance(item.get("checksum"), str) else None
                    ),
                    confidence=float(confidence),
                    reference_count=len(refs),
                    references=refs,
                )
            )

        source_checksums: dict[str, dict[str, set[str]]] = {}
        for entry in entries:
            if not entry.source_id or not entry.checksum:
                continue
            checksum_map = source_checksums.setdefault(entry.source_id, {})
            checksum_map.setdefault(entry.checksum, set()).add(entry.evidence_id)

        conflicts: list[SourceChecksumConflict] = []
        for source_id, checksum_map in sorted(source_checksums.items()):
            if len(checksum_map) < 2:
                continue
            conflicts.append(
                SourceChecksumConflict(
                    source_id=source_id,
                    checksums=tuple(sorted(checksum_map)),
                    evidence_ids=tuple(
                        sorted(evidence_id for ids in checksum_map.values() for evidence_id in ids)
                    ),
                )
            )

        return EvidenceIndexResult(
            schema_version="crow-evidence-index-v0.1",
            evidence_count=len(entries),
            reference_count=reference_count,
            entries=tuple(entries),
            unreferenced_evidence_ids=tuple(
                entry.evidence_id for entry in entries if entry.reference_count == 0
            ),
            missing_evidence_ids=tuple(sorted(missing_ids)),
            duplicate_evidence_ids=tuple(sorted(duplicate_ids)),
            source_checksum_conflicts=tuple(conflicts),
        )

    def build_from_collections(
        self,
        *,
        evidence: Iterable[dict[str, Any]],
        objects: Iterable[dict[str, Any]] = (),
        relations: Iterable[dict[str, Any]] = (),
        properties: Iterable[dict[str, Any]] = (),
    ) -> EvidenceIndexResult:
        return self.build(
            {
                "evidence": list(evidence),
                "objects": list(objects),
                "relations": list(relations),
                "properties": list(properties),
            }
        )
