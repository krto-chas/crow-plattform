from crow_graph_timeline import GraphTimelineBuilder


def test_timeline_and_diff_are_deterministic():
    b = GraphTimelineBuilder()
    result = b.build(
        {"project_id": "p", "objects": [{"object_id": "a"}]},
        [{"audit_id": "g", "created_at": "2026-01-01", "findings": []}],
        [],
    )
    assert result["summary"]["events"] == 1
    diff = b.diff({"objects": [{"object_id": "a"}]}, {"objects": [{"object_id": "b"}]})
    assert diff["sections"]["objects"]["added"] == ["b"]
    assert diff["sections"]["objects"]["removed"] == ["a"]
