from __future__ import annotations

from typing import Any


class Rc1WorkbenchBuilder:
    """Aggregate implemented read-only RC1 explorer capabilities."""

    REQUIRED = (
        "graph",
        "evidence",
        "audit",
        "rules",
        "assurance",
        "sources",
        "pipeline",
        "cross_source_links",
        "timeline",
    )

    def build(self, project_id: str, capabilities: dict[str, Any]) -> dict[str, Any]:
        views = []
        for name in self.REQUIRED:
            value = capabilities.get(name)
            views.append(
                {
                    "view": name,
                    "available": value is not None,
                    "summary": value.get("summary", {}) if isinstance(value, dict) else {},
                }
            )
        return {
            "project_id": project_id,
            "milestone": "RC1 Workbench Beta",
            "views": views,
            "summary": {
                "available": sum(v["available"] for v in views),
                "required": len(views),
                "complete": all(v["available"] for v in views),
            },
            "metadata": {
                "read_only_aggregation": True,
                "technical_correctness_asserted": False,
                "release_asserted": False,
            },
        }
