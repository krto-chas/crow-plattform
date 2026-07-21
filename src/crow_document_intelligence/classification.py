from __future__ import annotations

import re
from pathlib import Path

from .models import DocumentRole, DocumentType

_RULES = (
    (
        re.compile(r"(^|[-_ ])AF([-. _]|$)|administrativa", re.I),
        DocumentType.AF,
        DocumentRole.AUTHORITY,
    ),
    (re.compile(r"\bAMA\b", re.I), DocumentType.AMA, DocumentRole.REFERENCE),
    (re.compile(r"brand|brandskydd", re.I), DocumentType.FIRE_SAFETY, DocumentRole.SECONDARY),
    (re.compile(r"rums?beskriv", re.I), DocumentType.ROOM_DESCRIPTION, DocumentRole.SECONDARY),
    (
        re.compile(r"funktions?beskriv", re.I),
        DocumentType.FUNCTIONAL_DESCRIPTION,
        DocumentRole.SECONDARY,
    ),
    (
        re.compile(r"drift|skötsel|operating", re.I),
        DocumentType.OPERATING_INSTRUCTION,
        DocumentRole.REFERENCE,
    ),
    (
        re.compile(r"relations?handling|as[-_ ]?built", re.I),
        DocumentType.AS_BUILT,
        DocumentRole.PRIMARY,
    ),
    (re.compile(r"offert|quotation", re.I), DocumentType.QUOTATION, DocumentRole.SECONDARY),
    (re.compile(r"kalkyl|estimate", re.I), DocumentType.ESTIMATE, DocumentRole.SECONDARY),
    (re.compile(r"protokoll|minutes", re.I), DocumentType.PROTOCOL, DocumentRole.SECONDARY),
    (
        re.compile(r"beskrivning|specifikation|specification", re.I),
        DocumentType.TECHNICAL_SPECIFICATION,
        DocumentRole.PRIMARY,
    ),
    (re.compile(r"^[A-Z]-?\d{2}(?:\.\d+)*-?\d*", re.I), DocumentType.DRAWING, DocumentRole.PRIMARY),
)


def classify_document(filename: str, title: str | None = None) -> tuple[DocumentType, DocumentRole]:
    text = f"{Path(filename).stem} {title or ''}"
    for pattern, kind, role in _RULES:
        if pattern.search(text):
            return kind, role
    return DocumentType.UNKNOWN, DocumentRole.UNKNOWN
