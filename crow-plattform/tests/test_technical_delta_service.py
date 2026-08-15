from pathlib import Path

from crow_technical_delta import (
    TechnicalDeltaSet,
    load_baseline,
    load_delta_set,
    save_delta_set,
    summarize_deltas,
    write_baseline_template,
)


def test_baseline_template_loads(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    write_baseline_template(path, "project")

    baseline = load_baseline(path)

    assert baseline.project_id == "project"
    assert baseline.baseline_id == "baseline.contract"
    assert len(baseline.items) == 1


def test_delta_set_round_trip(tmp_path: Path) -> None:
    delta_set = TechnicalDeltaSet(project_id="project", baseline_id="base")
    path = tmp_path / "deltas.json"

    save_delta_set(delta_set, path)

    assert load_delta_set(path) == delta_set


def test_empty_delta_summary() -> None:
    summary = summarize_deltas(TechnicalDeltaSet(project_id="project", baseline_id="base"))

    assert summary["total"] == 0
    assert summary["changed"] == 0
