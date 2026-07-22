from __future__ import annotations

from typing import Any


class ImportPipelineOrchestrator:
    """Create deterministic, recoverable import plans without executing adapters."""

    ORDER = {"ifc": 10, "dxf": 20, "dwg": 30, "pdf": 40}

    def build_plan(self, manifest: dict[str, Any]) -> dict[str, Any]:
        project_id = self._required(manifest, "project_id")
        sources = manifest.get("sources", [])
        if not isinstance(sources, list):
            raise ValueError("Manifest sources must be a list")
        steps: list[dict[str, Any]] = []
        for source in sources:
            if not isinstance(source, dict):
                raise ValueError("Manifest source must be an object")
            source_id = self._required(source, "source_id")
            fmt = str(source.get("type", "unknown")).lower()
            adapter = str(source.get("imported_by", "unknown"))
            steps.append(
                {
                    "step_id": f"import:{source_id}",
                    "source_id": source_id,
                    "format": fmt,
                    "adapter": adapter,
                    "order": self.ORDER.get(fmt, 99),
                    "status": "blocked" if adapter == "unknown" else "ready",
                    "checkpoint": f"source:{source.get('sha256') or source_id}",
                }
            )
        steps.sort(key=lambda x: (int(x["order"]), str(x["source_id"])))
        return {
            "project_id": project_id,
            "steps": steps,
            "summary": {
                "total": len(steps),
                "ready": sum(x["status"] == "ready" for x in steps),
                "blocked": sum(x["status"] == "blocked" for x in steps),
            },
            "recovery": {
                "checkpointed": True,
                "resume_from": "last_completed_step",
                "completed_steps": [],
            },
            "metadata": {
                "read_only": True,
                "automatic_import_performed": False,
                "project_files_mutated": False,
            },
        }

    @staticmethod
    def _required(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing required string: {key}")
        return value
