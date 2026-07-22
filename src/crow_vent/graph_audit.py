from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

FLOW_RELATIONS = frozenset({"feeds", "returns_from", "passes_through"})
SYSTEM_RELATIONS = frozenset({"belongs_to"})
SYSTEM_SCOPED_TYPES = frozenset(
    {
        "air_handling_unit",
        "fan",
        "duct",
        "damper",
        "silencer",
        "air_terminal",
        "heat_exchanger",
        "air_treatment_component",
        "accessory",
    }
)


@dataclass(frozen=True)
class VentGraphFinding:
    finding_id: str
    rule_id: str
    rule_version: str
    category: str
    severity: str
    status: str
    message: str
    object_ids: tuple[str, ...] = ()
    relation_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VentGraphAuditResult:
    findings: tuple[VentGraphFinding, ...]
    summary: dict[str, int]
    metadata: dict[str, Any] = field(default_factory=dict)


class VentGraphAudit:
    """Evidence-first checks for ventilation graph completeness and integrity.

    Missing relations are reported as evidence gaps, never as proven design defects.
    The audit performs no geometric or AI inference.
    """

    RULE_VERSION = "0.1.0"

    def audit(self, graph: dict[str, Any]) -> VentGraphAuditResult:
        objects = {str(item["id"]): item for item in graph.get("objects", [])}
        relations = list(graph.get("relations", []))
        findings: list[VentGraphFinding] = []

        findings.extend(self._dangling_relations(objects, relations))
        findings.extend(self._relations_without_evidence(relations))
        findings.extend(self._terminals_without_explicit_feed(objects, relations))
        findings.extend(self._objects_without_explicit_system(objects, relations))

        findings.sort(key=lambda item: (item.rule_id, item.object_ids, item.relation_ids))
        summary: dict[str, int] = {
            "total": len(findings),
            "evidence_gap": 0,
            "data_quality": 0,
            "proven_design_defect": 0,
        }
        for finding in findings:
            summary[finding.category] = summary.get(finding.category, 0) + 1

        return VentGraphAuditResult(
            findings=tuple(findings),
            summary=summary,
            metadata={
                "rule_version": self.RULE_VERSION,
                "inference_performed": False,
                "missing_information_treated_as_defect": False,
            },
        )

    def _dangling_relations(
        self,
        objects: dict[str, dict[str, Any]],
        relations: list[dict[str, Any]],
    ) -> list[VentGraphFinding]:
        findings: list[VentGraphFinding] = []
        for relation in relations:
            missing = tuple(
                object_id
                for object_id in (str(relation["source_id"]), str(relation["target_id"]))
                if object_id not in objects
            )
            if not missing:
                continue
            relation_id = str(relation["id"])
            findings.append(
                self._finding(
                    rule_id="VENT-DQ-001",
                    category="data_quality",
                    severity="error",
                    status="verified",
                    message="Relationen refererar till ett objekt som saknas i grafen.",
                    object_ids=missing,
                    relation_ids=(relation_id,),
                    evidence_ids=self._evidence_ids(relation),
                    metadata={"missing_object_ids": list(missing)},
                )
            )
        return findings

    def _relations_without_evidence(
        self, relations: list[dict[str, Any]]
    ) -> list[VentGraphFinding]:
        findings: list[VentGraphFinding] = []
        for relation in relations:
            relation_type = str(relation.get("relation_type", ""))
            if relation_type not in FLOW_RELATIONS | SYSTEM_RELATIONS:
                continue
            if self._evidence_ids(relation):
                continue
            relation_id = str(relation["id"])
            findings.append(
                self._finding(
                    rule_id="VENT-DQ-002",
                    category="data_quality",
                    severity="warning",
                    status="verified",
                    message="En explicit ventilationsrelation saknar evidensreferens.",
                    object_ids=(str(relation["source_id"]), str(relation["target_id"])),
                    relation_ids=(relation_id,),
                    metadata={"relation_type": relation_type},
                )
            )
        return findings

    def _terminals_without_explicit_feed(
        self,
        objects: dict[str, dict[str, Any]],
        relations: list[dict[str, Any]],
    ) -> list[VentGraphFinding]:
        fed_targets = {
            str(relation["target_id"])
            for relation in relations
            if relation.get("relation_type") == "feeds"
        }
        findings: list[VentGraphFinding] = []
        for object_id, obj in objects.items():
            if obj.get("object_type") != "air_terminal" or object_id in fed_targets:
                continue
            findings.append(
                self._finding(
                    rule_id="VENT-EVID-001",
                    category="evidence_gap",
                    severity="info",
                    status="review_required",
                    message=(
                        "Luftdonet saknar en explicit feeds-relation i tillgänglig evidens. "
                        "Detta är inte ett fastställt projekteringsfel."
                    ),
                    object_ids=(object_id,),
                    evidence_ids=self._evidence_ids(obj),
                    metadata={
                        "expected_relation": "feeds",
                        "design_defect_asserted": False,
                    },
                )
            )
        return findings

    def _objects_without_explicit_system(
        self,
        objects: dict[str, dict[str, Any]],
        relations: list[dict[str, Any]],
    ) -> list[VentGraphFinding]:
        assigned = {
            str(relation["source_id"])
            for relation in relations
            if relation.get("relation_type") == "belongs_to"
            and str(relation.get("target_id", "")) in objects
            and objects[str(relation["target_id"])].get("object_type") == "ventilation_system"
        }
        findings: list[VentGraphFinding] = []
        for object_id, obj in objects.items():
            if obj.get("object_type") not in SYSTEM_SCOPED_TYPES or object_id in assigned:
                continue
            findings.append(
                self._finding(
                    rule_id="VENT-EVID-002",
                    category="evidence_gap",
                    severity="info",
                    status="review_required",
                    message=(
                        "Objektet saknar explicit systemtillhörighet i tillgänglig evidens. "
                        "Ingen systemtillhörighet har infererats."
                    ),
                    object_ids=(object_id,),
                    evidence_ids=self._evidence_ids(obj),
                    metadata={
                        "expected_relation": "belongs_to",
                        "inference_performed": False,
                        "design_defect_asserted": False,
                    },
                )
            )
        return findings

    def _finding(
        self,
        *,
        rule_id: str,
        category: str,
        severity: str,
        status: str,
        message: str,
        object_ids: tuple[str, ...] = (),
        relation_ids: tuple[str, ...] = (),
        evidence_ids: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> VentGraphFinding:
        digest = sha256(
            "|".join((rule_id, *object_ids, *relation_ids)).encode("utf-8")
        ).hexdigest()[:20]
        return VentGraphFinding(
            finding_id=f"vent:finding:{digest}",
            rule_id=rule_id,
            rule_version=self.RULE_VERSION,
            category=category,
            severity=severity,
            status=status,
            message=message,
            object_ids=object_ids,
            relation_ids=relation_ids,
            evidence_ids=evidence_ids,
            metadata=metadata or {},
        )

    @staticmethod
    def _evidence_ids(entity: dict[str, Any]) -> tuple[str, ...]:
        return tuple(str(value) for value in entity.get("evidence_ids", []) if value)
