from __future__ import annotations

import re
from collections import defaultdict

from .knowledge import PressureTestKnowledge
from .models import (
    ClaimOrigin,
    TestScopeRequirement,
    TextLocator,
    TightnessClass,
    TightnessConflict,
    TightnessRequirement,
)

_CLASS_PATTERN = re.compile(r"täthetsklass\s+(?P<klass>[A-D])\b", re.IGNORECASE)
_PERCENT_PATTERN = re.compile(r"(?P<value>\d{1,3})\s*%")
_FAMILY_WINDOW = 80


def _family_positions(line: str, knowledge: PressureTestKnowledge) -> tuple[tuple[int, str], ...]:
    lowered = line.casefold()
    hits: list[tuple[int, str]] = []
    for family, terms in knowledge.duct_families.items():
        for term in terms:
            start = 0
            needle = term.casefold()
            while (index := lowered.find(needle, start)) != -1:
                hits.append((index, family))
                start = index + len(needle)
    return tuple(sorted(hits))


def _closest_family(
    position: int, families: tuple[tuple[int, str], ...], prefer_following: bool
) -> str | None:
    if not families:
        return None
    following = [item for item in families if item[0] >= position]
    preceding = [item for item in families if item[0] < position]
    ordered = (following + preceding) if prefer_following else (preceding[::-1] + following)
    for index, family in ordered:
        if abs(index - position) <= _FAMILY_WINDOW:
            return family
    return None


def extract_tightness_requirements(
    text: str,
    document_id: str,
    knowledge: PressureTestKnowledge,
) -> tuple[TightnessRequirement, ...]:
    requirements: list[TightnessRequirement] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        matches = list(_CLASS_PATTERN.finditer(line))
        if not matches:
            continue
        families = _family_positions(line, knowledge)
        for match in matches:
            family = _closest_family(match.end(), families, prefer_following=True)
            if family is None:
                family = _closest_family(match.start(), families, prefer_following=False)
            if family is None or family in {"schakt", "platsbyggd"}:
                continue
            requirements.append(
                TightnessRequirement(
                    duct_family=family,
                    tightness_class=TightnessClass(match.group("klass").upper()),
                    origin=ClaimOrigin.STATED,
                    locator=TextLocator(
                        document_id=document_id,
                        line_number=line_number,
                        source_text=line.strip(),
                    ),
                )
            )
    return tuple(requirements)


def extract_test_scope(
    text: str,
    document_id: str,
    knowledge: PressureTestKnowledge,
) -> tuple[TestScopeRequirement, ...]:
    scopes: list[TestScopeRequirement] = []
    seen: set[tuple[str, int]] = set()
    for line_number, line in enumerate(text.splitlines(), start=1):
        percent_match = _PERCENT_PATTERN.search(line)
        if percent_match is None:
            continue
        families = _family_positions(line, knowledge)
        family = _closest_family(percent_match.start(), families, prefer_following=False)
        if family is None:
            continue
        value = int(percent_match.group("value"))
        key = (family, value)
        if key in seen or value > 100:
            continue
        seen.add(key)
        scopes.append(
            TestScopeRequirement(
                target=family,
                percentage=value,
                origin=ClaimOrigin.STATED,
                locator=TextLocator(
                    document_id=document_id,
                    line_number=line_number,
                    source_text=line.strip(),
                ),
            )
        )
    return tuple(scopes)


def find_conflicts(
    requirements: tuple[TightnessRequirement, ...],
) -> tuple[TightnessConflict, ...]:
    grouped: dict[str, list[TightnessRequirement]] = defaultdict(list)
    for requirement in requirements:
        grouped[requirement.duct_family].append(requirement)
    conflicts: list[TightnessConflict] = []
    for family in sorted(grouped):
        members = grouped[family]
        classes = tuple(sorted({member.tightness_class for member in members}))
        if len(classes) > 1:
            conflicts.append(
                TightnessConflict(
                    duct_family=family,
                    classes=classes,
                    requirements=tuple(members),
                )
            )
    return tuple(conflicts)
