from __future__ import annotations

from collections import Counter
from typing import Any


class SourceExplorerBuilder:
    """Build a deterministic read-only source and provenance projection."""

    def build(self, manifest: dict[str, Any]) -> dict[str, Any]:
        project_id = self._required_string(manifest, "project_id")
        raw_sources = manifest.get("sources", [])
        if not isinstance(raw_sources, list):
            raise ValueError("Manifest sources must be a list")
        validation = manifest.get("validation", {})
        if not isinstance(validation, dict):
            raise ValueError("Manifest validation must be an object")

        source_findings: dict[str, list[dict[str, Any]]] = {}
        findings = validation.get("findings", [])
        if not isinstance(findings, list):
            raise ValueError("Manifest findings must be a list")
        for finding in findings:
            if not isinstance(finding, dict):
                raise ValueError("Manifest finding must be an object")
            context = finding.get("context", {})
            if not isinstance(context, dict):
                raise ValueError("Manifest finding context must be an object")
            source_id = context.get("source_id")
            if isinstance(source_id, str) and source_id:
                source_findings.setdefault(source_id, []).append(finding)

        sources: list[dict[str, Any]] = []
        for item in raw_sources:
            if not isinstance(item, dict):
                raise ValueError("Manifest source must be an object")
            source_id = self._required_string(item, "source_id")
            sources.append(
                {
                    "source_id": source_id,
                    "relative_path": item.get("relative_path"),
                    "type": item.get("type", "unknown"),
                    "sha256": item.get("sha256"),
                    "size_bytes": item.get("size_bytes", 0),
                    "imported_by": item.get("imported_by", "unknown"),
                    "status": (
                        "attention_required"
                        if source_findings.get(source_id)
                        else "inventoried"
                    ),
                    "findings": source_findings.get(source_id, []),
                }
            )
        sources.sort(key=lambda item: (str(item["type"]), str(item["relative_path"])))

        type_counts = Counter(str(item["type"]) for item in sources)
        module_counts = Counter(str(item["imported_by"]) for item in sources)
        total_size = sum(int(item["size_bytes"]) for item in sources)
        attention_count = sum(item["status"] == "attention_required" for item in sources)
        audit_runs = manifest.get("audit_runs", {})
        if not isinstance(audit_runs, dict):
            raise ValueError("Manifest audit_runs must be an object")
        graph_audits = audit_runs.get("graph", [])
        evidence_audits = audit_runs.get("evidence", [])
        if not isinstance(graph_audits, list) or not isinstance(evidence_audits, list):
            raise ValueError("Manifest audit inventories must be lists")

        return {
            "project_id": project_id,
            "project_version": manifest.get("project_version"),
            "graph_checksum": manifest.get("graph_checksum"),
            "model_versions": {
                "canonical_model": manifest.get("canonical_model_version"),
                "graph_rule_engine": manifest.get("graph_rule_engine_version"),
                "evidence_rules": manifest.get("evidence_rules_version"),
            },
            "sources": sources,
            "facets": {
                "types": dict(sorted(type_counts.items())),
                "import_modules": dict(sorted(module_counts.items())),
            },
            "audit_inventory": {
                "graph": graph_audits,
                "evidence": evidence_audits,
                "total": len(graph_audits) + len(evidence_audits),
            },
            "summary": {
                "sources": len(sources),
                "size_bytes": total_size,
                "known_import_module": sum(item["imported_by"] != "unknown" for item in sources),
                "unknown_import_module": sum(item["imported_by"] == "unknown" for item in sources),
                "attention_required": attention_count,
                "manifest_findings": int(validation.get("finding_count", len(findings))),
            },
            "validation": validation,
            "metadata": {
                "read_only": True,
                "project_files_mutated": False,
                "graph_mutated": False,
                "audit_runs_mutated": False,
                "automatic_import_performed": False,
                "automatic_repair_performed": False,
            },
        }

    @staticmethod
    def _required_string(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing required string: {key}")
        return value
