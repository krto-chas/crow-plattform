"""Filbaserad lagring av OVK-intyg med atomiska skrivningar och säkra identifierare."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import OvkIntyg
from .service import intyg_from_payload, intyg_to_payload

_ALLOWED_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")


class OvkIntygRepository:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, intyg: OvkIntyg) -> Path:
        """Sparar ett utfärdat intyg. Ett intyg är omutbart: finns intygs-ID:t
        redan höjs ``FileExistsError`` och det lagrade intyget lämnas orört.
        Ett felaktigt intyg ersätts genom nytt utfärdande med nytt ID."""
        path = self._path(intyg.project_id, intyg.intyg_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.stem}.{os.getpid()}.tmp")
        temp.write_text(
            json.dumps(intyg_to_payload(intyg), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        try:
            # Hårdlänk är atomisk och misslyckas om målet finns — två samtidiga
            # utfärdanden med samma ID kan därför aldrig skriva över varandra.
            os.link(temp, path)
        finally:
            temp.unlink(missing_ok=True)
        return path

    def exists(self, project_id: str, intyg_id: str) -> bool:
        return self._path(project_id, intyg_id).exists()

    def load(self, project_id: str, intyg_id: str) -> OvkIntyg:
        path = self._path(project_id, intyg_id)
        if not path.exists():
            raise FileNotFoundError(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("stored OVK intyg must be an object")
        return intyg_from_payload(payload)

    def list(self, project_id: str) -> tuple[OvkIntyg, ...]:
        _safe_identifier(project_id, "project_id")
        directory = self.root / "projects" / project_id / "ovk-intyg"
        if not directory.exists():
            return ()
        return tuple(self.load(project_id, path.stem) for path in sorted(directory.glob("*.json")))

    def _path(self, project_id: str, intyg_id: str) -> Path:
        _safe_identifier(project_id, "project_id")
        _safe_identifier(intyg_id, "intyg_id")
        return self.root / "projects" / project_id / "ovk-intyg" / f"{intyg_id}.json"


def _safe_identifier(value: str, field: str) -> None:
    if not value or any(char not in _ALLOWED_ID_CHARS for char in value):
        raise ValueError(f"invalid {field}")
