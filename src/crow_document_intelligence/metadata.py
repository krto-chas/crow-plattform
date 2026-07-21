from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .models import DocumentMetadata

_REV = (
    re.compile(r"(?:^|[ _.-])rev(?:ision)?[ _.-]*([A-Z0-9]+)(?:$|[ _.-])", re.I),
    re.compile(r"(?:^|[ _.-])([A-Z])(?:$)", re.I),
)
_NUM = re.compile(r"\b([A-Z]{1,3}-\d{2}(?:\.\d+)*(?:-\d+)?)\b", re.I)


def normalize_filename_key(filename: str) -> str:
    stem = Path(filename).stem
    normalized = unicodedata.normalize("NFKD", stem)
    ascii_name = "".join(c for c in normalized if not unicodedata.combining(c))
    ascii_name = re.sub(r"(?i)(?:[ _.-])rev(?:ision)?[ _.-]*[A-Z0-9]+", "", ascii_name)
    return re.sub(r"[^a-z0-9]+", "", ascii_name.lower())


def parse_filename_metadata(filename: str) -> DocumentMetadata:
    stem = Path(filename).stem
    revision = None
    for pattern in _REV:
        match = pattern.search(stem)
        if match:
            revision = match.group(1).upper()
            break
    match = _NUM.search(stem)
    number = match.group(1).upper() if match else None
    discipline = number.split("-", 1)[0] if number else None
    return DocumentMetadata(
        title=stem, document_number=number, revision=revision, discipline=discipline
    )
