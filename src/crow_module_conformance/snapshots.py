from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any


def _normalise(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _normalise(asdict(value))
    if isinstance(value, dict):
        return {str(key): _normalise(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_normalise(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def render_snapshot(value: Any) -> str:
    return (
        json.dumps(
            _normalise(value),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )


def assert_snapshot(value: Any, snapshot_path: Path, update: bool = False) -> None:
    rendered = render_snapshot(value)
    if update or not snapshot_path.exists():
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(rendered, encoding="utf-8")
        return

    expected = snapshot_path.read_text(encoding="utf-8")
    if rendered != expected:
        raise AssertionError(
            f"Snapshot mismatch: {snapshot_path}. "
            "Run with update=True only after an intentional contract change."
        )
