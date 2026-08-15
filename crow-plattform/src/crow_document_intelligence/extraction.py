from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfReader

from .document_model import (
    BoundingBox,
    DocumentPage,
    DocumentRegion,
    PageContentStatus,
    RegionKind,
)


def extract_pdf_structure(
    path: Path,
    document_id: str,
) -> tuple[tuple[DocumentPage, ...], tuple[DocumentRegion, ...]]:
    reader = PdfReader(path)
    pages: list[DocumentPage] = []
    regions: list[DocumentRegion] = []

    for index, pdf_page in enumerate(reader.pages, start=1):
        text = (pdf_page.extract_text() or "").strip()
        width = float(pdf_page.mediabox.width)
        height = float(pdf_page.mediabox.height)
        rotation = int(pdf_page.get("/Rotate", 0) or 0) % 360
        status = PageContentStatus.TEXT_AVAILABLE if text else PageContentStatus.OCR_REQUIRED
        page_id = f"{document_id}:page:{index}"
        page = DocumentPage(
            id=page_id,
            document_id=document_id,
            page_number=index,
            width_points=width,
            height_points=height,
            rotation_degrees=rotation,
            content_status=status,
            text=text,
            text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )
        pages.append(page)
        regions.append(
            DocumentRegion(
                id=f"{page_id}:region:page",
                document_id=document_id,
                page_id=page_id,
                page_number=index,
                kind=RegionKind.PAGE,
                bounds=BoundingBox(0.0, 0.0, 1.0, 1.0),
                text=text or None,
                confidence=1.0,
            )
        )
    return tuple(pages), tuple(regions)
