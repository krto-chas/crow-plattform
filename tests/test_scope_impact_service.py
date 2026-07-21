from pathlib import Path

from crow_scope_impact import (
    ScopeImpactSet,
    load_rule_set,
    load_scope_impacts,
    save_scope_impacts,
    summarize_scope_impacts,
    write_rule_set_template,
)


def test_rule_template_loads(tmp_path: Path) -> None:
    path = tmp_path / "scope-rules.json"
    write_rule_set_template(path)

    rules = load_rule_set(path)

    assert rules.id == "crow.scope.ventilation.example"
    assert len(rules.rules) == 1


def test_scope_impact_round_trip(tmp_path: Path) -> None:
    result = ScopeImpactSet(
        project_id="project",
        baseline_id="baseline",
        rule_set_id="rules",
    )
    path = tmp_path / "scope.json"

    save_scope_impacts(result, path)

    assert load_scope_impacts(path) == result


def test_scope_summary() -> None:
    summary = summarize_scope_impacts(
        ScopeImpactSet(
            project_id="project",
            baseline_id="baseline",
            rule_set_id="rules",
        )
    )

    assert summary["total"] == 0
    assert summary["review_required"] == 0
