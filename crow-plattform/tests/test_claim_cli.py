from pathlib import Path

from crow_document_intelligence import (
    BoundingBox,
    DocumentIndex,
    DocumentPage,
    DocumentRegion,
    PageContentStatus,
    RegionKind,
    save_index,
)
from crow_module_conformance.cli import main


def test_claims_cli_creates_observations_and_candidates(
    tmp_path: Path,
    capsys: object,
) -> None:
    page = DocumentPage(
        id="doc:1:page:1",
        document_id="doc:1",
        page_number=1,
        width_points=100,
        height_points=100,
        rotation_degrees=0,
        content_status=PageContentStatus.TEXT_AVAILABLE,
        text="Luftflöde: 320 l/s",
        text_sha256="hash",
    )
    region = DocumentRegion(
        id="region:1",
        document_id="doc:1",
        page_id=page.id,
        page_number=1,
        kind=RegionKind.PAGE,
        bounds=BoundingBox(0, 0, 1, 1),
        text=page.text,
    )
    project_file = tmp_path / "crow-project.json"
    save_index(
        DocumentIndex(
            project_id="project",
            project_name="Project",
            pages=(page,),
            regions=(region,),
        ),
        project_file,
    )

    assert main(["claims", str(project_file), "--json"]) == 0
    assert (tmp_path / "crow-observations.json").exists()
    assert (tmp_path / "crow-claim-candidates.json").exists()
