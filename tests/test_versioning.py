import pytest

from crow_module_conformance import Version, satisfies


def test_semver_range_accepts_supported_backbone() -> None:
    assert satisfies("1.4.2", ">=1.0.0,<2.0.0")


def test_semver_range_rejects_next_major() -> None:
    assert not satisfies("2.0.0", ">=1.0.0,<2.0.0")


def test_invalid_semver_is_rejected() -> None:
    with pytest.raises(ValueError):
        Version.parse("1.0")
