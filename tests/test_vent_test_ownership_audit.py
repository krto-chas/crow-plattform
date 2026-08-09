from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_TESTS = ROOT / "tests"
VENT_TESTS = ROOT / "modules" / "crow-vent-module" / "tests"
VENT_OWNED_IMPORT_ROOTS = {
    "crow_vent",
    "crow_vent_drawing",
    "crow_riser_model",
    "crow_takeoff_consolidation",
    "crow_vent_quote",
    "crow_benchmark_pricing",
    "crow_vent_module",
}
MIGRATED_TESTS = {
    "test_benchmark_pricing.py",
    "test_crow_vent.py",
    "test_riser_model.py",
    "test_takeoff_consolidation.py",
    "test_takeoff_pricing.py",
    "test_vent_audit_diff.py",
    "test_vent_audit_verification.py",
    "test_vent_drawing.py",
    "test_vent_graph_audit.py",
    "test_vent_lexicon.py",
    "test_vent_quote.py",
    "test_vent_text_interpretation.py",
    "test_vent_surface.py",
    "test_workbench_vent_quote.py",
}
PLATFORM_INTEGRATION_ALLOWLIST = {
    "test_crow_canonical.py",
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


def test_declared_vent_tests_live_only_in_module() -> None:
    missing = sorted(name for name in MIGRATED_TESTS if not (VENT_TESTS / name).is_file())
    leaked = sorted(name for name in MIGRATED_TESTS if (ROOT_TESTS / name).exists())
    assert missing == [], "Vent module is missing owned tests:\n" + "\n".join(missing)
    assert leaked == [], "Vent-owned tests leaked back to root:\n" + "\n".join(leaked)


def test_root_tests_do_not_own_vent_domain_tests() -> None:
    offenders = sorted(
        path.name
        for path in ROOT_TESTS.glob("test_*.py")
        if path.name != Path(__file__).name
        and path.name not in PLATFORM_INTEGRATION_ALLOWLIST
        and _imports_vent_owned_package(path)
    )
    assert offenders == [], "Root tests importing Vent-owned packages:\n" + "\n".join(offenders)
