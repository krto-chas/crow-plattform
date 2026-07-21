from crow_module_sdk import CrowProject, DocumentRole, ProjectDocument


def test_project_operations_append_audit_events() -> None:
    project = CrowProject.create("project-1", "Project", actor="kristoffer")
    project = project.add_document(
        ProjectDocument("SPEC", "Specification", DocumentRole.SPECIFICATION),
        actor="kristoffer",
    )

    assert [event.event_type.value for event in project.audit_events] == [
        "project_created",
        "document_added",
    ]
    assert project.audit_events[0].actor == "kristoffer"
