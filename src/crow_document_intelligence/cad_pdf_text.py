"""Repair text extracted from CAD-exported PDFs with shifted font encodings.

Drawing PDFs exported from CAD tools often embed subset fonts whose
character map is offset from ASCII. The observed pattern (Mandelblomman,
AutoCAD export) is a uniform +0x1D shift for ASCII letters/digits plus a
small table for Swedish characters: "(175e" -> "ENTRÉ",
"+$1'/b**$5(" -> "HANDLÄGGARE", "XQGHUYnQLQJ" -> "undervåning",
"Pð" -> "m²".

The repair is evidence-preserving: tokens are only remapped when the
candidate is overwhelmingly more plausible than the raw token, and the
caller receives both the repaired text and the raw original.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SHIFT = 0x1D
_SPECIAL = {
    "b": "Ä", "c": "Å", "d": "Ö", "e": "É",
    "m": "ä", "n": "å", "o": "ö",
    "ð": "²", "ñ": "³",
}
_PLAUSIBLE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖÉabcdefghijklmnopqrstuvwxyzåäöé²³")
_TOKEN = re.compile(r"\S+")


def _map_char(char: str) -> str | None:
    code = ord(char)
    if 0x24 <= code <= 0x5A:
        return chr(code + _SHIFT)
    if char in _SPECIAL:
        return _SPECIAL[char]
    if char in "/|":
        return chr(ord("L") if char == "/" else ord("y"))
    return None


def _candidate(token: str) -> str | None:
    if all(char.isdigit() or char in ":./,-%" for char in token):
        # Pure numbers, dates and scales (2014-02-12, 1:50) are kept as-is:
        # measurements outrank the rare shifted all-digit word.
        return None
    mapped: list[str] = []
    hits = 0
    for char in token:
        replacement = _map_char(char)
        if replacement is None:
            mapped.append(char)
        else:
            mapped.append(replacement)
            hits += 1
    if hits < max(2, int(len(token) * 0.7)):
        return None
    candidate = "".join(mapped)
    plausible = sum(1 for char in candidate if char in _PLAUSIBLE)
    if plausible / len(candidate) < 0.8:
        return None
    if token.isascii() and token.isalpha():
        # A raw token that is already a consistently cased ASCII word
        # (TRAPPHUS, kvm, Datum) is presumed clean. The shifted pattern
        # betrays itself through implausible mixed case (XQGHUYnQLQJ).
        if token.isupper() or token.islower() or token.istitle():
            return None
    return candidate


@dataclass(frozen=True)
class RepairedText:
    text: str
    raw: str
    remapped_tokens: int

    @property
    def was_remapped(self) -> bool:
        return self.remapped_tokens > 0


def repair_cad_pdf_text(raw: str) -> RepairedText:
    remapped = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal remapped
        token = match.group(0)
        candidate = _candidate(token)
        if candidate is None:
            return token
        remapped += 1
        return candidate

    return RepairedText(text=_TOKEN.sub(replace, raw), raw=raw, remapped_tokens=remapped)
