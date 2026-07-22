from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

KNOWN_IMPORT_MODULES = {
    ".dxf": "crow_cad_text",
    ".ifc": "crow_ifc_relations",
    ".pdf": "crow_pdf_evidence",
}


@dataclass(frozen=True)
class ManifestFinding:
    code: str
    severity: str
    message: str
    context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "context": self.context,
        }


@dataclass(frozen=True)
class ProjectManifest:
    project_id: str
    project_version: str
    graph_checksum: str | None
    canonical_model_version: str
    graph_rule_engine_version: str
    evidence_rules_version: str
    sources: list[dict[str, Any]]
    graph_audits: list[dict[str, Any]]
    evidence_audits: list[dict[str, Any]]
    findings: list[ManifestFinding]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_version": self.project_version,
            "graph_checksum": self.graph_checksum,
            "canonical_model_version": self.canonical_model_version,
            "graph_rule_engine_version": self.graph_rule_engine_version,
            "evidence_rules_version": self.evidence_rules_version,
            "sources": self.sources,
            "audit_runs": {
                "graph": self.graph_audits,
                "evidence": self.evidence_audits,
            },
            "validation": {
                "valid": not any(item.severity == "error" for item in self.findings),
                "finding_count": len(self.findings),
                "findings": [item.to_dict() for item in self.findings],
            },
            "metadata": {
                "read_only": True,
                "graph_mutated": False,
                "automatic_repair_performed": False,
                "automatic_upgrade_performed": False,
                "project_structure_modified": False,
            },
        }


class ProjectManifestBuilder:
    """Build a deterministic, read-only inventory from persisted project artifacts."""

    def build(
        self,
        *,
        project_id: str,
        project_version: str,
        project_directory: Path,
        upload_directory: Path,
        graph_audits: list[dict[str, Any]],
        evidence_audits: list[dict[str, Any]],
        canonical_model_version: str = "0.1",
        graph_rule_engine_version: str = "0.1.0",
        evidence_rules_version: str = "0.1.0",
    ) -> ProjectManifest:
        normalized_id = project_id.strip()
        if not normalized_id:
            raise ValueError("project_id får inte vara tomt")
        sources = self._sources(upload_directory)
        graph_checksum = self._graph_checksum(project_directory / "building-graph" / "graph.json")
        findings = self._validate(
            sources=sources,
            graph_checksum=graph_checksum,
            graph_audits=graph_audits,
            evidence_audits=evidence_audits,
        )
        return ProjectManifest(
            project_id=normalized_id,
            project_version=project_version,
            graph_checksum=graph_checksum,
            canonical_model_version=canonical_model_version,
            graph_rule_engine_version=graph_rule_engine_version,
            evidence_rules_version=evidence_rules_version,
            sources=sources,
            graph_audits=self._audit_inventory(graph_audits),
            evidence_audits=self._audit_inventory(evidence_audits),
            findings=findings,
        )

    @staticmethod
    def _graph_checksum(path: Path) -> str | None:
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _sources(upload_directory: Path) -> list[dict[str, Any]]:
        if not upload_directory.exists():
            return []
        items: list[dict[str, Any]] = []
        for path in sorted(item for item in upload_directory.rglob("*") if item.is_file()):
            payload = path.read_bytes()
            extension = path.suffix.lower()
            items.append(
                {
                    "source_id": path.name,
                    "relative_path": path.relative_to(upload_directory).as_posix(),
                    "type": extension.removeprefix(".") or "unknown",
                    "sha256": sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                    "imported_by": KNOWN_IMPORT_MODULES.get(extension, "unknown"),
                }
            )
        return items

    @staticmethod
    def _audit_inventory(audits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for audit in audits:
            items.append(
                {
                    "audit_id": audit.get("audit_id"),
                    "graph_checksum": audit.get("graph_checksum"),
                    "created_at": audit.get("created_at"),
                    "finding_count": len(audit.get("findings", []))
                    if isinstance(audit.get("findings", []), list)
                    else None,
                }
            )
        return sorted(items, key=lambda item: str(item.get("created_at", "")), reverse=True)

    @staticmethod
    def _validate(
        *,
        sources: list[dict[str, Any]],
        graph_checksum: str | None,
        graph_audits: list[dict[str, Any]],
        evidence_audits: list[dict[str, Any]],
    ) -> list[ManifestFinding]:
        findings: list[ManifestFinding] = []
        by_source: dict[str, set[str]] = {}
        for source in sources:
            source_id = str(source.get("source_id", ""))
            checksum = str(source.get("sha256", ""))
            by_source.setdefault(source_id, set()).add(checksum)
            if source.get("imported_by") == "unknown":
                findings.append(
                    ManifestFinding(
                        code="MANIFEST-SOURCE-003",
                        severity="warning",
                        message="Källan har ingen känd explicit importmodul",
                        context={"source_id": source_id, "type": source.get("type")},
                    )
                )
        for source_id, checksums in sorted(by_source.items()):
            matching = [item for item in sources if item.get("source_id") == source_id]
            if len(matching) > 1:
                findings.append(
                    ManifestFinding(
                        code="MANIFEST-SOURCE-001",
                        severity="warning",
                        message="Samma source_id förekommer flera gånger",
                        context={"source_id": source_id, "occurrences": len(matching)},
                    )
                )
            if len(checksums) > 1:
                findings.append(
                    ManifestFinding(
                        code="MANIFEST-SOURCE-002",
                        severity="error",
                        message="Samma source_id har motstridiga checksummor",
                        context={"source_id": source_id, "checksums": sorted(checksums)},
                    )
                )
        for domain, audits in (("graph", graph_audits), ("evidence", evidence_audits)):
            for audit in audits:
                audit_checksum = audit.get("graph_checksum")
                if not isinstance(audit_checksum, str) or not audit_checksum:
                    findings.append(
                        ManifestFinding(
                            code="MANIFEST-AUDIT-001",
                            severity="error",
                            message="Audit-körning saknar graph_checksum",
                            context={"domain": domain, "audit_id": audit.get("audit_id")},
                        )
                    )
                elif graph_checksum is not None and audit_checksum != graph_checksum:
                    findings.append(
                        ManifestFinding(
                            code="MANIFEST-AUDIT-002",
                            severity="info",
                            message="Audit-körningen refererar en annan historisk graf-snapshot",
                            context={
                                "domain": domain,
                                "audit_id": audit.get("audit_id"),
                                "audit_graph_checksum": audit_checksum,
                                "current_graph_checksum": graph_checksum,
                            },
                        )
                    )
        return findings
