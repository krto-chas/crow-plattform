from __future__ import annotations

from pathlib import Path

import pytest

from crow_deployment.modules import build_module_install_plan, find_repository_root
from crow_deployment.runtime import platform_config_root, platform_data_root
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


def test_platform_data_root_can_be_configured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("CROW_PLATFORM_DATA_ROOT", str(data_root))

    assert platform_data_root() == data_root


def test_platform_config_root_defaults_under_data_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data_root = tmp_path / "data"
    monkeypatch.setenv("CROW_PLATFORM_DATA_ROOT", str(data_root))
    monkeypatch.delenv("CROW_PLATFORM_CONFIG_ROOT", raising=False)

    assert platform_config_root() == data_root / "config"


def test_platform_config_root_can_be_separated_from_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data_root = tmp_path / "data"
    config_root = tmp_path / "config"
    monkeypatch.setenv("CROW_PLATFORM_DATA_ROOT", str(data_root))
    monkeypatch.setenv("CROW_PLATFORM_CONFIG_ROOT", str(config_root))

    assert platform_data_root() == data_root
    assert platform_config_root() == config_root
