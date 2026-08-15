from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from crow_evidence_index import EvidenceIndexBuilder, EvidenceIndexResult
from crow_graph_rules import (
    GraphRuleContext,
    GraphRuleEngine,
    GraphRuleFinding,
    GraphRuleMetadata,
)


@dataclass(frozen=True)
class EvidenceAuditFinding:
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
class EvidenceAuditResult:
    findings: tuple[EvidenceAuditFinding, ...]
    summary: dict[str, int]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "findings": [
                {
                    "finding_id": item.finding_id,
                    "rule_id": item.rule_id,
                    "rule_version": item.rule_version,
                    "category": item.category,
                    "severity": item.severity,
                    "status": item.status,
                    "message": item.message,
                    "object_ids": list(item.object_ids),
                    "relation_ids": list(item.relation_ids),
                    "evidence_ids": list(item.evidence_ids),
                    "metadata": item.metadata,
                }
                for item in self.findings
            ],
            "summary": self.summary,
            "metadata": self.metadata,
        }


def _finding_id(rule_id: str, *parts: str) -> str:
    digest = sha256("|".join((rule_id, *parts)).encode("utf-8")).hexdigest()[:20]
    return f"evidence:finding:{digest}"


class _EvidenceIndexRule:
    metadata: GraphRuleMetadata

    def __init__(self, index: EvidenceIndexResult) -> None:
        self.index = index


class MissingEvidenceReferenceRule(_EvidenceIndexRule):
    metadata = GraphRuleMetadata(
        rule_id="EVID-DQ-001",
        version="0.1.0",
        title="Evidensreferenser måste peka på befintlig evidens",
        description="Identifierar evidence_ids som saknar motsvarande evidenspost.",
        discipline="GENERAL",
        severity="error",
        evidence_required=False,
        tags=("data_quality", "evidence_integrity"),
    )

    def evaluate(self, context: GraphRuleContext) -> tuple[GraphRuleFinding, ...]:
        del context
        return tuple(
            GraphRuleFinding(
                finding_id=_finding_id(self.metadata.rule_id, evidence_id),
                rule_id=self.metadata.rule_id,
                rule_version=self.metadata.version,
                category="data_quality",
                severity=self.metadata.severity,
                status="verified",
                message="En grafentitet refererar till evidens som saknas i grafen.",
                evidence_ids=(evidence_id,),
                metadata={"missing_evidence_id": evidence_id},
            )
            for evidence_id in self.index.missing_evidence_ids
        )


class DuplicateEvidenceIdRule(_EvidenceIndexRule):
    metadata = GraphRuleMetadata(
        rule_id="EVID-DQ-002",
        version="0.1.0",
        title="Evidens-ID:n måste vara unika",
        description="Identifierar dubblerade evidens-ID:n i samma graf-snapshot.",
        discipline="GENERAL",
        severity="error",
        evidence_required=False,
        tags=("data_quality", "identity"),
    )

    def evaluate(self, context: GraphRuleContext) -> tuple[GraphRuleFinding, ...]:
        del context
        return tuple(
            GraphRuleFinding(
                finding_id=_finding_id(self.metadata.rule_id, evidence_id),
                rule_id=self.metadata.rule_id,
                rule_version=self.metadata.version,
                category="data_quality",
                severity=self.metadata.severity,
                status="verified",
                message="Samma evidens-ID förekommer mer än en gång i grafen.",
                evidence_ids=(evidence_id,),
                metadata={"duplicate_evidence_id": evidence_id},
            )
            for evidence_id in self.index.duplicate_evidence_ids
        )


class SourceChecksumConflictRule(_EvidenceIndexRule):
    metadata = GraphRuleMetadata(
        rule_id="EVID-DQ-003",
        version="0.1.0",
        title="Samma källa bör inte ha motstridiga checksummor",
        description="Identifierar source_id med fler än en explicit checksumma.",
        discipline="GENERAL",
        severity="warning",
        evidence_required=False,
        tags=("data_quality", "provenance", "checksum"),
    )

    def evaluate(self, context: GraphRuleContext) -> tuple[GraphRuleFinding, ...]:
        del context
        return tuple(
            GraphRuleFinding(
                finding_id=_finding_id(self.metadata.rule_id, conflict.source_id),
                rule_id=self.metadata.rule_id,
                rule_version=self.metadata.version,
                category="data_quality",
                severity=self.metadata.severity,
                status="review_required",
                message="Samma källidentifierare förekommer med motstridiga checksummor.",
                evidence_ids=conflict.evidence_ids,
                metadata={
                    "source_id": conflict.source_id,
                    "checksums": list(conflict.checksums),
                    "automatic_checksum_selection_performed": False,
                },
            )
            for conflict in self.index.source_checksum_conflicts
        )


class UnreferencedEvidenceRule(_EvidenceIndexRule):
    metadata = GraphRuleMetadata(
        rule_id="EVID-EVID-001",
        version="0.1.0",
        title="Oanvänd evidens bör granskas",
        description=(
            "Rapporterar evidensposter som inte refereras av objekt, relation eller egenskap."
        ),
        discipline="GENERAL",
        severity="info",
        evidence_required=True,
        tags=("evidence_gap", "orphan_evidence"),
    )

    def evaluate(self, context: GraphRuleContext) -> tuple[GraphRuleFinding, ...]:
        del context
        return tuple(
            GraphRuleFinding(
                finding_id=_finding_id(self.metadata.rule_id, evidence_id),
                rule_id=self.metadata.rule_id,
                rule_version=self.metadata.version,
                category="evidence_gap",
                severity=self.metadata.severity,
                status="review_required",
                message=(
                    "Evidensposten används inte av någon grafentitet. "
                    "Detta är inte i sig ett tekniskt fel."
                ),
                evidence_ids=(evidence_id,),
                metadata={
                    "unreferenced_evidence_id": evidence_id,
                    "technical_defect_asserted": False,
                },
            )
            for evidence_id in self.index.unreferenced_evidence_ids
        )


class EvidenceIntegrityAudit:
    """Generell evidensgranskning ovanpå EvidenceIndex och GraphRuleEngine."""

    RULESET_VERSION = "0.1.0"

    def audit(self, graph: dict[str, Any]) -> EvidenceAuditResult:
        index = EvidenceIndexBuilder().build(graph)
        rules = (
            MissingEvidenceReferenceRule(index),
            DuplicateEvidenceIdRule(index),
            SourceChecksumConflictRule(index),
            UnreferencedEvidenceRule(index),
        )
        evaluation = GraphRuleEngine().evaluate(graph, rules)
        findings = tuple(
            EvidenceAuditFinding(
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
        return EvidenceAuditResult(
            findings=findings,
            summary={
                "total": evaluation.summary.get("total", 0),
                "data_quality": evaluation.summary.get("data_quality", 0),
                "evidence_gap": evaluation.summary.get("evidence_gap", 0),
            },
            metadata={
                **evaluation.metadata,
                "ruleset_version": self.RULESET_VERSION,
                "index_schema": index.schema_version,
                "graph_mutated": False,
                "evidence_mutated": False,
                "automatic_repair_performed": False,
            },
        )
