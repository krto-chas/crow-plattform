from __future__ import annotations

import json
from datetime import date
from importlib.resources import files
from typing import Any

from .models import RuleReference, RuleSource, RuleStatus


def load_regulation_library() -> tuple[RuleSource, ...]:
    raw = files("crow_regulations").joinpath("regulations.json").read_text(encoding="utf-8")
    payload: Any = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        raise ValueError("regulations.json must contain a sources list")
    sources = tuple(_source_from_payload(item) for item in payload["sources"])
    ids = [source.source_id for source in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate regulation source_id")
    reference_ids = [ref.reference_id for source in sources for ref in source.references]
    if len(reference_ids) != len(set(reference_ids)):
        raise ValueError("duplicate regulation reference_id")
    return sources


def source_by_id(source_id: str) -> RuleSource:
    for source in load_regulation_library():
        if source.source_id == source_id:
            return source
    raise KeyError(source_id)


def reference_by_id(reference_id: str) -> tuple[RuleSource, RuleReference]:
    for source in load_regulation_library():
        for reference in source.references:
            if reference.reference_id == reference_id:
                return source, reference
    raise KeyError(reference_id)


def search_regulations(
    *,
    topics: tuple[str, ...] = (),
    active_on: date | None = None,
    include_historical: bool = True,
) -> tuple[RuleSource, ...]:
    wanted = set(topics)
    result: list[RuleSource] = []
    for source in load_regulation_library():
        if not include_historical and source.status is RuleStatus.HISTORICAL:
            continue
        if active_on is not None and not source.active_on(active_on):
            continue
        if wanted and not wanted.intersection(source.topics):
            continue
        result.append(source)
    return tuple(result)


def _source_from_payload(value: object) -> RuleSource:
    if not isinstance(value, dict):
        raise ValueError("regulation source must be an object")
    references_raw = value.get("references", [])
    if not isinstance(references_raw, list):
        raise ValueError("references must be a list")
    return RuleSource(
        source_id=_str(value, "source_id"),
        title=_str(value, "title"),
        issuer=_str(value, "issuer"),
        status=RuleStatus(_str(value, "status")),
        source_url=_str(value, "source_url"),
        effective_from=_date_or_none(value.get("effective_from")),
        effective_to=_date_or_none(value.get("effective_to")),
        verified_on=date(2026, 8, 9),
        supersedes=_str_tuple(value.get("supersedes", [])),
        amended_by=_str_tuple(value.get("amended_by", [])),
        topics=_str_tuple(value.get("topics", [])),
        references=tuple(_reference_from_payload(item) for item in references_raw),
        note=_str(value, "note"),
    )


def _reference_from_payload(value: object) -> RuleReference:
    if not isinstance(value, dict):
        raise ValueError("rule reference must be an object")
    return RuleReference(
        reference_id=_str(value, "reference_id"),
        locator=_str(value, "locator"),
        topics=_str_tuple(value.get("topics", [])),
        note=_str(value, "note"),
    )


def _str(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ValueError(f"{key} must be a non-empty string")
    return result


def _str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("expected list of strings")
    return tuple(value)


def _date_or_none(value: object) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("date must be ISO string or null")
    return date.fromisoformat(value)
