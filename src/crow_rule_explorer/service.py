from __future__ import annotations

from collections import Counter
from typing import Any


class RuleExplorerBuilder:
    """Build a read-only rule-to-audit-to-finding projection."""

    def build(
        self,
        *,
        rules: list[dict[str, Any]],
        graph_audits: list[dict[str, Any]],
        evidence_audits: list[dict[str, Any]],
        graph_reviews: list[dict[str, Any]],
        evidence_reviews: list[dict[str, Any]],
        graph_verifications: list[dict[str, Any]],
        evidence_verifications: list[dict[str, Any]],
    ) -> dict[str, Any]:
        review_index = self._review_index(graph_reviews + evidence_reviews)
        verification_index = Counter(
            self._required_string(item, "finding_id")
            for item in graph_verifications + evidence_verifications
        )
        rule_index: dict[str, dict[str, Any]] = {}
        for raw in rules:
            rule_id = self._required_string(raw, "rule_id")
            if rule_id in rule_index:
                raise ValueError(f"Duplicate installed rule: {rule_id}")
            rule_index[rule_id] = {
                **raw,
                "executions": 0,
                "findings": 0,
                "reviewed": 0,
                "verified_resolutions": 0,
                "latest_run": None,
                "latest_finding": None,
                "runs": [],
            }

        for domain, audits in (("graph", graph_audits), ("evidence", evidence_audits)):
            for audit in audits:
                audit_id = self._required_string(audit, "audit_id")
                created_at = audit.get("created_at")
                findings = audit.get("findings", [])
                if not isinstance(findings, list):
                    raise ValueError(f"Audit findings must be a list: {audit_id}")
                seen_rules: set[str] = set()
                by_rule: dict[str, list[dict[str, Any]]] = {}
                for finding in findings:
                    if not isinstance(finding, dict):
                        raise ValueError(f"Audit finding must be an object: {audit_id}")
                    rule_id = self._required_string(finding, "rule_id")
                    finding_id = self._required_string(finding, "finding_id")
                    if rule_id not in rule_index:
                        rule_index[rule_id] = self._unknown_rule(rule_id, finding)
                    review = review_index.get((audit_id, finding_id))
                    item = {
                        **finding,
                        "audit_id": audit_id,
                        "domain": domain,
                        "created_at": created_at,
                        "review": review,
                        "review_status": "reviewed" if review else "unreviewed",
                        "verified_resolution_count": verification_index.get(finding_id, 0),
                    }
                    by_rule.setdefault(rule_id, []).append(item)
                    seen_rules.add(rule_id)
                    record = rule_index[rule_id]
                    record["findings"] += 1
                    record["reviewed"] += 1 if review else 0
                    record["verified_resolutions"] += verification_index.get(finding_id, 0)
                    if record["latest_finding"] is None or str(created_at or "") >= str(
                        record["latest_finding"].get("created_at", "")
                    ):
                        record["latest_finding"] = item
                for rule_id in seen_rules:
                    record = rule_index[rule_id]
                    record["executions"] += 1
                    run = {
                        "audit_id": audit_id,
                        "domain": domain,
                        "created_at": created_at,
                        "graph_checksum": audit.get("graph_checksum"),
                        "findings": sorted(
                            by_rule[rule_id], key=lambda item: str(item["finding_id"])
                        ),
                    }
                    record["runs"].append(run)
                    if record["latest_run"] is None or str(created_at or "") >= str(
                        record["latest_run"].get("created_at", "")
                    ):
                        record["latest_run"] = run

        items = sorted(rule_index.values(), key=lambda item: str(item["rule_id"]))
        for item in items:
            item["runs"].sort(key=lambda run: str(run.get("created_at", "")), reverse=True)
        disciplines = Counter(str(item.get("discipline", "GENERAL")) for item in items)
        severities = Counter(str(item.get("severity", "unknown")) for item in items)
        return {
            "items": items,
            "summary": {
                "rules": len(items),
                "active_rules": sum(1 for item in items if item.get("enabled", True)),
                "inactive_rules": sum(1 for item in items if not item.get("enabled", True)),
                "executions": sum(int(item["executions"]) for item in items),
                "findings": sum(int(item["findings"]) for item in items),
                "reviewed": sum(int(item["reviewed"]) for item in items),
                "verified_resolutions": sum(
                    int(item["verified_resolutions"]) for item in items
                ),
                "discipline_counts": dict(sorted(disciplines.items())),
                "severity_counts": dict(sorted(severities.items())),
            },
            "metadata": {
                "read_only": True,
                "graph_mutated": False,
                "rule_configuration_mutated": False,
                "audit_mutated": False,
                "automatic_rule_execution": False,
                "inference_performed": False,
            },
        }

    @staticmethod
    def _unknown_rule(rule_id: str, finding: dict[str, Any]) -> dict[str, Any]:
        return {
            "rule_id": rule_id,
            "title": rule_id,
            "description": "Rule metadata was not available in the installed registry.",
            "discipline": "GENERAL",
            "version": str(finding.get("rule_version", "unknown")),
            "severity": str(finding.get("severity", "unknown")),
            "enabled": False,
            "evidence_required": False,
            "supports_auto_inference": False,
            "tags": [],
            "executions": 0,
            "findings": 0,
            "reviewed": 0,
            "verified_resolutions": 0,
            "latest_run": None,
            "latest_finding": None,
            "runs": [],
        }

    @staticmethod
    def _review_index(reviews: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
        result: dict[tuple[str, str], dict[str, Any]] = {}
        for review in reviews:
            if not isinstance(review, dict):
                raise ValueError("Audit review must be an object")
            key = (
                RuleExplorerBuilder._required_string(review, "audit_id"),
                RuleExplorerBuilder._required_string(review, "finding_id"),
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
