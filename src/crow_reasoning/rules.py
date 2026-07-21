from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any

VALID_SEVERITIES = {"info", "warning", "error", "critical"}
VALID_OPERATORS = {"equals", "not_equals", "exists", "missing", "in"}


@dataclass(frozen=True)
class RuleSelector:
    object_type: str | None = None
    discipline: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuleRequirement:
    kind: str
    relation_type: str | None = None
    direction: str = "outgoing"
    target_object_type: str | None = None
    property_name: str | None = None
    operator: str = "exists"
    value: Any = None
    evidence_required: bool = False


@dataclass(frozen=True)
class RuleDefinition:
    id: str
    version: str
    title: str
    description: str
    selector: RuleSelector
    requirements: tuple[RuleRequirement, ...]
    severity: str = "warning"
    confidence: float = 1.0
    recommendation: str | None = None
    tags: tuple[str, ...] = ()
    enabled: bool = True

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RuleDefinition:
        selector = RuleSelector(**payload.get("selector", {}))
        requirements = tuple(RuleRequirement(**item) for item in payload.get("requirements", []))
        rule = cls(
            id=str(payload["id"]),
            version=str(payload.get("version", "1.0.0")),
            title=str(payload.get("title", payload["id"])),
            description=str(payload.get("description", "")),
            selector=selector,
            requirements=requirements,
            severity=str(payload.get("severity", "warning")),
            confidence=float(payload.get("confidence", 1.0)),
            recommendation=payload.get("recommendation"),
            tags=tuple(payload.get("tags", ())),
            enabled=bool(payload.get("enabled", True)),
        )
        rule.validate()
        return rule

    def validate(self) -> None:
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(f"Ogiltig severity: {self.severity}")
        if not 0 <= self.confidence <= 1:
            raise ValueError("Rule confidence måste ligga mellan 0 och 1")
        if not self.requirements:
            raise ValueError("En regel måste innehålla minst ett krav")
        for requirement in self.requirements:
            if requirement.kind not in {"relation", "property", "evidence"}:
                raise ValueError(f"Okänd kravtyp: {requirement.kind}")
            if requirement.operator not in VALID_OPERATORS:
                raise ValueError(f"Okänd operator: {requirement.operator}")
            if requirement.direction not in {"outgoing", "incoming", "both"}:
                raise ValueError(f"Ogiltig riktning: {requirement.direction}")


@dataclass(frozen=True)
class RuleFinding:
    id: str
    rule_id: str
    rule_version: str
    object_id: str
    severity: str
    confidence: float
    title: str
    message: str
    recommendation: str | None
    evidence_ids: tuple[str, ...] = ()
    related_object_ids: tuple[str, ...] = ()
    failed_requirements: tuple[dict[str, Any], ...] = ()


class RuleEngine:
    """Datadriven och deterministisk regelutvärdering över en Building Graph-snapshot."""

    def __init__(self, graph: dict[str, Any]):
        self.graph = graph
        self.objects = {item["id"]: item for item in graph.get("objects", [])}
        self.relations = list(graph.get("relations", []))
        self.properties = list(graph.get("properties", []))
        self.evidence = {item["id"]: item for item in graph.get("evidence", [])}

    def evaluate(self, rules: Iterable[RuleDefinition | dict[str, Any]]) -> dict[str, Any]:
        normalized = [
            r if isinstance(r, RuleDefinition) else RuleDefinition.from_dict(r) for r in rules
        ]
        findings: list[RuleFinding] = []
        evaluated_objects = 0
        for rule in normalized:
            if not rule.enabled:
                continue
            candidates = [
                obj for obj in self.objects.values() if self._matches_selector(obj, rule.selector)
            ]
            evaluated_objects += len(candidates)
            for obj in candidates:
                failed: list[dict[str, Any]] = []
                related_ids: set[str] = set()
                evidence_ids: set[str] = set(obj.get("evidence_ids") or ())
                for requirement in rule.requirements:
                    ok, details = self._evaluate_requirement(obj, requirement)
                    related_ids.update(details.get("related_object_ids", ()))
                    evidence_ids.update(details.get("evidence_ids", ()))
                    if not ok:
                        failed.append({"requirement": asdict(requirement), "details": details})
                if failed:
                    findings.append(self._finding(rule, obj, failed, related_ids, evidence_ids))
        severity_counts = {severity: 0 for severity in ("critical", "error", "warning", "info")}
        for finding in findings:
            severity_counts[finding.severity] += 1
        return {
            "schema": "crow-reasoning-rule-evaluation-v0.1",
            "rules_evaluated": len([r for r in normalized if r.enabled]),
            "objects_evaluated": evaluated_objects,
            "findings": [asdict(item) for item in findings],
            "summary": {"finding_count": len(findings), "by_severity": severity_counts},
        }

    def _matches_selector(self, obj: dict[str, Any], selector: RuleSelector) -> bool:
        if selector.object_type and obj.get("object_type") != selector.object_type:
            return False
        if selector.discipline and obj.get("discipline") != selector.discipline:
            return False
        metadata = obj.get("metadata") or {}
        return all(metadata.get(key) == value for key, value in selector.metadata.items())

    def _evaluate_requirement(
        self, obj: dict[str, Any], requirement: RuleRequirement
    ) -> tuple[bool, dict[str, Any]]:
        if requirement.kind == "relation":
            return self._relation_requirement(obj, requirement)
        if requirement.kind == "property":
            return self._property_requirement(obj, requirement)
        evidence_ids = tuple(obj.get("evidence_ids") or ())
        present = bool(evidence_ids)
        return self._operator(present, requirement.operator, requirement.value), {
            "evidence_ids": evidence_ids
        }

    def _relation_requirement(
        self, obj: dict[str, Any], requirement: RuleRequirement
    ) -> tuple[bool, dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for relation in self.relations:
            outgoing = relation.get("source_id") == obj["id"]
            incoming = relation.get("target_id") == obj["id"]
            if requirement.direction == "outgoing" and not outgoing:
                continue
            if requirement.direction == "incoming" and not incoming:
                continue
            if requirement.direction == "both" and not (outgoing or incoming):
                continue
            if (
                requirement.relation_type
                and relation.get("relation_type") != requirement.relation_type
            ):
                continue
            target_id = relation["target_id"] if outgoing else relation["source_id"]
            target = self.objects.get(target_id, {})
            if (
                requirement.target_object_type
                and target.get("object_type") != requirement.target_object_type
            ):
                continue
            if requirement.evidence_required and not relation.get("evidence_ids"):
                continue
            matches.append(relation)
        present = bool(matches)
        related = tuple(
            sorted(
                {r["target_id"] if r["source_id"] == obj["id"] else r["source_id"] for r in matches}
            )
        )
        evidence = tuple(sorted({eid for r in matches for eid in r.get("evidence_ids", ())}))
        return self._operator(present, requirement.operator, requirement.value), {
            "matching_relation_ids": tuple(r["id"] for r in matches),
            "related_object_ids": related,
            "evidence_ids": evidence,
        }

    def _property_requirement(
        self, obj: dict[str, Any], requirement: RuleRequirement
    ) -> tuple[bool, dict[str, Any]]:
        matches = [
            p
            for p in self.properties
            if p.get("owner_id") == obj["id"] and p.get("name") == requirement.property_name
        ]
        if requirement.evidence_required:
            matches = [p for p in matches if p.get("evidence_ids")]
        values = [p.get("value") for p in matches]
        if requirement.operator in {"exists", "missing"}:
            result = self._operator(bool(matches), requirement.operator, requirement.value)
        elif requirement.operator == "equals":
            result = any(value == requirement.value for value in values)
        elif requirement.operator == "not_equals":
            result = bool(matches) and all(value != requirement.value for value in values)
        else:
            expected = (
                requirement.value
                if isinstance(requirement.value, (list, tuple, set))
                else [requirement.value]
            )
            result = any(value in expected for value in values)
        evidence = tuple(sorted({eid for p in matches for eid in p.get("evidence_ids", ())}))
        return result, {
            "matching_property_ids": tuple(p["id"] for p in matches),
            "values": values,
            "evidence_ids": evidence,
        }

    @staticmethod
    def _operator(present: bool, operator: str, value: Any) -> bool:
        if operator == "exists":
            return present
        if operator == "missing":
            return not present
        if operator == "equals":
            return present == bool(value)
        if operator == "not_equals":
            return present != bool(value)
        return present in value if isinstance(value, (list, tuple, set)) else present == value

    @staticmethod
    def _finding(
        rule: RuleDefinition,
        obj: dict[str, Any],
        failed: list[dict[str, Any]],
        related_ids: set[str],
        evidence_ids: set[str],
    ) -> RuleFinding:
        digest = sha256(f"{rule.id}|{rule.version}|{obj['id']}".encode()).hexdigest()[:20]
        message = rule.description or f"Objektet uppfyller inte regeln {rule.id}"
        return RuleFinding(
            id=f"finding:{digest}",
            rule_id=rule.id,
            rule_version=rule.version,
            object_id=obj["id"],
            severity=rule.severity,
            confidence=rule.confidence,
            title=rule.title,
            message=message,
            recommendation=rule.recommendation,
            evidence_ids=tuple(sorted(evidence_ids)),
            related_object_ids=tuple(sorted(related_ids)),
            failed_requirements=tuple(failed),
        )
