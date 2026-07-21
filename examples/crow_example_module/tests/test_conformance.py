from decimal import Decimal

from crow_example_module.plugin import ExamplePlugin

from crow_module_conformance import validate_plugin
from crow_module_sdk import Claim, Provenance


def test_example_module_is_conformant() -> None:
    report = validate_plugin(ExamplePlugin())
    assert report.passed, report.issues


def test_example_claim_requires_provenance_and_decimal() -> None:
    claim = Claim(
        "claim-1",
        "example",
        "COMPONENT-01",
        "size",
        Decimal("125"),
        "mm",
        Provenance("SPEC-01", "B", 7, "Section 3.2"),
    )
    result = ExamplePlugin().validate_claim(claim)
    assert result.valid
