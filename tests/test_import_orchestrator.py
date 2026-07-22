from crow_import_orchestrator import ImportPipelineOrchestrator


def test_deterministic_pipeline_and_recovery():
    result = ImportPipelineOrchestrator().build_plan(
        {
            "project_id": "p",
            "sources": [
                {
                    "source_id": "b.pdf",
                    "type": "pdf",
                    "imported_by": "crow_pdf_evidence",
                    "sha256": "2",
                },
                {
                    "source_id": "a.ifc",
                    "type": "ifc",
                    "imported_by": "crow_ifc_relations",
                    "sha256": "1",
                },
            ],
        }
    )
    assert [x["source_id"] for x in result["steps"]] == ["a.ifc", "b.pdf"]
    assert result["recovery"]["checkpointed"] is True
    assert result["metadata"]["automatic_import_performed"] is False
