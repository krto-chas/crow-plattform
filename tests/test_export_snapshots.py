from decimal import Decimal
from pathlib import Path

from crow_module_conformance import assert_snapshot
from crow_module_sdk import (
    AuthorityPolicy,
    AuthorityRule,
    Claim,
    Provenance,
    RoundingPolicy,
)
from crow_module_sdk.pipeline import run_claim_to_estimate

SNAPSHOT = Path(__file__).parent / "snapshots" / "claim_to_estimate_exports.json"


def test_claim_to_estimate_exports_match_committed_snapshot() -> None:
    claims = (
        Claim(
            id="drawing-size",
            namespace="example",
            subject="COMPONENT-01",
            property="size",
            value=Decimal("160"),
            unit="mm",
            provenance=Provenance("DRAWING", "B", 4, "Section A-A"),
        ),
        Claim(
            id="spec-size",
            namespace="example",
            subject="COMPONENT-01",
            property="size",
            value=Decimal("125"),
            unit="mm",
            provenance=Provenance("SPEC", "B", 7, "3.2"),
        ),
    )
    policy = AuthorityPolicy(
        id="authority-2026",
        confirmed=True,
        rules=(
            AuthorityRule(
                "AF-1.3",
                "SPEC",
                "DRAWING",
                "Beskrivning gäller före ritning.",
            ),
        ),
    )
    result = run_claim_to_estimate(
        claims,
        policy,
        Decimal("500"),
        Decimal("684.20"),
        Decimal("100"),
        RoundingPolicy(),
    )

    exports = {
        "estimate_line": result.estimate_line,
        "client_question": result.client_question,
        "reservation": result.reservation,
    }
    assert_snapshot(exports, SNAPSHOT)
