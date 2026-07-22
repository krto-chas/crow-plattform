from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from crow_canonical import CanonicalObject


@dataclass(frozen=True)
class PdfPageEvidence:
    page_number: int
    text: str
    text_sha256: str
    extraction_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PdfEvidenceExtraction:
    schema_version: str
    source_id: str
    source_sha256: str
    page_count: int
    text_page_count: int
    ocr_required_page_count: int
    pages: tuple[PdfPageEvidence, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "pages": [page.to_dict() for page in self.pages],
        }


@dataclass(frozen=True)
class PdfObjectEvidenceLink:
    link_id: str
    canonical_id: str
    object_name: str
    source_id: str
    source_sha256: str
    page_number: int
    locator: str
    matched_text: str
    match_method: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PdfEvidenceLinkResult:
    extraction: PdfEvidenceExtraction
    links: tuple[PdfObjectEvidenceLink, ...]
    unmatched_object_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "crow-pdf-evidence-link-v0.1",
            "extraction": self.extraction.to_dict(),
            "link_count": len(self.links),
            "links": [link.to_dict() for link in self.links],
            "unmatched_object_ids": list(self.unmatched_object_ids),
            "ocr_performed": False,
            "semantic_inference_performed": False,
            "automatic_object_merge_performed": False,
            "graph_mutated": False,
        }


class PdfEvidenceExtractor:
    """Extract embedded PDF text page-by-page; never performs OCR implicitly."""

    def extract_path(self, path: Path, *, source_id: str | None = None) -> PdfEvidenceExtraction:
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Unsupported PDF evidence source format: {path.suffix or '<none>'}")
        raw = path.read_bytes()
        digest = sha256(raw).hexdigest()
        reader = PdfReader(path)
        pages: list[PdfPageEvidence] = []
        warnings: list[str] = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            status = "text_available" if text else "ocr_required"
            pages.append(
                PdfPageEvidence(
                    page_number=index,
                    text=text,
                    text_sha256=sha256(text.encode("utf-8")).hexdigest(),
                    extraction_status=status,
                )
            )
        ocr_required = sum(page.extraction_status == "ocr_required" for page in pages)
        if ocr_required:
            warnings.append(
                f"{ocr_required} page(s) contain no embedded text and require an explicit OCR step."
            )
        return PdfEvidenceExtraction(
            schema_version="crow-pdf-evidence-v0.1",
            source_id=source_id or path.name,
            source_sha256=digest,
            page_count=len(pages),
            text_page_count=len(pages) - ocr_required,
            ocr_required_page_count=ocr_required,
            pages=tuple(pages),
            warnings=tuple(warnings),
        )


class PdfCanonicalEvidenceLinker:
    """Link CCM objects to pages only through exact, boundary-aware name occurrences."""

    @staticmethod
    def _pattern(name: str) -> re.Pattern[str] | None:
        normalized = " ".join(name.strip().split())
        if not normalized:
            return None
        escaped = re.escape(normalized).replace(r"\ ", r"\s+")
        return re.compile(rf"(?<![A-Z0-9ÅÄÖ]){escaped}(?![A-Z0-9ÅÄÖ])", re.IGNORECASE)

    def link(
        self,
        extraction: PdfEvidenceExtraction,
        objects: tuple[CanonicalObject, ...] | list[CanonicalObject],
    ) -> PdfEvidenceLinkResult:
        links: list[PdfObjectEvidenceLink] = []
        unmatched: list[str] = []
        for obj in objects:
            pattern = self._pattern(obj.name)
            object_links = 0
            if pattern is not None:
                for page in extraction.pages:
                    for occurrence, match in enumerate(pattern.finditer(page.text), start=1):
                        link_seed = (
                            f"{obj.canonical_id}|{extraction.source_sha256}|"
                            f"{page.page_number}|{match.start()}|{occurrence}"
                        )
                        links.append(
                            PdfObjectEvidenceLink(
                                link_id=f"pdf-link-{sha256(link_seed.encode()).hexdigest()[:20]}",
                                canonical_id=obj.canonical_id,
                                object_name=obj.name,
                                source_id=extraction.source_id,
                                source_sha256=extraction.source_sha256,
                                page_number=page.page_number,
                                locator=f"page:{page.page_number}:char:{match.start()}-{match.end()}",
                                matched_text=match.group(0),
                                match_method="exact_name_boundary",
                                confidence=1.0,
                            )
                        )
                        object_links += 1
            if object_links == 0:
                unmatched.append(obj.canonical_id)
        return PdfEvidenceLinkResult(
            extraction=extraction,
            links=tuple(links),
            unmatched_object_ids=tuple(unmatched),
        )

    def link_path(
        self,
        path: Path,
        objects: tuple[CanonicalObject, ...] | list[CanonicalObject],
        *,
        source_id: str | None = None,
    ) -> PdfEvidenceLinkResult:
        extraction = PdfEvidenceExtractor().extract_path(path, source_id=source_id)
        return self.link(extraction, objects)
