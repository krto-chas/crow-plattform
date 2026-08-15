from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PageContentStatus(StrEnum):
    EMPTY = "empty"
    TEXT_AVAILABLE = "text_available"
    OCR_REQUIRED = "ocr_required"


class RegionKind(StrEnum):
    PAGE = "page"
    TEXT = "text"
    TITLE_BLOCK = "title_block"
    TABLE = "table"
    FIGURE = "figure"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        values = (self.x, self.y, self.width, self.height)
        if any(value < 0.0 or value > 1.0 for value in values):
            raise ValueError("BoundingBox values must be normalized to 0..1")
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("BoundingBox must fit inside the normalized page")


@dataclass(frozen=True, slots=True)
class DocumentPage:
    id: str
    document_id: str
    page_number: int
    width_points: float
    height_points: float
    rotation_degrees: int
    content_status: PageContentStatus
    text: str
    text_sha256: str

    @property
    def locator(self) -> str:
        return f"{self.document_id}#page={self.page_number}"


@dataclass(frozen=True, slots=True)
class DocumentRegion:
    id: str
    document_id: str
    page_id: str
    page_number: int
    kind: RegionKind
    bounds: BoundingBox
    text: str | None = None
    confidence: float = 1.0
    extraction_method: str = "embedded_pdf_text"

    @property
    def locator(self) -> str:
        box = self.bounds
        return (
            f"{self.document_id}#page={self.page_number}"
            f"&xywh={box.x:.6f},{box.y:.6f},{box.width:.6f},{box.height:.6f}"
        )
