from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_TESTS = ROOT / "tests"
OVK_OWNED_IMPORT_ROOTS = {
    "crow_ovk",
    "crow_ovk_field",
    "crow_ovk_workflow",
    "crow_ovk_import",
    "crow_ovk_pricing",
    "crow_ovk_legacy",
    "crow_ovk_reporting",
    "crow_ovk_module",
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


def test_root_tests_do_not_own_ovk_domain_tests() -> None:
    offenders = sorted(
        path.name
        for path in ROOT_TESTS.glob("test_*.py")
        if path.name != Path(__file__).name and _imports_ovk_owned_package(path)
    )
    assert offenders == [], "Root tests importing OVK-owned packages:\n" + "\n".join(offenders)
