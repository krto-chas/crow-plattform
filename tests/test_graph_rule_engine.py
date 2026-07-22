from dataclasses import dataclass

import pytest

from crow_graph_rules import (
    GraphRuleContext,
    GraphRuleEngine,
    GraphRuleFinding,
    GraphRuleMetadata,
)


@dataclass(frozen=True)
class _Rule:
    metadata: GraphRuleMetadata

    def evaluate(self, context: GraphRuleContext) -> tuple[GraphRuleFinding, ...]:
        if context.objects:
            return ()
        return (
            GraphRuleFinding(
                finding_id=f"finding:{self.metadata.rule_id}",
                rule_id=self.metadata.rule_id,
                rule_version=self.metadata.version,
                category="data_quality",
                severity=self.metadata.severity,
                status="verified",
                message="Grafen saknar objekt.",
            ),
        )


def _metadata(rule_id: str = "GENERAL-001") -> GraphRuleMetadata:
    return GraphRuleMetadata(
        rule_id=rule_id,
        version="1.0.0",
        title="Testregel",
        description="Deterministisk testregel.",
        discipline="GENERAL",
        severity="warning",
        evidence_required=False,
    )


def test_engine_evaluates_typed_rule_and_reports_execution_metadata() -> None:
    result = GraphRuleEngine().evaluate({"objects": [], "relations": []}, (_Rule(_metadata()),))

    assert result.summary == {"total": 1, "data_quality": 1}
    assert result.findings[0].rule_id == "GENERAL-001"
    assert result.metadata["rules_evaluated"] == 1
    assert result.metadata["inference_performed"] is False
    assert result.metadata["automatic_correction_performed"] is False


def test_disabled_rule_is_not_evaluated() -> None:
    metadata = GraphRuleMetadata(
        **{**_metadata().__dict__, "enabled": False},
    )
    result = GraphRuleEngine().evaluate({}, (_Rule(metadata),))

    assert result.findings == ()
    assert result.metadata["rules_evaluated"] == 0


def test_duplicate_rule_ids_are_rejected() -> None:
    rule = _Rule(_metadata())
    with pytest.raises(ValueError, match="Dubblerat rule_id"):
        GraphRuleEngine().evaluate({}, (rule, rule))


def test_rule_metadata_rejects_auto_inference_claim_only_when_invalid_fields() -> None:
    metadata = _metadata()
    metadata.validate()
    assert metadata.supports_auto_inference is False

    invalid = GraphRuleMetadata(
        **{**metadata.__dict__, "discipline": "UNKNOWN"},
    )
    with pytest.raises(ValueError, match="Ogiltig disciplin"):
        invalid.validate()
