from __future__ import annotations

import re
from dataclasses import dataclass

from .models import CrowDocument


@dataclass(frozen=True, order=True, slots=True)
class RevisionKey:
    kind: int
    major: int
    suffix: str


_NATURAL = re.compile(r"^(\d+)([A-Z]*)$", re.I)


def normalize_revision(revision: str | None) -> RevisionKey:
    if revision is None or not revision.strip():
        return RevisionKey(0, 0, "")

    value = revision.strip().upper()
    natural = _NATURAL.match(value)
    if natural:
        return RevisionKey(2, int(natural.group(1)), natural.group(2))

    if len(value) == 1 and value.isalpha():
        return RevisionKey(1, ord(value) - ord("A") + 1, "")

    return RevisionKey(1, 0, value)


def logical_identity(document: CrowDocument) -> str:
    return (
        document.metadata.document_number
        or document.fingerprint.filename_key
        or document.fingerprint.metadata_signature
    )


def is_newer_or_equal(candidate: CrowDocument, current: CrowDocument) -> bool:
    return normalize_revision(candidate.metadata.revision) >= normalize_revision(
        current.metadata.revision
    )
