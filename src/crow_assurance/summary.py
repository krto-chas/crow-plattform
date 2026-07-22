from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssuranceDomainSummary:
    domain: str
    audit_id: str | None
    graph_checksum: str | None
    created_at: str | None
    finding_count: int
    reviewed_count: int
    unreviewed_count: int
    verified_resolution_count: int
    status: str
    severity_counts: dict[str, int]
    category_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "audit_id": self.audit_id,
            "graph_checksum": self.graph_checksum,
            "created_at": self.created_at,
            "finding_count": self.finding_count,
            "reviewed_count": self.reviewed_count,
            "unreviewed_count": self.unreviewed_count,
            "verified_resolution_count": self.verified_resolution_count,
            "status": self.status,
            "severity_counts": self.severity_counts,
            "category_counts": self.category_counts,
        }


@dataclass(frozen=True)
class ProjectAssuranceSummary:
    project_id: str
    graph: AssuranceDomainSummary
    evidence: AssuranceDomainSummary
    status: str
    metadata: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "status": self.status,
            "domains": {
                "graph": self.graph.to_dict(),
                "evidence": self.evidence.to_dict(),
            },
            "totals": {
                "findings": self.graph.finding_count + self.evidence.finding_count,
                "reviewed": self.graph.reviewed_count + self.evidence.reviewed_count,
                "unreviewed": self.graph.unreviewed_count + self.evidence.unreviewed_count,
                "verified_resolutions": (
                    self.graph.verified_resolution_count
                    + self.evidence.verified_resolution_count
                ),
            },
            "metadata": self.metadata,
        }


class ProjectAssuranceSummaryBuilder:
    """Builds a read-only operational summary from immutable audit records."""

    def build(
        self,
        *,
        project_id: str,
        graph_audits: Sequence[Mapping[str, Any]],
        evidence_audits: Sequence[Mapping[str, Any]],
        graph_reviews: Sequence[Mapping[str, Any]] = (),
        evidence_reviews: Sequence[Mapping[str, Any]] = (),
        graph_verifications: Sequence[Mapping[str, Any]] = (),
        evidence_verifications: Sequence[Mapping[str, Any]] = (),
    ) -> ProjectAssuranceSummary:
        normalized_project_id = project_id.strip()
        if not normalized_project_id:
            raise ValueError("project_id får inte vara tomt")

        graph = self._domain(
            "graph",
            self._latest(graph_audits),
            graph_reviews,
            graph_verifications,
        )
        evidence = self._domain(
            "evidence",
            self._latest(evidence_audits),
            evidence_reviews,
            evidence_verifications,
        )
        statuses = {graph.status, evidence.status}
        if "attention_required" in statuses:
            status = "attention_required"
        elif "review_in_progress" in statuses:
            status = "review_in_progress"
        elif "no_persisted_audit" in statuses:
            status = "incomplete_audit_coverage"
        else:
            status = "no_findings_detected"

        return ProjectAssuranceSummary(
            project_id=normalized_project_id,
            graph=graph,
            evidence=evidence,
            status=status,
            metadata={
                "read_only": True,
                "audit_runs_mutated": False,
                "graph_mutated": False,
                "evidence_mutated": False,
                "automatic_resolution_performed": False,
                "technical_correctness_asserted": False,
            },
        )

    @staticmethod
    def _latest(audits: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
        if not audits:
            return None
        return max(audits, key=lambda item: str(item.get("created_at", "")))

    def _domain(
        self,
        domain: str,
        audit: Mapping[str, Any] | None,
        reviews: Sequence[Mapping[str, Any]],
        verifications: Sequence[Mapping[str, Any]],
    ) -> AssuranceDomainSummary:
        if audit is None:
            return AssuranceDomainSummary(
                domain=domain,
                audit_id=None,
                graph_checksum=None,
                created_at=None,
                finding_count=0,
                reviewed_count=0,
                unreviewed_count=0,
                verified_resolution_count=0,
                status="no_persisted_audit",
                severity_counts={},
                category_counts={},
            )

        audit_id = self._required_string(audit, "audit_id")
        findings_raw = audit.get("findings", [])
        if not isinstance(findings_raw, list):
            raise ValueError(f"{domain}-audit har ogiltig findings-lista")
        findings: list[Mapping[str, Any]] = []
        finding_ids: set[str] = set()
        for item in findings_raw:
            if not isinstance(item, Mapping):
                raise ValueError(f"{domain}-audit innehåller ogiltig finding")
            finding_id = self._required_string(item, "finding_id")
            if finding_id in finding_ids:
                raise ValueError(f"{domain}-audit innehåller dubblerat finding_id")
            finding_ids.add(finding_id)
            findings.append(item)

        reviewed_ids = {
            str(item.get("finding_id"))
            for item in reviews
            if item.get("audit_id") == audit_id and item.get("finding_id") in finding_ids
        }
        verified_count = sum(
            1
            for item in verifications
            if item.get("target_audit_id") == audit_id
            and item.get("decision") == "verify_resolved"
        )
        unreviewed_count = len(findings) - len(reviewed_ids)
        if not findings:
            status = "no_findings_detected"
        elif unreviewed_count > 0:
            status = "attention_required"
        else:
            status = "review_in_progress"

        return AssuranceDomainSummary(
            domain=domain,
            audit_id=audit_id,
            graph_checksum=self._optional_string(audit.get("graph_checksum")),
            created_at=self._optional_string(audit.get("created_at")),
            finding_count=len(findings),
            reviewed_count=len(reviewed_ids),
            unreviewed_count=unreviewed_count,
            verified_resolution_count=verified_count,
            status=status,
            severity_counts=self._counts(findings, "severity"),
            category_counts=self._counts(findings, "category"),
        )

    @staticmethod
    def _counts(items: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            value = item.get(field)
            if isinstance(value, str) and value:
                counts[value] = counts.get(value, 0) + 1
        return dict(sorted(counts.items()))

    @staticmethod
    def _required_string(item: Mapping[str, Any], field: str) -> str:
        value = item.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} måste vara en icke-tom sträng")
        return value

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return value if isinstance(value, str) and value else None
