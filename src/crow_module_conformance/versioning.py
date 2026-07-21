from __future__ import annotations

import re
from dataclasses import dataclass

_VERSION = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?P<prerelease>-[0-9A-Za-z.-]+)?"
    r"(?P<build>\+[0-9A-Za-z.-]+)?$"
)

_COMPARATOR = re.compile(r"^(>=|<=|>|<|==|=)?\s*(\d+\.\d+(?:\.\d+)?(?:-[0-9A-Za-z.-]+)?)$")


@dataclass(frozen=True, order=True, slots=True)
class Version:
    major: int
    minor: int
    patch: int
    prerelease_rank: int
    prerelease: str

    @classmethod
    def parse(cls, value: str) -> Version:
        match = _VERSION.fullmatch(value.strip())
        if match is None:
            raise ValueError(f"Invalid semantic version: {value}")
        prerelease = (match.group("prerelease") or "").removeprefix("-")
        return cls(
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
            0 if prerelease else 1,
            prerelease,
        )


def _normalise_short_version(value: str) -> str:
    core, separator, suffix = value.partition("-")
    if core.count(".") == 1:
        core += ".0"
    return core + (separator + suffix if separator else "")


def satisfies(version: str, expression: str) -> bool:
    parsed = Version.parse(_normalise_short_version(version))
    parts = [part.strip() for part in expression.split(",") if part.strip()]
    if not parts:
        raise ValueError("Version expression must not be empty")

    for part in parts:
        match = _COMPARATOR.fullmatch(part)
        if match is None:
            raise ValueError(f"Unsupported version comparator: {part}")
        operator = match.group(1) or "=="
        expected = Version.parse(_normalise_short_version(match.group(2)))
        if operator in ("=", "==") and parsed != expected:
            return False
        if operator == ">=" and parsed < expected:
            return False
        if operator == "<=" and parsed > expected:
            return False
        if operator == ">" and parsed <= expected:
            return False
        if operator == "<" and parsed >= expected:
            return False
    return True
