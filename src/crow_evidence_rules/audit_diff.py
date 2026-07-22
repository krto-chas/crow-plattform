from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceAuditFindingChange:
    finding_id: str
    lifecycle: str
    previous: dict[str, Any] | None
    current: dict[str, Any] | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceAuditDiffResult:
    base_audit_id: str
    target_audit_id: str
    changes: tuple[EvidenceAuditFindingChange, ...]
    summary: dict[str, int]
    metadata: dict[str, Any] = field(default_factory=dict)


class EvidenceAuditDiffer:
    """Compare immutable evidence audit runs without changing audit or graph state."""

    def compare(
        self,
        base: dict[str, Any],
        target: dict[str, Any],
    ) -> EvidenceAuditDiffResult:
        base_id = str(base.get("audit_id", ""))
        target_id = str(target.get("audit_id", ""))
        if not base_id or not target_id:
            raise ValueError("Båda evidensgranskningarna måste ha audit_id")
        if base_id == target_id:
            raise ValueError("Samma evidensgranskning kan inte jämföras med sig själv")

        base_findings = self._index_findings(base)
        target_findings = self._index_findings(target)
        changes: list[EvidenceAuditFindingChange] = []

        for finding_id in sorted(set(base_findings) | set(target_findings)):
            previous = base_findings.get(finding_id)
            current = target_findings.get(finding_id)
            if previous is None:
                lifecycle = "new"
            elif current is None:
                lifecycle = "no_longer_detected"
            else:
                lifecycle = "persistent"

            metadata: dict[str, Any] = {
                "automatic_resolution_asserted": False,
                "graph_mutated": False,
                "evidence_mutated": False,
            }
            if lifecycle == "no_longer_detected":
                metadata["resolution_status"] = "candidate_for_verification"

            changes.append(
                EvidenceAuditFindingChange(
                    finding_id=finding_id,
                    lifecycle=lifecycle,
                    previous=previous,
                    current=current,
                    metadata=metadata,
                )
            )

        summary = {
            "total": len(changes),
            "new": sum(item.lifecycle == "new" for item in changes),
            "persistent": sum(item.lifecycle == "persistent" for item in changes),
            "no_longer_detected": sum(
                item.lifecycle == "no_longer_detected" for item in changes
            ),
        }
        return EvidenceAuditDiffResult(
            base_audit_id=base_id,
            target_audit_id=target_id,
            changes=tuple(changes),
            summary=summary,
            metadata={
                "comparison_only": True,
                "automatic_resolution_performed": False,
                "audit_runs_mutated": False,
                "graph_mutated": False,
                "evidence_mutated": False,
            },
        )

    @staticmethod
    def _index_findings(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
        findings = audit.get("findings", [])
        if not isinstance(findings, list):
            raise ValueError("Ogiltig findings-lista i evidensgranskning")
        indexed: dict[str, dict[str, Any]] = {}
        for finding in findings:
            if not isinstance(finding, dict) or not finding.get("finding_id"):
                raise ValueError("Varje evidence finding måste ha finding_id")
            finding_id = str(finding["finding_id"])
            if finding_id in indexed:
                raise ValueError(f"Duplicerat finding_id: {finding_id}")
            indexed[finding_id] = finding
        return indexed
