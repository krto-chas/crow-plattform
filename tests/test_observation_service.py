from pathlib import Path

from crow_document_intelligence import (
    BoundingBox,
    DocumentIndex,
    DocumentPage,
    DocumentRegion,
    PageContentStatus,
    RegionKind,
)
from crow_observation_engine import (
    load_collection,
    observe_index,
    save_collection,
    summarize_observations,
)


def make_index(text: str) -> DocumentIndex:
    page = DocumentPage(
        id="doc:1:page:1",
        document_id="doc:1",
        page_number=1,
        width_points=100,
        height_points=100,
        rotation_degrees=0,
        content_status=PageContentStatus.TEXT_AVAILABLE,
        text=text,
        text_sha256="hash",
    )
    region = DocumentRegion(
        id="region:1",
        document_id="doc:1",
        page_id=page.id,
        page_number=1,
        kind=RegionKind.PAGE,
        bounds=BoundingBox(0, 0, 1, 1),
        text=text,
    )
    return DocumentIndex(
        project_id="project",
        project_name="Project",
        pages=(page,),
        regions=(region,),
    )


def test_collection_detects_duplicate_content() -> None:
    collection = observe_index(make_index("10 mm 10 mm"))
    summary = summarize_observations(collection)

    assert summary["observations"] > summary["unique_content"]
    assert summary["duplicates"] > 0


def test_collection_round_trip(tmp_path: Path) -> None:
    collection = observe_index(make_index("320 l/s"))
    path = tmp_path / "observations.json"

    save_collection(collection, path)
    loaded = load_collection(path)

    assert loaded == collection
