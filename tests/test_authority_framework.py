from crow_authority import (
    DEFAULT_AB04_HIERARCHY,
    DocumentAuthorityType,
    ab04_framework,
    project_framework,
)


def test_ab04_hierarchy_places_description_before_drawing() -> None:
    hierarchy = DEFAULT_AB04_HIERARCHY

    assert hierarchy.index(DocumentAuthorityType.TECHNICAL_DESCRIPTION) < hierarchy.index(
        DocumentAuthorityType.DRAWING
    )


def test_project_override_is_marked_and_completed() -> None:
    framework = project_framework(
        (
            DocumentAuthorityType.DRAWING,
            DocumentAuthorityType.TECHNICAL_DESCRIPTION,
        ),
        source="AFC.111",
    )

    assert framework.project_override is True
    assert framework.hierarchy[0] == DocumentAuthorityType.DRAWING
    assert DocumentAuthorityType.CONTRACT in framework.hierarchy


def test_default_framework_is_not_project_override() -> None:
    assert ab04_framework().project_override is False
