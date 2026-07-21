from decimal import Decimal

from crow_module_sdk import Claim, Evidence, Provenance, validate_evidence_integrity


def test_evidence_integrity_accepts_known_claims() -> None:
    claims = (
        Claim(
            id="claim-1",
            namespace="example",
            subject="COMPONENT-01",
            property="size",
            value=Decimal("125"),
            unit="mm",
            provenance=Provenance("SPEC"),
        ),
    )
    evidence = (
        Evidence(
            id="evidence-1",
            kind="rule",
            statement="Specification governs.",
            source_claim_ids=("claim-1",),
            rule_id="AF-1.3",
        ),
    )

    report = validate_evidence_integrity(claims, evidence)

    assert report.passed


def test_evidence_integrity_rejects_unknown_claim() -> None:
    report = validate_evidence_integrity(
        (),
        (
            Evidence(
                id="evidence-1",
                kind="observation",
                statement="Unknown source.",
                source_claim_ids=("missing",),
            ),
        ),
    )

    assert not report.passed
    assert report.issues[0].code == "EVI-002"
