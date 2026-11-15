from pathlib import Path


def test_dashboard_renders_read_only_flow_review() -> None:
    page = (
        Path(__file__).resolve().parents[1]
        / "src/crow_ovk_module/assets/dashboard.html"
    ).read_text(encoding="utf-8")
    assert "renderFlowReview(data.flow_protocol)" in page
    assert "flow.system_totals.map(summary)" in page
    assert "group.points.map" in page
    assert "row.comparison_complete" in page
    assert "td.textContent=String(cell" in page
    assert "requestId!==pbRequest" in page
    assert "Ändra mätvärden i fältbesiktningen" in page
