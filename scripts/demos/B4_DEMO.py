from pathlib import Path
from tempfile import TemporaryDirectory

from crow_claim_extraction import extract_project_claims, summarize_claim_candidates
from crow_document_intelligence import (
    BoundingBox,
    DocumentIndex,
    DocumentPage,
    DocumentRegion,
    PageContentStatus,
    RegionKind,
    save_index,
)

with TemporaryDirectory() as directory:
    path = Path(directory) / "crow-project.json"
    page = DocumentPage(
        id="doc:demo:page:1",
        document_id="doc:demo",
        page_number=1,
        width_points=100,
        height_points=100,
        rotation_degrees=0,
        content_status=PageContentStatus.TEXT_AVAILABLE,
        text="LUFTDATA\nLuftflöde: 320 l/s\nKanal 160 mm\nSe V-57.1-100",
        text_sha256="demo-page-hash",
    )
    region = DocumentRegion(
        id="region:demo",
        document_id="doc:demo",
        page_id=page.id,
        page_number=1,
        kind=RegionKind.PAGE,
        bounds=BoundingBox(0, 0, 1, 1),
        text=page.text,
    )
    save_index(
        DocumentIndex(
            project_id="demo",
            project_name="B4 Demo",
            pages=(page,),
            regions=(region,),
        ),
        path,
    )
    collection, _ = extract_project_claims(path)
    print(summarize_claim_candidates(collection))
