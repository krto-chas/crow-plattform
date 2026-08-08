from __future__ import annotations

import json
from pathlib import Path

from .models import OvkWorkflowRecord
from .service import record_from_payload, record_to_payload


class OvkWorkflowRepository:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, record: OvkWorkflowRecord) -> Path:
        project_id = record.inspection.ovk_object.project_id
        inspection_id = record.inspection.inspection_id
        path = self._path(project_id, inspection_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(record_to_payload(record), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temp.replace(path)
        return path

    def load(self, project_id: str, inspection_id: str) -> OvkWorkflowRecord:
        path = self._path(project_id, inspection_id)
        if not path.exists():
            raise FileNotFoundError(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("stored OVK workflow must be an object")
        return record_from_payload(payload)

    def list(self, project_id: str) -> tuple[OvkWorkflowRecord, ...]:
        directory = self.root / "projects" / project_id / "ovk"
        if not directory.exists():
            return ()
        records = [
            self.load(project_id, path.stem)
            for path in sorted(directory.glob("*.json"))
        ]
        return tuple(records)

    def _path(self, project_id: str, inspection_id: str) -> Path:
        _safe_identifier(project_id, "project_id")
        _safe_identifier(inspection_id, "inspection_id")
        return self.root / "projects" / project_id / "ovk" / f"{inspection_id}.json"


def _safe_identifier(value: str, field: str) -> None:
    if not value or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in value):
        raise ValueError(f"invalid {field}")
