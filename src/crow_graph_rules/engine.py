from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

VALID_SEVERITIES = frozenset({"info", "warning", "error", "critical"})
VALID_DISCIPLINES = frozenset({"GENERAL", "VENT", "VS", "EL", "SPRINKLER", "BRAND", "BYGG"})


@dataclass(frozen=True)
class GraphRuleMetadata:
    rule_id: str
    version: str
    title: str
    description: str
    discipline: str
    severity: str
    evidence_required: bool
    supports_auto_inference: bool = False
    enabled: bool = True
    tags: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.rule_id.strip():
            raise ValueError("rule_id får inte vara tomt")
        if not self.version.strip():
            raise ValueError("regelversion får inte vara tom")
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(f"Ogiltig severity: {self.severity}")
        if self.discipline not in VALID_DISCIPLINES:
            raise ValueError(f"Ogiltig disciplin: {self.discipline}")


@dataclass(frozen=True)
class GraphRuleFinding:
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
class GraphRuleContext:
    graph: dict[str, Any]
    objects: dict[str, dict[str, Any]]
    relations: tuple[dict[str, Any], ...]
    properties: tuple[dict[str, Any], ...]
    evidence: dict[str, dict[str, Any]]

    @classmethod
    def from_graph(cls, graph: dict[str, Any]) -> GraphRuleContext:
        return cls(
            graph=graph,
            objects={str(item["id"]): item for item in graph.get("objects", [])},
            relations=tuple(graph.get("relations", [])),
            properties=tuple(graph.get("properties", [])),
            evidence={str(item["id"]): item for item in graph.get("evidence", [])},
        )


class GraphRule(Protocol):
    metadata: GraphRuleMetadata

    def evaluate(self, context: GraphRuleContext) -> tuple[GraphRuleFinding, ...]: ...


@dataclass(frozen=True)
class GraphRuleEvaluation:
    findings: tuple[GraphRuleFinding, ...]
    summary: dict[str, int]
    metadata: dict[str, Any]


class GraphRuleEngine:
    """Deterministisk regelmotor för Building Graph-snapshots."""

    def evaluate(
        self,
        graph: dict[str, Any],
        rules: tuple[GraphRule, ...],
    ) -> GraphRuleEvaluation:
        context = GraphRuleContext.from_graph(graph)
        findings: list[GraphRuleFinding] = []
        evaluated: list[GraphRuleMetadata] = []

        seen_ids: set[str] = set()
        for rule in rules:
            rule.metadata.validate()
            if rule.metadata.rule_id in seen_ids:
                raise ValueError(f"Dubblerat rule_id: {rule.metadata.rule_id}")
            seen_ids.add(rule.metadata.rule_id)
            if not rule.metadata.enabled:
                continue
            evaluated.append(rule.metadata)
            findings.extend(rule.evaluate(context))

        findings.sort(key=lambda item: (item.rule_id, item.object_ids, item.relation_ids))
        summary: dict[str, int] = {"total": len(findings)}
        for finding in findings:
            summary[finding.category] = summary.get(finding.category, 0) + 1

        return GraphRuleEvaluation(
            findings=tuple(findings),
            summary=summary,
            metadata={
                "engine_schema": "crow-graph-rule-evaluation-v0.1",
                "rules_evaluated": len(evaluated),
                "rule_ids": [item.rule_id for item in evaluated],
                "inference_performed": False,
                "automatic_correction_performed": False,
            },
        )
