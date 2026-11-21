"""Ställning för ett utfärdat OVK-intyg, härledd ur manifest och checksummor."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from crow_ovk_intyg import OvkIntyg, OvkIntygRepository, intyg_to_payload

from .ovk_issuance_manifest import manifest_path


def intyg_standing(
    data_root: Path, intyg_repository: OvkIntygRepository, intyg: OvkIntyg
) -> dict[str, Any]:
    """Intygets ställning: ``current``, ``superseded`` eller ``integrity_error``.

    Enda definitionen av vad som räknas som ett giltigt utfärdat intyg. Används
    av statusrutten, verifieringssidan, rättelseflödet och uppdragsöversikten.
    """

    def digest(item: OvkIntyg) -> str:
        canonical = json.dumps(
            intyg_to_payload(item), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
        return sha256(canonical.encode("utf-8")).hexdigest()

    error = {"status": "integrity_error"}
    project_id = intyg.project_id
    if not intyg.inspection_id or any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for char in intyg.inspection_id
    ):
        return error
    try:
        source_path = manifest_path(data_root, project_id, intyg.inspection_id)
        source_bytes = source_path.read_bytes()
        source = json.loads(source_bytes)
        original_id = source["intyg_id"]
        original = intyg_repository.load(project_id, original_id)
        if (
            source["project_id"] != project_id
            or source["inspection_id"] != intyg.inspection_id
            or original.project_id != project_id
            or original.inspection_id != intyg.inspection_id
            or original.intyg_id != original_id
            or source["intyg_sha256"] != digest(original)
        ):
            return error
        directory = data_root / "projects" / project_id / "ovk-correction-manifests"
        path = directory / f"{original_id}.json"
        if not path.exists():
            return {"status": "current"} if intyg.intyg_id == original_id else error
        correction = json.loads(path.read_bytes())
        replacement_id = correction["replacement_intyg_id"]
        replacement = intyg_repository.load(project_id, replacement_id)
        if (
            correction["project_id"] != project_id
            or correction["inspection_id"] != intyg.inspection_id
            or correction["original_intyg_id"] != original_id
            or correction["original_sha256"] != digest(original)
            or correction["original_manifest_sha256"] != sha256(source_bytes).hexdigest()
            or replacement_id == original_id
            or replacement.project_id != project_id
            or replacement.inspection_id != intyg.inspection_id
            or replacement.intyg_id != replacement_id
            or correction["replacement_sha256"] != digest(replacement)
        ):
            return error
        if intyg.intyg_id == original_id:
            return {"status": "superseded", "replacement_intyg_id": replacement_id}
        if intyg.intyg_id == replacement_id:
            return {"status": "current", "original_intyg_id": original_id}
    except (OSError, ValueError, KeyError, TypeError):
        return error
    return error
