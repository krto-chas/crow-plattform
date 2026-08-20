from __future__ import annotations

import pytest

from crow_graph_rules import (
    GraphAuditDiffer,
    GraphAuditProfile,
    GraphResolutionVerificationService,
)


def test_graph_audit_profile_validates_identity_fields() -> None:
    profile = GraphAuditProfile(
        profile_id="crow.example.audit",
        audit_prefix="example",
        ruleset_version="1.2.3",
        rules=(),
        summary_categories=("data_quality",),
        metadata={"source": "module"},
    )

    assert profile.audit_prefix == "example"
    assert profile.rules == ()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"profile_id": ""}, "profile_id"),
        ({"audit_prefix": "bad:prefix"}, "audit_prefix"),
        ({"ruleset_version": ""}, "ruleset_version"),
    ],
)
def test_graph_audit_profile_rejects_invalid_identity_fields(
    kwargs: dict[str, str], message: str
) -> None:
    values = {
        "profile_id": "crow.example.audit",
        "audit_prefix": "example",
        "ruleset_version": "1.0.0",
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=message):
        GraphAuditProfile(rules=(), **values)


def test_graph_audit_differ_tracks_full_finding_lifecycle_without_mutation() -> None:
    base = {
        "audit_id": "example:audit:base",
        "findings": [
            {"finding_id": "persistent", "status": "review_required"},
            {"finding_id": "resolved-candidate", "status": "review_required"},
        ],
    }
    target = {
        "audit_id": "example:audit:target",
        "findings": [
            {"finding_id": "persistent", "status": "review_required"},
            {"finding_id": "new", "status": "review_required"},
        ],
    }
    reviews = [
        {
            "audit_id": "example:audit:base",
            "finding_id": "resolved-candidate",
            "review_id": "review:1",
            "decision": "acknowledge",
            "reviewer": "reviewer@example.test",
            "decided_at": "2026-08-20T18:00:00+00:00",
        }
    ]

    result = GraphAuditDiffer().compare(base, target, reviews=reviews)

    assert result.summary == {
        "total": 3,
        "new": 1,
        "persistent": 1,
        "no_longer_detected": 1,
    }
    by_id = {item.finding_id: item for item in result.changes}
    assert by_id["new"].lifecycle == "new"
    assert by_id["persistent"].lifecycle == "persistent"
    resolved = by_id["resolved-candidate"]
    assert resolved.lifecycle == "no_longer_detected"
    assert resolved.metadata["resolution_status"] == "candidate_for_verification"
    assert resolved.metadata["base_review"]["review_id"] == "review:1"
    assert result.metadata["comparison_only"] is True
    assert result.metadata["automatic_resolution_performed"] is False
    assert base["findings"][1]["status"] == "review_required"


def test_graph_audit_differ_rejects_duplicate_finding_ids() -> None:
    duplicate = {
        "audit_id": "example:audit:base",
        "findings": [{"finding_id": "f1"}, {"finding_id": "f1"}],
    }

    with pytest.raises(ValueError, match="Duplicerat finding_id"):
        GraphAuditDiffer().compare(
            duplicate,
            {"audit_id": "example:audit:target", "findings": []},
        )


def test_resolution_verification_preserves_namespace_and_human_boundary() -> None:
    previous = {"finding_id": "f1", "rule_id": "EXAMPLE-001"}

    result = GraphResolutionVerificationService(namespace="example").decide(
        base_audit_id="example:audit:base",
        target_audit_id="example:audit:target",
        finding_id="f1",
        lifecycle="no_longer_detected",
        previous_finding=previous,
        decision="verify_resolved",
        reviewer="reviewer@example.test",
        rationale="Verifierad mot explicit evidens.",
        decided_at="2026-08-20T18:30:00+00:00",
    )

    assert result.verification_id.startswith("example:resolution-verification:")
    assert result.previous_finding == previous
    assert result.metadata == {
        "human_verification": True,
        "automatic_resolution_performed": False,
        "audit_runs_mutated": False,
        "graph_mutated": False,
    }


def test_resolution_verification_rejects_non_candidate_lifecycle() -> None:
    with pytest.raises(ValueError, match="inte längre upptäcks"):
        GraphResolutionVerificationService().decide(
            base_audit_id="graph:audit:base",
            target_audit_id="graph:audit:target",
            finding_id="f1",
            lifecycle="persistent",
            previous_finding={"finding_id": "f1"},
            decision="verify_resolved",
            reviewer="reviewer@example.test",
            rationale="Inte en upplösningskandidat.",
        )
