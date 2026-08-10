from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_TESTS = ROOT / "tests"
MODULE_TESTS = ROOT / "modules" / "crow-ovk-module" / "tests"
OVK_OWNED_IMPORT_ROOTS = {
    "crow_ovk",
    "crow_ovk_field",
    "crow_ovk_workflow",
    "crow_ovk_import",
    "crow_ovk_intyg",
    "crow_ovk_pricing",
    "crow_ovk_legacy",
    "crow_ovk_reporting",
    "crow_ovk_module",
}
OVK_OWNED_TESTS = {
    "test_ovk_domain.py",
    "test_ovk_field.py",
    "test_ovk_field_history.py",
    "test_ovk_field_media.py",
    "test_ovk_field_surface.py",
    "test_ovk_field_workbench.py",
    "test_ovk_import.py",
    "test_ovk_intyg.py",
    "test_ovk_legacy.py",
    "test_ovk_legacy_commit.py",
    "test_ovk_module_ownership.py",
    "test_ovk_pricing.py",
    "test_ovk_reporting.py",
    "test_ovk_surface.py",
    "test_ovk_time_capture.py",
    "test_ovk_web_ownership.py",
    "test_ovk_workflow.py",
}


def _imports_ovk_owned_package(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".", 1)[0] in OVK_OWNED_IMPORT_ROOTS:
                    return True
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".", 1)[0] in OVK_OWNED_IMPORT_ROOTS:
                return True
    return False


def test_declared_ovk_tests_live_only_in_module() -> None:
    missing = sorted(name for name in OVK_OWNED_TESTS if not (MODULE_TESTS / name).is_file())
    leaked = sorted(name for name in OVK_OWNED_TESTS if (ROOT_TESTS / name).exists())
    assert missing == [], "Declared OVK tests missing from module:\n" + "\n".join(missing)
    assert leaked == [], "OVK-owned tests leaked back to root:\n" + "\n".join(leaked)


def test_root_tests_do_not_directly_import_ovk_owned_packages() -> None:
    offenders = sorted(
        path.name
        for path in ROOT_TESTS.glob("test_*.py")
        if path.name != Path(__file__).name and _imports_ovk_owned_package(path)
    )
    assert offenders == [], "Root tests importing OVK-owned packages:\n" + "\n".join(offenders)
