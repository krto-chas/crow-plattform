from pathlib import Path

from crow_module_conformance import scan_forbidden_imports


def test_forbidden_private_core_import_is_detected(tmp_path: Path) -> None:
    source = tmp_path / "plugin.py"
    source.write_text("from crow_core.internal.database import Session\n", encoding="utf-8")

    violations = scan_forbidden_imports(tmp_path)

    assert len(violations) == 1
    assert violations[0].module == "crow_core.internal.database"


def test_public_sdk_import_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "plugin.py"
    source.write_text("from crow_module_sdk import Claim\n", encoding="utf-8")

    assert scan_forbidden_imports(tmp_path) == ()
