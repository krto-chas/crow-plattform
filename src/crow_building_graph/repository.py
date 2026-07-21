from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import CrowEvidence, CrowObject


class GraphRepository:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, list[dict[str, Any]]]:
        if not self.path.exists():
            return {"objects": [], "relations": [], "properties": [], "evidence": [], "history": []}
        data: dict[str, list[dict[str, Any]]] = json.loads(self.path.read_text(encoding="utf-8"))
        for key in ("objects", "relations", "properties", "evidence", "history"):
            data.setdefault(key, [])
        return data

    def save(self, data: dict[str, list[dict[str, Any]]]) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.path)

    @staticmethod
    def _payload(entity: Any) -> dict[str, Any]:
        payload: dict[str, Any] = asdict(entity)
        if isinstance(entity, CrowEvidence):
            payload["kind"] = entity.kind.value
        return payload

    def add(self, collection: str, entity: object) -> dict[str, Any]:
        data = self.load()
        payload = self._payload(entity)
        if any(item.get("id") == payload["id"] for item in data[collection]):
            raise ValueError(f"ID används redan: {payload['id']}")
        data[collection].append(payload)
        self.save(data)
        return payload

    def replace_object(self, entity: CrowObject) -> dict[str, Any]:
        data = self.load()
        payload = self._payload(entity)
        for index, item in enumerate(data["objects"]):
            if item.get("id") == entity.id:
                data["objects"][index] = payload
                self.save(data)
                return payload
        raise KeyError(entity.id)

    def get(self, collection: str, entity_id: str) -> dict[str, Any] | None:
        return next((item for item in self.load()[collection] if item.get("id") == entity_id), None)
