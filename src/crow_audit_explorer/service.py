from __future__ import annotations

from collections import Counter
from typing import Any


class AuditExplorerBuilder:
    """Build a read-only projection of persisted graph and evidence audits."""

    def build(
        self,
        *,
        graph_audits: list[dict[str, Any]],
        evidence_audits: list[dict[str, Any]],
        graph_reviews: list[dict[str, Any]],
        evidence_reviews: list[dict[str, Any]],
        graph_verifications: list[dict[str, Any]],
        evidence_verifications: list[dict[str, Any]],
    ) -> dict[str, Any]:
        graph = self._domain(
            "graph", graph_audits, graph_reviews, graph_verifications
        )
        evidence = self._domain(
            "evidence", evidence_audits, evidence_reviews, evidence_verifications
        )
        all_runs = graph["runs"] + evidence["runs"]
        all_findings = [finding for run in all_runs for finding in run["findings"]]
        severity = Counter(str(item.get("severity", "unknown")) for item in all_findings)
        lifecycle = Counter(str(item.get("review_status", "unreviewed")) for item in all_findings)
        return {
            "domains": {"graph": graph, "evidence": evidence},
            "runs": sorted(
                all_runs,
                key=lambda item: str(item.get("created_at", "")),
                reverse=True,
            ),
            "summary": {
                "audit_runs": len(all_runs),
                "graph_audit_runs": len(graph["runs"]),
                "evidence_audit_runs": len(evidence["runs"]),
                "findings": len(all_findings),
                "reviewed_findings": lifecycle["reviewed"],
                "unreviewed_findings": lifecycle["unreviewed"],
                "verified_resolutions": (
                    graph["verified_resolution_count"]
                    + evidence["verified_resolution_count"]
                ),
                "severity_counts": dict(sorted(severity.items())),
            },
            "metadata": {
                "read_only": True,
                "audit_runs_mutated": False,
                "reviews_mutated": False,
                "verifications_mutated": False,
                "graph_mutated": False,
                "evidence_mutated": False,
                "technical_correctness_asserted": False,
            },
        }

    def _domain(
        self,
        domain: str,
        audits: list[dict[str, Any]],
        reviews: list[dict[str, Any]],
        verifications: list[dict[str, Any]],
    ) -> dict[str, Any]:
        review_index = self._review_index(reviews)
        verification_index = self._verification_index(verifications)
        runs: list[dict[str, Any]] = []
        for audit in audits:
            audit_id = self._required_string(audit, "audit_id")
            findings_value = audit.get("findings", [])
            if not isinstance(findings_value, list):
                raise ValueError(f"Audit findings must be a list: {audit_id}")
            findings: list[dict[str, Any]] = []
            for raw in findings_value:
                if not isinstance(raw, dict):
                    raise ValueError(f"Audit finding must be an object: {audit_id}")
                finding_id = self._required_string(raw, "finding_id")
                review = review_index.get((audit_id, finding_id))
                findings.append(
                    {
                        **raw,
                        "review_status": "reviewed" if review else "unreviewed",
                        "review": review,
                        "verified_resolution_count": verification_index.get(finding_id, 0),
                    }
                )
            runs.append(
                {
                    "domain": domain,
                    "audit_id": audit_id,
                    "created_at": audit.get("created_at"),
                    "graph_checksum": audit.get("graph_checksum"),
                    "rule_version": self._rule_version(audit),
                    "summary": audit.get("summary", {}),
                    "finding_count": len(findings),
                    "reviewed_count": sum(
                        1 for item in findings if item["review_status"] == "reviewed"
                    ),
                    "unreviewed_count": sum(
                        1 for item in findings if item["review_status"] == "unreviewed"
                    ),
                    "findings": sorted(
                        findings,
                        key=lambda item: (
                            str(item.get("severity", "")),
                            str(item.get("rule_id", "")),
                            str(item.get("finding_id", "")),
                        ),
                    ),
                }
            )
        runs.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return {
            "domain": domain,
            "runs": runs,
            "run_count": len(runs),
            "finding_count": sum(item["finding_count"] for item in runs),
            "reviewed_count": sum(item["reviewed_count"] for item in runs),
            "unreviewed_count": sum(item["unreviewed_count"] for item in runs),
            "verified_resolution_count": len(verifications),
        }

    @staticmethod
    def _review_index(
        reviews: list[dict[str, Any]],
    ) -> dict[tuple[str, str], dict[str, Any]]:
        result: dict[tuple[str, str], dict[str, Any]] = {}
        for review in reviews:
            if not isinstance(review, dict):
                raise ValueError("Audit review must be an object")
            audit_id = AuditExplorerBuilder._required_string(review, "audit_id")
            finding_id = AuditExplorerBuilder._required_string(review, "finding_id")
            key = (audit_id, finding_id)
            if key in result:
                raise ValueError(f"Duplicate audit review: {audit_id}/{finding_id}")
            result[key] = review
        return result

    @staticmethod
    def _verification_index(verifications: list[dict[str, Any]]) -> dict[str, int]:
        result: Counter[str] = Counter()
        for verification in verifications:
            if not isinstance(verification, dict):
                raise ValueError("Audit verification must be an object")
            finding_id = AuditExplorerBuilder._required_string(
                verification, "finding_id"
            )
            result[finding_id] += 1
        return dict(result)

    @staticmethod
    def _rule_version(audit: dict[str, Any]) -> str | None:
        metadata = audit.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("Audit metadata must be an object")
        value = metadata.get("rule_version", metadata.get("ruleset_version"))
        return str(value) if value is not None else None

    @staticmethod
    def _required_string(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"Missing required string: {key}")
        return value
