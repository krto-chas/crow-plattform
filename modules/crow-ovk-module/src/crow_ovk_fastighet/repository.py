"""Filbaserade repositorier för fastigheter (per projekt) och besiktningsmän (globalt)."""

from __future__ import annotations

import json
from pathlib import Path

from .models import (
    Besiktningsman,
    Fastighet,
    besiktningsman_from_payload,
    besiktningsman_to_payload,
    fastighet_from_payload,
    fastighet_to_payload,
)

_ALLOWED_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")


def _safe_identifier(value: str, field: str) -> None:
    if not value or any(char not in _ALLOWED_ID_CHARS for char in value):
        raise ValueError(f"invalid {field}")


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
    return path


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("stored payload must be an object")
    return payload


class FastighetRepository:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, fastighet: Fastighet) -> Path:
        return _write_json(
            self._path(fastighet.project_id, fastighet.fastighet_id),
            fastighet_to_payload(fastighet),
        )

    def load(self, project_id: str, fastighet_id: str) -> Fastighet:
        return fastighet_from_payload(_read_json(self._path(project_id, fastighet_id)))

    def list(self, project_id: str) -> tuple[Fastighet, ...]:
        _safe_identifier(project_id, "project_id")
        directory = self.root / "projects" / project_id / "fastighet"
        if not directory.exists():
            return ()
        return tuple(self.load(project_id, path.stem) for path in sorted(directory.glob("*.json")))

    def _path(self, project_id: str, fastighet_id: str) -> Path:
        _safe_identifier(project_id, "project_id")
        _safe_identifier(fastighet_id, "fastighet_id")
        return self.root / "projects" / project_id / "fastighet" / f"{fastighet_id}.json"


class BesiktningsmanRepository:
    """Företagsgemensamt register, inte projektbundet."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, person: Besiktningsman) -> Path:
        return _write_json(self._path(person.besiktningsman_id), besiktningsman_to_payload(person))

    def load(self, besiktningsman_id: str) -> Besiktningsman:
        return besiktningsman_from_payload(_read_json(self._path(besiktningsman_id)))

    def list(self) -> tuple[Besiktningsman, ...]:
        directory = self.root / "registry" / "besiktningsman"
        if not directory.exists():
            return ()
        return tuple(self.load(path.stem) for path in sorted(directory.glob("*.json")))

    def _path(self, besiktningsman_id: str) -> Path:
        _safe_identifier(besiktningsman_id, "besiktningsman_id")
        return self.root / "registry" / "besiktningsman" / f"{besiktningsman_id}.json"
