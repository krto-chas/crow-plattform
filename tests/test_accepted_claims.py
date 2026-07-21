from crow_accepted_claims import AcceptanceBasis, canonicalize_claims
from crow_authority import (
    AuthorityDecision,
    AuthorityDecisionStatus,
    AuthorityResolution,
    ab04_framework,
)
from crow_knowledge_fusion import (
    FusionStatus,
    KnowledgeCluster,
    KnowledgeFusionResult,
    ValueVariant,
)


def make_cluster() -> KnowledgeCluster:
    return KnowledgeCluster(
        id="cluster:airflow",
        semantic_key="key_value|ahu-03|airflow|l/s",
        subject="AHU-03",
        predicate="airflow",
        unit="L/S",
        candidate_ids=("candidate:drawing", "candidate:description"),
        document_ids=("drawing", "description"),
        variants=(
            ValueVariant("320", "L/S", ("candidate:drawing",), ("drawing",), 0.98, 0.98),
            ValueVariant("400", "L/S", ("candidate:description",), ("description",), 0.95, 0.95),
        ),
        status=FusionStatus.CONFLICTING,
        support_count=2,
        fingerprint="cluster-fingerprint",
    )


def decision(status: AuthorityDecisionStatus, value: str | None = "400") -> AuthorityDecision:
    return AuthorityDecision(
        id="decision:1",
        cluster_id="cluster:airflow",
        status=status,
        accepted_value=value,
        accepted_unit="L/S" if value else None,
        accepted_candidate_ids=("candidate:description",) if value else (),
        accepted_document_ids=("description",) if value else (),
        evaluated_variants=(),
        applied_rule="document_hierarchy",
        explanation="Description outranks drawing.",
        framework_id="se.ab04.default",
        trace=("conflict", "description wins"),
    )


def test_resolved_decision_becomes_accepted_claim() -> None:
    fusion = KnowledgeFusionResult("project", (make_cluster(),))
    resolution = AuthorityResolution(
        "project", ab04_framework(), (decision(AuthorityDecisionStatus.RESOLVED_BY_HIERARCHY),)
    )

    result = canonicalize_claims(fusion, resolution)

    assert result.accepted_count == 1
    assert result.pending_count == 0
    assert result.claims[0].value == "400"
    assert result.claims[0].acceptance_basis == AcceptanceBasis.AUTHORITY_HIERARCHY
    assert result.claims[0].confidence == 0.95
    assert result.claims[0].provenance.cluster_id == "cluster:airflow"


def test_unresolved_decision_never_enters_canonical_layer() -> None:
    fusion = KnowledgeFusionResult("project", (make_cluster(),))
    resolution = AuthorityResolution(
        "project",
        ab04_framework(),
        (decision(AuthorityDecisionStatus.UNRESOLVED_TIE, value=None),),
    )

    result = canonicalize_claims(fusion, resolution)

    assert result.accepted_count == 0
    assert result.pending_count == 1
    assert result.pending[0].status == "unresolved_tie"


def test_missing_decision_is_pending() -> None:
    result = canonicalize_claims(
        KnowledgeFusionResult("project", (make_cluster(),)),
        AuthorityResolution("project", ab04_framework(), ()),
    )
    assert result.pending[0].status == "missing_authority_decision"


def test_ids_are_deterministic() -> None:
    fusion = KnowledgeFusionResult("project", (make_cluster(),))
    resolution = AuthorityResolution(
        "project", ab04_framework(), (decision(AuthorityDecisionStatus.RESOLVED_BY_HIERARCHY),)
    )
    assert canonicalize_claims(fusion, resolution) == canonicalize_claims(fusion, resolution)


def test_project_mismatch_is_rejected() -> None:
    fusion = KnowledgeFusionResult("project-a", (make_cluster(),))
    resolution = AuthorityResolution(
        "project-b", ab04_framework(), (decision(AuthorityDecisionStatus.RESOLVED_BY_HIERARCHY),)
    )
    try:
        canonicalize_claims(fusion, resolution)
    except ValueError as error:
        assert "different projects" in str(error)
    else:
        raise AssertionError("Expected ValueError")
