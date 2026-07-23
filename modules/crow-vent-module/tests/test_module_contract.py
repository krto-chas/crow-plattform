from decimal import Decimal

from crow_vent_module import CrowVentModulePlugin

from crow_module_conformance import validate_plugin
from crow_module_sdk.models import Claim, Provenance


def make_claim(subject: str, prop: str, value: object, unit: str | None) -> Claim:
    return Claim(
        id="claim-1",
        namespace="vent",
        subject=subject,
        property=prop,
        value=value,
        unit=unit,
        provenance=Provenance("K-57-1-001", "A", 1, "plan 1"),
    )


def test_vent_module_is_conformant() -> None:
    report = validate_plugin(CrowVentModulePlugin())
    assert report.passed, report.issues


def test_length_claim_with_known_duct_string_passes_cleanly() -> None:
    result = CrowVentModulePlugin().validate_claim(
        make_claim("T-125", "length", Decimal("118.0"), "m")
    )
    assert result.valid
    assert result.warnings == ()


def test_unknown_designation_warns_but_passes() -> None:
    result = CrowVentModulePlugin().validate_claim(
        make_claim("XYZ99", "count", Decimal("24"), "st")
    )
    assert result.valid
    assert result.warnings


def test_wrong_unit_and_non_integral_count_are_rejected() -> None:
    plugin = CrowVentModulePlugin()
    assert not plugin.validate_claim(make_claim("T-125", "length", Decimal("118"), "mm")).valid
    assert not plugin.validate_claim(make_claim("TD1", "count", Decimal("24.5"), "st")).valid
