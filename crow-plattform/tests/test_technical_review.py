from datetime import UTC, datetime

import pytest

from crow_decision_engine import DecisionEvaluationResult
from crow_technical_review import (
    ReviewStatus,
    can_approve_decision,
    initialize_review_set,
    transition_record,
)
from crow_technical_validation import (
    TechnicalValidationIssue,
    TechnicalValidationResult,
    ValidationIssueType,
    ValidationSeverity,
)


def validation_issue() -> TechnicalValidationIssue:
    return TechnicalValidationIssue(
        id="validation:1",
        requirement_id="requirement:1",
        issue_type=ValidationIssueType.MISSING_INFORMATION,
        severity=ValidationSeverity.BLOCKING,
        title="Missing area",
        explanation="Area is missing.",
        missing_aliases=("area",),
        related_claim_ids=(),
        document_ids=(),
        recommended_action="Provide area.",
        fingerprint="validation-fingerprint",
    )


def initial_set():
    return initialize_review_set(
        DecisionEvaluationResult(project_id="project", rule_set_id="rules"),
        TechnicalValidationResult(
            project_id="project",
            profile_id="profile",
            issues=(validation_issue(),),
            checked_requirements=1,
        ),
    )


def test_initial_status_is_proposed() -> None:
    review_set = initial_set()

    assert review_set.records[0].status == ReviewStatus.PROPOSED


def test_transition_creates_immutable_event() -> None:
    timestamp = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)

    updated = transition_record(
        initial_set(),
        "validation:1",
        ReviewStatus.NEEDS_INFORMATION,
        "reviewer@example.com",
        "Area must be documented.",
        timestamp,
    )

    record = updated.records[0]
    assert record.status == ReviewStatus.NEEDS_INFORMATION
    assert record.history[0].previous_status == ReviewStatus.PROPOSED
    assert record.history[0].created_at == timestamp


def test_invalid_transition_is_rejected() -> None:
    approved = transition_record(
        initial_set(),
        "validation:1",
        ReviewStatus.APPROVED,
        "reviewer",
        "Verified.",
        datetime(2026, 7, 19, tzinfo=UTC),
    )

    with pytest.raises(ValueError):
        transition_record(
            approved,
            "validation:1",
            ReviewStatus.REJECTED,
            "reviewer",
            "Changed mind.",
        )


def test_reviewer_and_reason_are_required() -> None:
    with pytest.raises(ValueError):
        transition_record(
            initial_set(),
            "validation:1",
            ReviewStatus.APPROVED,
            "",
            "Verified.",
        )


def test_blocking_issue_prevents_approval_gate() -> None:
    review_set = initial_set()
    validation = TechnicalValidationResult(
        project_id="project",
        profile_id="profile",
        issues=(validation_issue(),),
    )

    assert not can_approve_decision(review_set, validation)

    resolved = transition_record(
        review_set,
        "validation:1",
        ReviewStatus.REJECTED,
        "reviewer",
        "Issue was based on obsolete requirement.",
    )
    assert can_approve_decision(resolved, validation)


def test_project_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError):
        initialize_review_set(
            DecisionEvaluationResult(project_id="a", rule_set_id="rules"),
            TechnicalValidationResult(project_id="b", profile_id="profile"),
        )
