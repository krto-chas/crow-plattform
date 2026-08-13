from __future__ import annotations

from pathlib import Path

import pytest

from crow_deployment.modules import build_module_install_plan, find_repository_root
from crow_workbench.__main__ import _port_from_environment

ROOT = Path(__file__).resolve().parents[1]


def test_first_party_install_plan_comes_from_layout_manifest() -> None:
    plan = build_module_install_plan(ROOT)

    assert set(plan.module_ids) == {"crow.ovk", "crow.provtryckning", "crow.vent"}
    assert plan.module_ids.index("crow.vent") < plan.module_ids.index("crow.provtryckning")
    assert all((path / "pyproject.toml").is_file() for path in plan.repository_roots)


def test_repository_root_is_discovered_from_nested_directory() -> None:
    nested = ROOT / "src" / "crow_workbench"

    assert find_repository_root(nested) == ROOT


def test_workbench_port_defaults_to_8080(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CROW_PLATFORM_PORT", raising=False)

    assert _port_from_environment() == 8080


def test_workbench_port_can_be_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROW_PLATFORM_PORT", "18080")

    assert _port_from_environment() == 18080


def test_workbench_port_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CROW_PLATFORM_PORT", "invalid")

    with pytest.raises(ValueError, match="must be an integer"):
        _port_from_environment()
