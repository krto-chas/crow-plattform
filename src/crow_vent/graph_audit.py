from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from crow_graph_rules import (
    GraphRuleContext,
    GraphRuleEngine,
    GraphRuleFinding,
    GraphRuleMetadata,
)

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


def _evidence_ids(item: dict[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(str(value) for value in item.get("evidence_ids", ()) if value))


def _finding(
    metadata: GraphRuleMetadata,
    *,
    category: str,
    status: str,
    message: str,
    object_ids: tuple[str, ...] = (),
    relation_ids: tuple[str, ...] = (),
    evidence_ids: tuple[str, ...] = (),
    finding_metadata: dict[str, Any] | None = None,
) -> GraphRuleFinding:
    digest = sha256(
        "|".join((metadata.rule_id, *object_ids, *relation_ids)).encode("utf-8")
    ).hexdigest()[:20]
    return GraphRuleFinding(
        finding_id=f"vent:finding:{digest}",
        rule_id=metadata.rule_id,
        rule_version=metadata.version,
        category=category,
        severity=metadata.severity,
        status=status,
        message=message,
        object_ids=object_ids,
        relation_ids=relation_ids,
        evidence_ids=evidence_ids,
        metadata=finding_metadata or {},
    )


class _DanglingRelationRule:
    metadata = GraphRuleMetadata(
        rule_id="VENT-DQ-001",
        version="0.1.0",
        title="Relationer måste referera till befintliga objekt",
        description="Identifierar relationer med saknad källa eller mål.",
        discipline="VENT",
        severity="error",
        evidence_required=False,
        tags=("data_quality", "relation_integrity"),
    )

    def evaluate(self, context: GraphRuleContext) -> tuple[GraphRuleFinding, ...]:
        findings: list[GraphRuleFinding] = []
        for relation in context.relations:
            missing = tuple(
                object_id
                for object_id in (str(relation["source_id"]), str(relation["target_id"]))
                if object_id not in context.objects
            )
            if missing:
                relation_id = str(relation["id"])
                findings.append(
                    _finding(
                        self.metadata,
                        category="data_quality",
                        status="verified",
                        message="Relationen refererar till ett objekt som saknas i grafen.",
                        object_ids=missing,
                        relation_ids=(relation_id,),
                        evidence_ids=_evidence_ids(relation),
                        finding_metadata={"missing_object_ids": list(missing)},
                    )
                )
        return tuple(findings)


class _RelationEvidenceRule:
    metadata = GraphRuleMetadata(
        rule_id="VENT-DQ-002",
        version="0.1.0",
        title="Explicita ventilationsrelationer måste bära evidens",
        description="Kontrollerar evidensreferenser på flödes- och systemrelationer.",
        discipline="VENT",
        severity="warning",
        evidence_required=True,
        tags=("data_quality", "evidence_integrity"),
    )

    def evaluate(self, context: GraphRuleContext) -> tuple[GraphRuleFinding, ...]:
        findings: list[GraphRuleFinding] = []
        for relation in context.relations:
            relation_type = str(relation.get("relation_type", ""))
            if relation_type not in FLOW_RELATIONS | SYSTEM_RELATIONS or _evidence_ids(relation):
                continue
            findings.append(
                _finding(
                    self.metadata,
                    category="data_quality",
                    status="verified",
                    message="En explicit ventilationsrelation saknar evidensreferens.",
                    object_ids=(str(relation["source_id"]), str(relation["target_id"])),
                    relation_ids=(str(relation["id"]),),
                    finding_metadata={"relation_type": relation_type},
                )
            )
        return tuple(findings)


class _TerminalFeedEvidenceRule:
    metadata = GraphRuleMetadata(
        rule_id="VENT-EVID-001",
        version="0.1.0",
        title="Luftdon bör ha explicit försörjningsrelation",
        description="Rapporterar evidensgap utan att fastställa projekteringsfel.",
        discipline="VENT",
        severity="info",
        evidence_required=True,
        tags=("evidence_gap", "flow"),
    )

    def evaluate(self, context: GraphRuleContext) -> tuple[GraphRuleFinding, ...]:
        fed_targets = {
            str(relation["target_id"])
            for relation in context.relations
            if relation.get("relation_type") == "feeds"
        }
        findings = []
        for object_id, obj in context.objects.items():
            if obj.get("object_type") != "air_terminal" or object_id in fed_targets:
                continue
            findings.append(
                _finding(
                    self.metadata,
                    category="evidence_gap",
                    status="review_required",
                    message=(
                        "Luftdonet saknar en explicit feeds-relation i tillgänglig evidens. "
                        "Detta är inte ett fastställt projekteringsfel."
                    ),
                    object_ids=(object_id,),
                    evidence_ids=_evidence_ids(obj),
                    finding_metadata={
                        "expected_relation": "feeds",
                        "design_defect_asserted": False,
                    },
                )
            )
        return tuple(findings)


class _SystemMembershipEvidenceRule:
    metadata = GraphRuleMetadata(
        rule_id="VENT-EVID-002",
        version="0.1.0",
        title="Ventilationsobjekt bör ha explicit systemtillhörighet",
        description="Rapporterar saknad evidens för systemtillhörighet utan inferens.",
        discipline="VENT",
        severity="info",
        evidence_required=True,
        tags=("evidence_gap", "system_integrity"),
    )

    def evaluate(self, context: GraphRuleContext) -> tuple[GraphRuleFinding, ...]:
        assigned = {
            str(relation["source_id"])
            for relation in context.relations
            if relation.get("relation_type") == "belongs_to"
            and str(relation.get("target_id", "")) in context.objects
            and context.objects[str(relation["target_id"])].get("object_type")
            == "ventilation_system"
        }
        findings = []
        for object_id, obj in context.objects.items():
            if obj.get("object_type") not in SYSTEM_SCOPED_TYPES or object_id in assigned:
                continue
            findings.append(
                _finding(
                    self.metadata,
                    category="evidence_gap",
                    status="review_required",
                    message=(
                        "Objektet saknar explicit systemtillhörighet i tillgänglig evidens. "
                        "Ingen systemtillhörighet har infererats."
                    ),
                    object_ids=(object_id,),
                    evidence_ids=_evidence_ids(obj),
                    finding_metadata={
                        "expected_relation": "belongs_to",
                        "inference_performed": False,
                        "design_defect_asserted": False,
                    },
                )
            )
        return tuple(findings)


VENT_GRAPH_RULES = (
    _DanglingRelationRule(),
    _RelationEvidenceRule(),
    _TerminalFeedEvidenceRule(),
    _SystemMembershipEvidenceRule(),
)


class VentGraphAudit:
    """Ventilationsprofil ovanpå den generella Building Graph-regelmotorn."""

    RULE_VERSION = "0.1.0"

    def audit(self, graph: dict[str, Any]) -> VentGraphAuditResult:
        evaluation = GraphRuleEngine().evaluate(graph, VENT_GRAPH_RULES)
        findings = tuple(
            VentGraphFinding(
                finding_id=item.finding_id,
                rule_id=item.rule_id,
                rule_version=item.rule_version,
                category=item.category,
                severity=item.severity,
                status=item.status,
                message=item.message,
                object_ids=item.object_ids,
                relation_ids=item.relation_ids,
                evidence_ids=item.evidence_ids,
                metadata=item.metadata,
            )
            for item in evaluation.findings
        )
        summary = {
            "total": evaluation.summary.get("total", 0),
            "evidence_gap": evaluation.summary.get("evidence_gap", 0),
            "data_quality": evaluation.summary.get("data_quality", 0),
            "proven_design_defect": evaluation.summary.get("proven_design_defect", 0),
        }
        return VentGraphAuditResult(
            findings=findings,
            summary=summary,
            metadata={
                **evaluation.metadata,
                "rule_version": self.RULE_VERSION,
                "missing_information_treated_as_defect": False,
            },
        )
