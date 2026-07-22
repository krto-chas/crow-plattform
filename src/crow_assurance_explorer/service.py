from __future__ import annotations

from typing import Any


class AssuranceExplorerBuilder:
    """Build a read-only operational assurance projection from a summary and audits."""

    def build(
        self,
        *,
        assurance_summary: dict[str, Any],
        graph_audits: list[dict[str, Any]],
        evidence_audits: list[dict[str, Any]],
        graph_reviews: list[dict[str, Any]],
        evidence_reviews: list[dict[str, Any]],
    ) -> dict[str, Any]:
        review_index = self._review_index(graph_reviews + evidence_reviews)
        domains = assurance_summary.get("domains")
        if not isinstance(domains, dict):
            raise ValueError("Assurance summary must contain domains")

        actions: list[dict[str, Any]] = []
        for domain, audits in (("graph", graph_audits), ("evidence", evidence_audits)):
            domain_summary = domains.get(domain)
            if not isinstance(domain_summary, dict):
                raise ValueError(f"Missing assurance domain: {domain}")
            audit_id = domain_summary.get("audit_id")
            if not isinstance(audit_id, str) or not audit_id:
                continue
            audit = next((item for item in audits if item.get("audit_id") == audit_id), None)
            if audit is None:
                raise ValueError(f"Latest assurance audit not found: {audit_id}")
            findings = audit.get("findings", [])
            if not isinstance(findings, list):
                raise ValueError(f"Audit findings must be a list: {audit_id}")
            for finding in findings:
                if not isinstance(finding, dict):
                    raise ValueError(f"Audit finding must be an object: {audit_id}")
                finding_id = self._required_string(finding, "finding_id")
                review = review_index.get((audit_id, finding_id))
                if review is not None:
                    continue
                actions.append(
                    {
                        "domain": domain,
                        "audit_id": audit_id,
                        "finding_id": finding_id,
                        "rule_id": finding.get("rule_id"),
                        "title": finding.get("title") or finding.get("message") or finding_id,
                        "severity": finding.get("severity", "unknown"),
                        "category": finding.get("category", "unknown"),
                        "created_at": audit.get("created_at"),
                        "action": "human_review_required",
                    }
                )

        severity_order = {"error": 0, "critical": 0, "warning": 1, "info": 2}
        actions.sort(
            key=lambda item: (
                severity_order.get(str(item.get("severity", "unknown")).lower(), 9),
                str(item.get("domain", "")),
                str(item.get("finding_id", "")),
            )
        )
        totals = assurance_summary.get("totals", {})
        if not isinstance(totals, dict):
            raise ValueError("Assurance summary totals must be an object")
        coverage = {
            "graph_audit_available": bool(domains["graph"].get("audit_id")),
            "evidence_audit_available": bool(domains["evidence"].get("audit_id")),
        }
        coverage["complete"] = all(coverage.values())
        return {
            "status": assurance_summary.get("status", "unknown"),
            "domains": domains,
            "totals": totals,
            "coverage": coverage,
            "action_queue": actions,
            "summary": {
                "findings": int(totals.get("findings", 0)),
                "reviewed": int(totals.get("reviewed", 0)),
                "unreviewed": int(totals.get("unreviewed", 0)),
                "verified_resolutions": int(totals.get("verified_resolutions", 0)),
                "actions": len(actions),
            },
            "metadata": {
                "read_only": True,
                "audit_runs_mutated": False,
                "reviews_mutated": False,
                "graph_mutated": False,
                "evidence_mutated": False,
                "automatic_approval_performed": False,
                "technical_correctness_asserted": False,
            },
        }

    @staticmethod
    def _review_index(reviews: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
        result: dict[tuple[str, str], dict[str, Any]] = {}
        for review in reviews:
            if not isinstance(review, dict):
                raise ValueError("Audit review must be an object")
            key = (
                AssuranceExplorerBuilder._required_string(review, "audit_id"),
                AssuranceExplorerBuilder._required_string(review, "finding_id"),
            )
            if key in result:
                raise ValueError(f"Duplicate audit review: {key[0]}/{key[1]}")
            result[key] = review
        return result

    @staticmethod
    def _required_string(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"Missing required string: {key}")
        return value
