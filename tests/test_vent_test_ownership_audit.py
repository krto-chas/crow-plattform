from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_TESTS = ROOT / "tests"
VENT_OWNED_IMPORT_ROOTS = {
    "crow_vent",
    "crow_vent_drawing",
    "crow_riser_model",
    "crow_takeoff_consolidation",
    "crow_vent_quote",
    "crow_benchmark_pricing",
    "crow_vent_module",
}


def _imports_vent_owned_package(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".", 1)[0] in VENT_OWNED_IMPORT_ROOTS:
                    return True
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".", 1)[0] in VENT_OWNED_IMPORT_ROOTS:
                return True
    return False


def test_root_tests_do_not_own_vent_domain_tests() -> None:
    offenders = sorted(
        path.name
        for path in ROOT_TESTS.glob("test_*.py")
        if path.name != Path(__file__).name and _imports_vent_owned_package(path)
    )
    assert offenders == [], "Root tests importing Vent-owned packages:\n" + "\n".join(offenders)
