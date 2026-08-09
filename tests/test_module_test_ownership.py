from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "modules" / "module_layout_manifest.json"


def _manifest_modules() -> list[dict[str, object]]:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    modules = payload["modules"]
    assert isinstance(modules, list)
    return modules


def test_repository_ownership_requires_source_and_test_migration() -> None:
    for module in _manifest_modules():
        complete = bool(module["repository_ownership_complete"])
        expected = bool(module["source_migration_complete"]) and bool(
            module["test_migration_complete"]
        )
        assert complete is expected, module["module_id"]


def test_completed_test_migrations_are_owned_by_module_tree() -> None:
    for module in _manifest_modules():
        if not bool(module["test_migration_complete"]):
            continue
        repository_root = ROOT / str(module["repository_root"])
        owned_tests = module["owned_tests"]
        assert isinstance(owned_tests, list) and owned_tests, module["module_id"]
        for filename in owned_tests:
            assert isinstance(filename, str)
            assert (repository_root / "tests" / filename).is_file(), (
                module["module_id"],
                filename,
            )
            assert not (ROOT / "tests" / filename).exists(), (
                module["module_id"],
                filename,
            )
