from crow_document_intelligence import (
    BoundingBox,
    DocumentPage,
    DocumentRegion,
    PageContentStatus,
    RegionKind,
)
from crow_observation_engine import ObservationType, extract_observations


def page_and_region(text: str) -> tuple[DocumentPage, DocumentRegion]:
    page = DocumentPage(
        id="doc:1:page:1",
        document_id="doc:1",
        page_number=1,
        width_points=100.0,
        height_points=100.0,
        rotation_degrees=0,
        content_status=PageContentStatus.TEXT_AVAILABLE,
        text=text,
        text_sha256="pagehash",
    )
    region = DocumentRegion(
        id="doc:1:page:1:region:page",
        document_id="doc:1",
        page_id=page.id,
        page_number=1,
        kind=RegionKind.PAGE,
        bounds=BoundingBox(0, 0, 1, 1),
        text=text,
    )
    return page, region


def test_extracts_numbers_units_references_and_dates() -> None:
    page, region = page_and_region("LUFTFLÖDE\n320 l/s enligt V-57.1-100 2026-07-18")
    observations = extract_observations(page, region)
    types = {item.observation_type for item in observations}

    assert ObservationType.NUMBER in types
    assert ObservationType.UNIT in types
    assert ObservationType.REFERENCE in types
    assert ObservationType.DATE in types
    assert ObservationType.HEADING in types
    assert ObservationType.TEXT in types


def test_locator_contains_page_region_and_offsets() -> None:
    page, region = page_and_region("Ø160 mm")
    observation = next(
        item
        for item in extract_observations(page, region)
        if item.observation_type == ObservationType.UNIT
    )

    assert "#page=1" in observation.evidence.locator.value
    assert "&region=" in observation.evidence.locator.value
    assert "&chars=" in observation.evidence.locator.value


def test_observation_id_is_stable() -> None:
    page, region = page_and_region("320 l/s")
    first = extract_observations(page, region)
    second = extract_observations(page, region)

    assert [item.id for item in first] == [item.id for item in second]
