from pathlib import Path

from crow_authority import (
    DocumentAuthorityType,
    load_authority_manifest,
    write_manifest_template,
)


def test_manifest_template_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "authority.json"

    write_manifest_template(path)
    framework, documents = load_authority_manifest(path)

    assert framework.hierarchy[0] == DocumentAuthorityType.CONTRACT
    assert documents[0].authority_type == (DocumentAuthorityType.TECHNICAL_DESCRIPTION)


def test_manifest_can_override_description_and_drawing_order(tmp_path: Path) -> None:
    path = tmp_path / "authority.json"
    path.write_text(
        """
        {
          "framework_id": "project.afc111",
          "source": "AFC.111",
          "hierarchy": ["drawing", "technical_description"],
          "documents": []
        }
        """,
        encoding="utf-8",
    )

    framework, _ = load_authority_manifest(path)

    assert framework.project_override is True
    assert framework.hierarchy[:2] == (
        DocumentAuthorityType.DRAWING,
        DocumentAuthorityType.TECHNICAL_DESCRIPTION,
    )
