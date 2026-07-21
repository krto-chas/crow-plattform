from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crow_building_graph.repository import GraphRepository

from .findings import FindingRepository, FindingService
from .rules import RuleDefinition, RuleEngine


class RuleService:
    def __init__(self, graph_path: Path, rules_path: Path | None = None):
        self.repository = GraphRepository(graph_path)
        self.rules_path = rules_path

    def load_rules(self) -> list[dict[str, Any]]:
        if self.rules_path is None or not self.rules_path.exists():
            return []
        payload = json.loads(self.rules_path.read_text(encoding="utf-8"))
        rules = payload.get("rules", payload) if isinstance(payload, dict) else payload
        return [dict(item) for item in rules]

    def validate_rules(self, rules: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        source = rules if rules is not None else self.load_rules()
        validated = [RuleDefinition.from_dict(item) for item in source]
        return {"valid": True, "rule_count": len(validated), "rules": [r.id for r in validated]}

    def evaluate(self, rules: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        source = rules if rules is not None else self.load_rules()
        return RuleEngine(self.repository.load()).evaluate(source)

    def finding_service(self, findings_path: Path | None = None) -> FindingService:
        target = findings_path or self.repository.path.parent / "findings.json"
        return FindingService(FindingRepository(target))

    def synchronize_findings(
        self, rules: list[dict[str, Any]] | None = None, *, actor: str = "rule-engine"
    ) -> dict[str, Any]:
        return self.finding_service().synchronize(self.evaluate(rules), actor=actor)
