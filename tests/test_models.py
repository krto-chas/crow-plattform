from decimal import Decimal

from crow_module_sdk import Claim, Provenance


def test_claim_conflict_key_is_domain_neutral() -> None:
    claim = Claim(
        "claim-1",
        "example",
        "COMPONENT-01",
        "size",
        Decimal("100"),
        "mm",
        Provenance("DRAWING-01", "A", 1),
    )
    assert claim.conflict_key == ("example", "COMPONENT-01", "size")
