from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from crow_canonical.models import CanonicalEvidence
from crow_canonical.relations import (
    CanonicalRelationType,
    ExplicitRelationAssertion,
)

_IFC_ROW = re.compile(
    r"^(#\d+)\s*=\s*(IFC[A-Z0-9_]+)\s*\((.*)\);\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_IFC_REF = re.compile(r"#\d+")


@dataclass(frozen=True)
class IfcExplicitRelation:
    relation_entity_id: str
    relation_entity_type: str
    relation_type: CanonicalRelationType
    source_ifc_id: str
    target_ifc_id: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class IfcRelationExtraction:
    source_id: str
    source_checksum_sha256: str
    relations: tuple[IfcExplicitRelation, ...]
    relation_entity_counts: dict[str, int]
    supported_relation_entity_counts: dict[str, int]
    unsupported_relation_entity_counts: dict[str, int]
    malformed_supported_entities: tuple[str, ...]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class IfcRelationMappingResult:
    assertions: tuple[ExplicitRelationAssertion, ...]
    unmapped_ifc_ids: tuple[str, ...]
    skipped_relation_entity_ids: tuple[str, ...]
    metadata: dict[str, Any]


class IfcRelationExtractor:
    """Extract only explicit IFC relationship semantics from STEP text.

    Supported IFC relationships are deliberately explicit and non-geometric:
    - IfcRelAggregates -> ``contains``
    - IfcRelContainedInSpatialStructure -> ``located_in``
    - IfcRelDefinesByType -> ``typed_by``
    - IfcRelAssignsToGroup -> ``assigned_to``
    - IfcRelServicesBuildings -> ``serves``
    - IfcRelAssociatesMaterial -> ``associated_with_material``
    - IfcRelCoversBldgElements -> ``covers``

    No geometry, proximity, flow direction or AI inference is performed.
    """

    supported_entity_types = frozenset(
        {
            "IFCRELAGGREGATES",
            "IFCRELCONTAINEDINSPATIALSTRUCTURE",
            "IFCRELDEFINESBYTYPE",
            "IFCRELASSIGNSTOGROUP",
            "IFCRELSERVICESBUILDINGS",
            "IFCRELASSOCIATESMATERIAL",
            "IFCRELCOVERSBLDGELEMENTS",
        }
    )

    def extract_path(self, path: Path, *, source_id: str | None = None) -> IfcRelationExtraction:
        data = path.read_bytes()
        return self.extract_text(
            data.decode("utf-8", errors="replace"),
            source_id=source_id or path.name,
            source_checksum_sha256=sha256(data).hexdigest(),
        )

    def extract_text(
        self,
        text: str,
        *,
        source_id: str,
        source_checksum_sha256: str | None = None,
    ) -> IfcRelationExtraction:
        checksum = source_checksum_sha256 or sha256(text.encode("utf-8")).hexdigest()
        relation_counts: Counter[str] = Counter()
        supported_counts: Counter[str] = Counter()
        unsupported_counts: Counter[str] = Counter()
        malformed: list[str] = []
        relations: list[IfcExplicitRelation] = []

        for entity_id, raw_entity_type, raw_args in _IFC_ROW.findall(text):
            entity_type = raw_entity_type.upper()
            if not entity_type.startswith("IFCREL"):
                continue
            relation_counts[entity_type] += 1
            if entity_type not in self.supported_entity_types:
                unsupported_counts[entity_type] += 1
                continue
            supported_counts[entity_type] += 1
            args = _split_top_level(raw_args)
            parsed = self._parse_supported(entity_id, entity_type, args)
            if parsed is None:
                malformed.append(entity_id)
                continue
            relations.extend(parsed)

        relations.sort(
            key=lambda item: (
                item.relation_entity_id,
                item.relation_type.value,
                item.source_ifc_id,
                item.target_ifc_id,
            )
        )
        return IfcRelationExtraction(
            source_id=source_id,
            source_checksum_sha256=checksum,
            relations=tuple(relations),
            relation_entity_counts=dict(sorted(relation_counts.items())),
            supported_relation_entity_counts=dict(sorted(supported_counts.items())),
            unsupported_relation_entity_counts=dict(sorted(unsupported_counts.items())),
            malformed_supported_entities=tuple(sorted(malformed)),
            metadata={
                "schema": "crow-ifc-explicit-relations-v0.2",
                "explicit_relations_extracted": len(relations),
                "inference_performed": False,
                "geometry_used": False,
                "unsupported_relationships_reported": True,
            },
        )

    @staticmethod
    def _parse_supported(
        entity_id: str,
        entity_type: str,
        args: list[str],
    ) -> list[IfcExplicitRelation] | None:
        if len(args) < 6:
            return None
        if entity_type == "IFCRELAGGREGATES":
            parent = _single_ref(args[4])
            children = _all_refs(args[5])
            if parent is None or not children:
                return None
            return [
                IfcExplicitRelation(
                    relation_entity_id=entity_id,
                    relation_entity_type=entity_type,
                    relation_type=CanonicalRelationType.CONTAINS,
                    source_ifc_id=parent,
                    target_ifc_id=child,
                    metadata={"ifc_semantics": "RelatingObject contains RelatedObjects"},
                )
                for child in children
            ]
        if entity_type == "IFCRELCONTAINEDINSPATIALSTRUCTURE":
            elements = _all_refs(args[4])
            structure = _single_ref(args[5])
            if structure is None or not elements:
                return None
            return [
                IfcExplicitRelation(
                    relation_entity_id=entity_id,
                    relation_entity_type=entity_type,
                    relation_type=CanonicalRelationType.LOCATED_IN,
                    source_ifc_id=element,
                    target_ifc_id=structure,
                    metadata={"ifc_semantics": "RelatedElements located in RelatingStructure"},
                )
                for element in elements
            ]
        if entity_type == "IFCRELDEFINESBYTYPE":
            objects = _all_refs(args[4])
            relating_type = _single_ref(args[5])
            if relating_type is None or not objects:
                return None
            return [
                IfcExplicitRelation(
                    relation_entity_id=entity_id,
                    relation_entity_type=entity_type,
                    relation_type=CanonicalRelationType.TYPED_BY,
                    source_ifc_id=object_id,
                    target_ifc_id=relating_type,
                    metadata={"ifc_semantics": "RelatedObjects typed by RelatingType"},
                )
                for object_id in objects
            ]
        if entity_type == "IFCRELASSIGNSTOGROUP":
            objects = _all_refs(args[4])
            group = _single_ref(args[6]) if len(args) > 6 else None
            if group is None or not objects:
                return None
            return [
                IfcExplicitRelation(
                    relation_entity_id=entity_id,
                    relation_entity_type=entity_type,
                    relation_type=CanonicalRelationType.ASSIGNED_TO,
                    source_ifc_id=object_id,
                    target_ifc_id=group,
                    metadata={"ifc_semantics": "RelatedObjects assigned to RelatingGroup"},
                )
                for object_id in objects
            ]
        if entity_type == "IFCRELSERVICESBUILDINGS":
            system = _single_ref(args[4])
            buildings = _all_refs(args[5])
            if system is None or not buildings:
                return None
            return [
                IfcExplicitRelation(
                    relation_entity_id=entity_id,
                    relation_entity_type=entity_type,
                    relation_type=CanonicalRelationType.SERVES,
                    source_ifc_id=system,
                    target_ifc_id=building,
                    metadata={"ifc_semantics": "RelatingSystem serves RelatedBuildings"},
                )
                for building in buildings
            ]
        if entity_type == "IFCRELASSOCIATESMATERIAL":
            objects = _all_refs(args[4])
            material = _single_ref(args[5])
            if material is None or not objects:
                return None
            return [
                IfcExplicitRelation(
                    relation_entity_id=entity_id,
                    relation_entity_type=entity_type,
                    relation_type=CanonicalRelationType.ASSOCIATED_WITH_MATERIAL,
                    source_ifc_id=object_id,
                    target_ifc_id=material,
                    metadata={"ifc_semantics": "RelatedObjects associated with RelatingMaterial"},
                )
                for object_id in objects
            ]
        if entity_type == "IFCRELCOVERSBLDGELEMENTS":
            element = _single_ref(args[4])
            coverings = _all_refs(args[5])
            if element is None or not coverings:
                return None
            return [
                IfcExplicitRelation(
                    relation_entity_id=entity_id,
                    relation_entity_type=entity_type,
                    relation_type=CanonicalRelationType.COVERS,
                    source_ifc_id=element,
                    target_ifc_id=covering,
                    metadata={
                        "ifc_semantics": "RelatingBuildingElement covered by RelatedCoverings"
                    },
                )
                for covering in coverings
            ]
        return None

    def map_to_assertions(
        self,
        extraction: IfcRelationExtraction,
        ifc_to_canonical_id: dict[str, str],
    ) -> IfcRelationMappingResult:
        assertions: list[ExplicitRelationAssertion] = []
        unmapped: set[str] = set()
        skipped: list[str] = []

        for relation in extraction.relations:
            source_id = ifc_to_canonical_id.get(relation.source_ifc_id)
            target_id = ifc_to_canonical_id.get(relation.target_ifc_id)
            if source_id is None or target_id is None:
                if source_id is None:
                    unmapped.add(relation.source_ifc_id)
                if target_id is None:
                    unmapped.add(relation.target_ifc_id)
                skipped.append(relation.relation_entity_id)
                continue
            assertions.append(
                ExplicitRelationAssertion(
                    source_id=source_id,
                    relation_type=relation.relation_type,
                    target_id=target_id,
                    confidence=1.0,
                    assertion_id=f"ifc:{extraction.source_checksum_sha256}:{relation.relation_entity_id}:"
                    f"{relation.source_ifc_id}:{relation.target_ifc_id}",
                    evidence=CanonicalEvidence(
                        source_id=extraction.source_id,
                        source_kind="ifc_explicit_relation",
                        locator=relation.relation_entity_id,
                        confidence=1.0,
                        metadata={
                            "source_checksum_sha256": extraction.source_checksum_sha256,
                            "ifc_relation_entity_type": relation.relation_entity_type,
                            "source_ifc_id": relation.source_ifc_id,
                            "target_ifc_id": relation.target_ifc_id,
                        },
                    ),
                    metadata={
                        **relation.metadata,
                        "ifc_relation_entity_id": relation.relation_entity_id,
                        "ifc_relation_entity_type": relation.relation_entity_type,
                        "derivation_source": "explicit_ifc_relationship",
                    },
                )
            )

        assertions.sort(key=lambda item: item.assertion_id or "")
        return IfcRelationMappingResult(
            assertions=tuple(assertions),
            unmapped_ifc_ids=tuple(sorted(unmapped)),
            skipped_relation_entity_ids=tuple(sorted(set(skipped))),
            metadata={
                "schema": "crow-ifc-relation-mapping-v0.2",
                "assertion_count": len(assertions),
                "skipped_relation_count": len(set(skipped)),
                "inference_performed": False,
                "automatic_object_creation_performed": False,
            },
        )


def _split_top_level(raw: str) -> list[str]:
    result: list[str] = []
    start = 0
    depth = 0
    quoted = False
    index = 0
    while index < len(raw):
        char = raw[index]
        if char == "'":
            if quoted and index + 1 < len(raw) and raw[index + 1] == "'":
                index += 2
                continue
            quoted = not quoted
        elif not quoted:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                result.append(raw[start:index].strip())
                start = index + 1
        index += 1
    result.append(raw[start:].strip())
    return result


def _all_refs(value: str) -> list[str]:
    return _IFC_REF.findall(value)


def _single_ref(value: str) -> str | None:
    refs = _all_refs(value)
    return refs[0] if len(refs) == 1 else None
