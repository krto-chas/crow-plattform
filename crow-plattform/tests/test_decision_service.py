from pathlib import Path

from crow_decision_engine import (
    load_decision_result,
    load_rule_set,
    save_decision_result,
    summarize_decisions,
    write_rule_set_template,
)
from crow_decision_engine.models import DecisionEvaluationResult


def test_rule_template_can_be_loaded(tmp_path: Path) -> None:
    path = tmp_path / "rules.json"
    write_rule_set_template(path)

    rule_set = load_rule_set(path)

    assert rule_set.id == "crow.rules.technical.example"
    assert len(rule_set.rules) == 1


def test_decision_result_round_trip(tmp_path: Path) -> None:
    result = DecisionEvaluationResult(project_id="project", rule_set_id="rules")
    path = tmp_path / "decisions.json"

    save_decision_result(result, path)

    assert load_decision_result(path) == result


def test_summary_for_empty_result() -> None:
    summary = summarize_decisions(
        DecisionEvaluationResult(project_id="project", rule_set_id="rules")
    )

    assert summary["evaluated"] == 0
    assert summary["candidates"] == 0
