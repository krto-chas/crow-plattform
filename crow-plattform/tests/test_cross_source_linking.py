from crow_cross_source_linking import CrossSourceLinkBuilder


def test_links_only_explicit_ids_across_sources():
    graph = {
        "project_id": "p",
        "objects": [
            {"object_id": "a", "metadata": {"external_id": "X", "source_id": "a.ifc"}},
            {"object_id": "b", "metadata": {"external_id": "X", "source_id": "b.dxf"}},
            {"object_id": "c", "metadata": {"source_id": "c.pdf"}},
        ],
    }
    result = CrossSourceLinkBuilder().build(graph)
    assert result["summary"]["candidates"] == 1
    assert result["links"][0]["basis"] == "explicit_external_id"
    assert result["metadata"]["automatic_merge_performed"] is False
