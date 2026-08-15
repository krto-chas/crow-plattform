from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from crow_document_intelligence import DocumentPage, DocumentRegion

from .models import (
    Observation,
    ObservationEvidence,
    ObservationSource,
    ObservationType,
    SourceLocator,
)

_NUMBER = re.compile(r"(?<![\w.-])[-+]?\d+(?:[.,]\d+)?")
_UNIT = re.compile(
    r"(?<!\w)(?:mm|cm|m|m²|m3|m³|l/s|m3/s|m³/s|Pa|kPa|W|kW|°C|%)(?!\w)",
    re.I,
)
_REFERENCE = re.compile(r"\b[A-ZÅÄÖ]{1,3}-?\d{2}(?:\.\d+)*(?:-\d+)?\b", re.I)
_DATE = re.compile(r"\b(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])\b")


@dataclass(frozen=True, slots=True)
class Match:
    observation_type: ObservationType
    value: str
    start: int
    end: int
    confidence: float


def _content_hash(kind: ObservationType, normalized: str) -> str:
    return hashlib.sha256(f"{kind.value}|{normalized}".encode()).hexdigest()


def _observation_id(
    page: DocumentPage,
    region: DocumentRegion,
    match: Match,
) -> str:
    material = (
        f"{page.document_id}|{page.page_number}|{region.id}|"
        f"{match.start}|{match.end}|{match.observation_type.value}|{match.value}"
    )
    return "obs:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _normalize(kind: ObservationType, value: str) -> str:
    normalized = " ".join(value.strip().split())
    if kind == ObservationType.NUMBER:
        normalized = normalized.replace(",", ".")
    if kind in {ObservationType.UNIT, ObservationType.REFERENCE}:
        normalized = normalized.upper()
    return normalized


def _heading_matches(text: str) -> list[Match]:
    matches: list[Match] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        candidate = line.strip()
        start = offset + len(line) - len(line.lstrip())
        if (
            3 <= len(candidate) <= 100
            and any(char.isalpha() for char in candidate)
            and (
                candidate.isupper()
                or candidate.endswith(":")
                or re.match(r"^\d+(?:\.\d+)*\s+\S+", candidate)
            )
        ):
            matches.append(
                Match(
                    ObservationType.HEADING,
                    candidate.rstrip(":"),
                    start,
                    start + len(candidate),
                    0.75,
                )
            )
        offset += len(line)
    return matches


def find_matches(text: str) -> tuple[Match, ...]:
    matches: list[Match] = []
    matches.extend(
        Match(ObservationType.NUMBER, item.group(), item.start(), item.end(), 0.95)
        for item in _NUMBER.finditer(text)
    )
    matches.extend(
        Match(ObservationType.UNIT, item.group(), item.start(), item.end(), 0.95)
        for item in _UNIT.finditer(text)
    )
    matches.extend(
        Match(ObservationType.REFERENCE, item.group(), item.start(), item.end(), 0.90)
        for item in _REFERENCE.finditer(text)
    )
    matches.extend(
        Match(ObservationType.DATE, item.group(), item.start(), item.end(), 0.95)
        for item in _DATE.finditer(text)
    )
    matches.extend(_heading_matches(text))
    if text.strip():
        start = len(text) - len(text.lstrip())
        value = text.strip()
        matches.append(Match(ObservationType.TEXT, value, start, start + len(value), 1.0))
    return tuple(
        sorted(
            matches,
            key=lambda item: (
                item.start,
                item.end,
                item.observation_type.value,
            ),
        )
    )


def extract_observations(
    page: DocumentPage,
    region: DocumentRegion,
) -> tuple[Observation, ...]:
    text = region.text or ""
    observations: list[Observation] = []
    for match in find_matches(text):
        normalized = _normalize(match.observation_type, match.value)
        locator = SourceLocator(
            document_id=page.document_id,
            page_id=page.id,
            page_number=page.page_number,
            region_id=region.id,
            character_start=match.start,
            character_end=match.end,
        )
        evidence = ObservationEvidence(
            source=ObservationSource.EMBEDDED_PDF_TEXT,
            source_text=match.value,
            confidence=match.confidence,
            locator=locator,
            page_sha256=page.text_sha256,
        )
        observations.append(
            Observation(
                id=_observation_id(page, region, match),
                observation_type=match.observation_type,
                value=match.value,
                normalized_value=normalized,
                content_sha256=_content_hash(match.observation_type, normalized),
                evidence=evidence,
            )
        )
    return tuple(observations)
