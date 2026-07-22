from __future__ import annotations

from typing import Any


class GraphTimelineBuilder:
    """Build a deterministic project timeline and structural graph diff."""

    def build(
        self,
        graph: dict[str, Any],
        graph_audits: list[dict[str, Any]],
        evidence_audits: list[dict[str, Any]],
    ) -> dict[str, Any]:
        events = []
        for domain, audits in (("graph", graph_audits), ("evidence", evidence_audits)):
            for audit in audits:
                events.append(
                    {
                        "event_type": "audit",
                        "domain": domain,
                        "event_id": audit.get("audit_id"),
                        "occurred_at": audit.get("created_at"),
                        "finding_count": len(audit.get("findings", [])),
                    }
                )
        events.sort(key=lambda x: (str(x.get("occurred_at") or ""), str(x.get("event_id") or "")))
        return {
            "project_id": graph.get("project_id"),
            "current_graph": {
                "objects": len(graph.get("objects", [])),
                "relations": len(graph.get("relations", [])),
                "evidence": len(graph.get("evidence", [])),
                "properties": len(graph.get("properties", [])),
            },
            "events": events,
            "summary": {
                "events": len(events),
                "graph_audits": len(graph_audits),
                "evidence_audits": len(evidence_audits),
            },
            "metadata": {"read_only": True, "graph_mutated": False, "audit_runs_mutated": False},
        }

    def diff(self, base: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
        def ids(payload: dict[str, Any], key: str, id_key: str) -> set[str]:
            return {
                str(x[id_key]) for x in payload.get(key, []) if isinstance(x, dict) and id_key in x
            }

        sections = {}
        for key, id_key in (
            ("objects", "object_id"),
            ("relations", "relation_id"),
            ("evidence", "evidence_id"),
            ("properties", "property_id"),
        ):
            a, b = ids(base, key, id_key), ids(target, key, id_key)
            sections[key] = {
                "added": sorted(b - a),
                "removed": sorted(a - b),
                "unchanged": len(a & b),
            }
        return {
            "sections": sections,
            "metadata": {"deterministic": True, "content_equivalence_asserted": False},
        }
