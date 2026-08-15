from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable
from hashlib import sha256
from typing import Any

from .models import DerivedRelation, ExplanationStep, InferenceConflict, InferenceRule

DEFAULT_RULES = (
    InferenceRule(
        id="crow.core.indirectly_served_by",
        premise_relation="served_by",
        conclusion_relation="indirectly_served_by",
        description="Härleder indirekt försörjning genom en served_by-kedja.",
    ),
    InferenceRule(
        id="crow.core.indirectly_located_in",
        premise_relation="located_in",
        conclusion_relation="indirectly_located_in",
        confidence_factor=0.99,
        description="Härleder överordnad placering genom en located_in-kedja.",
    ),
    InferenceRule(
        id="crow.core.indirectly_depends_on",
        premise_relation="depends_on",
        conclusion_relation="indirectly_depends_on",
        description="Härleder transitiva beroenden.",
    ),
)


class InferenceEngine:
    """Deterministisk och förklarbar inferens över en Building Graph-snapshot.

    Källgrafen är skrivskyddad. Explicita fakta, härledda fakta och konflikter hålls
    separerade, så att varje slutsats kan granskas och återskapas.
    """

    def __init__(self, graph: dict[str, Any]):
        self.graph = graph
        self.objects = {item["id"]: item for item in graph.get("objects", [])}
        self.relations = list(graph.get("relations", []))
        self.properties = list(graph.get("properties", []))

    def infer(
        self,
        rules: Iterable[InferenceRule] | None = None,
        *,
        max_iterations: int = 8,
    ) -> dict[str, Any]:
        selected = tuple(rule for rule in (rules or DEFAULT_RULES) if rule.enabled)
        explicit_keys = {
            (r["source_id"], r["relation_type"], r["target_id"]) for r in self.relations
        }
        facts = [self._normalize_relation(item, derived=False) for item in self.relations]
        derived_by_key: dict[tuple[str, str, str], DerivedRelation] = {}
        iterations = 0

        for iteration in range(1, max_iterations + 1):
            iterations = iteration
            created = 0
            for rule in selected:
                premise_facts = [
                    fact for fact in facts if fact["relation_type"] == rule.premise_relation
                ]
                for item in self._apply_transitive(rule, premise_facts, iteration=iteration):
                    key = (item.source_id, item.relation_type, item.target_id)
                    if key in explicit_keys:
                        continue
                    current = derived_by_key.get(key)
                    if current is not None and current.confidence >= item.confidence:
                        continue
                    derived_by_key[key] = item
                    if rule.chainable:
                        facts = [
                            fact
                            for fact in facts
                            if not (
                                fact["source_id"] == item.source_id
                                and fact["relation_type"] == item.relation_type
                                and fact["target_id"] == item.target_id
                            )
                        ]
                        facts.append(self._derived_fact(item))
                    created += 1
            if created == 0:
                break

        derived = sorted(
            derived_by_key.values(),
            key=lambda item: (item.rule_id, item.source_id, item.target_id),
        )
        conflicts = self.detect_property_conflicts()
        return {
            "schema": "crow-inference-v0.2",
            "graph_revision": self.graph.get("revision", 1),
            "rules": [rule.__dict__ for rule in selected],
            "derived_relations": [self._relation_payload(item) for item in derived],
            "conflicts": [conflict.__dict__ for conflict in conflicts],
            "summary": {
                "derived_relations": len(derived),
                "conflicts": len(conflicts),
                "rules_executed": len(selected),
                "iterations": iterations,
                "evidence_links": sum(len(item.evidence_ids) for item in derived),
            },
        }

    def explain(
        self, relation_id: str, rules: Iterable[InferenceRule] | None = None
    ) -> dict[str, Any]:
        result = self.infer(rules)
        for relation in result["derived_relations"]:
            if relation["id"] == relation_id:
                return relation
        raise KeyError(relation_id)

    def query(
        self,
        result: dict[str, Any],
        *,
        source_id: str | None = None,
        target_id: str | None = None,
        relation_type: str | None = None,
        minimum_confidence: float = 0.0,
    ) -> list[dict[str, Any]]:
        return [
            item
            for item in result.get("derived_relations", [])
            if (source_id is None or item["source_id"] == source_id)
            and (target_id is None or item["target_id"] == target_id)
            and (relation_type is None or item["relation_type"] == relation_type)
            and float(item.get("confidence", 0.0)) >= minimum_confidence
        ]

    def detect_property_conflicts(self) -> list[InferenceConflict]:
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for prop in self.properties:
            grouped[(prop["owner_id"], prop["name"])].append(prop)
        conflicts: list[InferenceConflict] = []
        for (owner_id, name), properties in sorted(grouped.items()):
            normalized = {self._normalize_value(item.get("value")) for item in properties}
            if len(normalized) <= 1:
                continue
            property_ids = tuple(sorted(item["id"] for item in properties))
            evidence_ids = tuple(
                sorted({eid for item in properties for eid in item.get("evidence_ids", [])})
            )
            digest = sha256(f"{owner_id}|{name}|{'|'.join(property_ids)}".encode()).hexdigest()[:20]
            conflicts.append(
                InferenceConflict(
                    id=f"conflict-{digest}",
                    subject_id=owner_id,
                    predicate=name,
                    values=tuple(item.get("value") for item in properties),
                    property_ids=property_ids,
                    evidence_ids=evidence_ids,
                )
            )
        return conflicts

    def _apply_transitive(
        self,
        rule: InferenceRule,
        premise_facts: list[dict[str, Any]],
        *,
        iteration: int,
    ) -> list[DerivedRelation]:
        if not rule.transitive:
            return []
        adjacency: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for relation in premise_facts:
            adjacency[relation["source_id"]].append(relation)
        for relations in adjacency.values():
            relations.sort(key=lambda item: (item["target_id"], item["id"]))

        output: list[DerivedRelation] = []
        for source_id in sorted(adjacency):
            queue = deque([(source_id, tuple(), 1.0)])
            visited_depth: dict[str, int] = {source_id: 0}
            while queue:
                current, path, path_confidence = queue.popleft()
                if len(path) >= rule.max_depth:
                    continue
                for relation in adjacency.get(current, []):
                    target = relation["target_id"]
                    next_path = path + (relation,)
                    relation_confidence = float(relation.get("confidence", 1.0))
                    confidence = min(path_confidence, relation_confidence) * rule.confidence_factor
                    depth = len(next_path)
                    if depth >= 2 and target != source_id:
                        explanation = tuple(self._explanation_step(item) for item in next_path)
                        evidence_ids = tuple(
                            sorted(
                                {
                                    evidence_id
                                    for step in explanation
                                    for evidence_id in step.evidence_ids
                                }
                            )
                        )
                        digest = sha256(
                            f"{rule.id}|{source_id}|{target}|"
                            f"{'|'.join(step.relation_id for step in explanation)}".encode()
                        ).hexdigest()[:24]
                        output.append(
                            DerivedRelation(
                                id=f"inference-{digest}",
                                source_id=source_id,
                                relation_type=rule.conclusion_relation,
                                target_id=target,
                                confidence=round(max(0.0, min(1.0, confidence)), 6),
                                rule_id=rule.id,
                                explanation=explanation,
                                evidence_ids=evidence_ids,
                                iteration=iteration,
                                metadata={
                                    "path_length": depth,
                                    "premise_relation": rule.premise_relation,
                                    "evidence_fused": len(evidence_ids) > 1,
                                },
                            )
                        )
                    if target == source_id:
                        continue
                    previous_depth = visited_depth.get(target)
                    if previous_depth is None or depth < previous_depth:
                        visited_depth[target] = depth
                        queue.append((target, next_path, confidence))
        return output

    @staticmethod
    def _normalize_relation(item: dict[str, Any], *, derived: bool) -> dict[str, Any]:
        return {
            **item,
            "confidence": float(item.get("confidence", 1.0)),
            "evidence_ids": list(item.get("evidence_ids", [])),
            "derived": derived,
        }

    @staticmethod
    def _derived_fact(item: DerivedRelation) -> dict[str, Any]:
        return {
            "id": item.id,
            "source_id": item.source_id,
            "relation_type": item.relation_type,
            "target_id": item.target_id,
            "confidence": item.confidence,
            "evidence_ids": list(item.evidence_ids),
            "derived": True,
            "rule_id": item.rule_id,
        }

    @staticmethod
    def _explanation_step(item: dict[str, Any]) -> ExplanationStep:
        return ExplanationStep(
            relation_id=item["id"],
            source_id=item["source_id"],
            relation_type=item["relation_type"],
            target_id=item["target_id"],
            confidence=float(item.get("confidence", 1.0)),
            derived=bool(item.get("derived", False)),
            rule_id=item.get("rule_id"),
            evidence_ids=tuple(sorted(item.get("evidence_ids", []))),
        )

    @staticmethod
    def _normalize_value(value: Any) -> str:
        if isinstance(value, str):
            return value.strip().casefold()
        return repr(value)

    @staticmethod
    def _relation_payload(item: DerivedRelation) -> dict[str, Any]:
        return {
            "id": item.id,
            "source_id": item.source_id,
            "relation_type": item.relation_type,
            "target_id": item.target_id,
            "confidence": item.confidence,
            "rule_id": item.rule_id,
            "explanation": [step.__dict__ for step in item.explanation],
            "evidence_ids": list(item.evidence_ids),
            "iteration": item.iteration,
            "metadata": item.metadata,
        }
