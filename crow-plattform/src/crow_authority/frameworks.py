from __future__ import annotations

from .models import (
    DEFAULT_AB04_HIERARCHY,
    AuthorityFramework,
    DocumentAuthorityType,
)


def ab04_framework() -> AuthorityFramework:
    return AuthorityFramework(
        id="se.ab04.default",
        name="AB 04 default authority framework",
        hierarchy=DEFAULT_AB04_HIERARCHY,
        source="AB 04 hierarchy configured from project domain rules",
        project_override=False,
    )


def project_framework(
    hierarchy: tuple[DocumentAuthorityType, ...],
    source: str,
    framework_id: str = "project.override",
    name: str = "Project-specific authority framework",
) -> AuthorityFramework:
    if len(set(hierarchy)) != len(hierarchy):
        raise ValueError("Authority hierarchy contains duplicate document types")
    missing = [
        document_type for document_type in DocumentAuthorityType if document_type not in hierarchy
    ]
    return AuthorityFramework(
        id=framework_id,
        name=name,
        hierarchy=hierarchy + tuple(missing),
        source=source,
        project_override=True,
    )
