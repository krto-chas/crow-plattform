from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "modules" / "module_layout_manifest.json"


def _manifest() -> dict[str, object]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_first_party_modules_must_live_under_modules() -> None:
    manifest = _manifest()
    meta = manifest["meta"]
    assert isinstance(meta, dict)
    assert meta["new_modules_must_live_under"] == "modules/"

    modules = manifest["modules"]
    assert isinstance(modules, list)
    registered_roots: set[str] = set()
    for entry in modules:
        assert isinstance(entry, dict)
        repository_root = str(entry["repository_root"])
        assert repository_root.startswith("modules/")
        assert (ROOT / repository_root / "pyproject.toml").is_file()
        registered_roots.add(repository_root)

    discovered_roots: set[str] = set()
    for pyproject in (ROOT / "modules").glob("*/pyproject.toml"):
        text = pyproject.read_text(encoding="utf-8")
        if '[project.entry-points."crow.modules"]' in text:
            discovered_roots.add(pyproject.parent.relative_to(ROOT).as_posix())

    assert discovered_roots == registered_roots


def test_backbone_root_cannot_register_a_domain_module() -> None:
    root_pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '[project.entry-points."crow.modules"]' not in root_pyproject


def test_module_owned_packages_do_not_silently_live_in_backbone() -> None:
    manifest = _manifest()
    modules = manifest["modules"]
    assert isinstance(modules, list)

    for entry in modules:
        assert isinstance(entry, dict)
        module_id = str(entry["module_id"])
        module_root = ROOT / str(entry["repository_root"]) / "src"
        pending = bool(entry.get("migration_pending_from_root_src", False))
        packages = entry["owned_packages"]
        assert isinstance(packages, list)

        for package in packages:
            package_name = str(package)
            in_root = (ROOT / "src" / package_name).exists()
            in_module = (module_root / package_name).exists()
            if pending:
                message = f"{module_id}: declared package {package_name} is missing"
                assert in_root or in_module, message
            else:
                assert not in_root, f"{module_id}: {package_name} leaked back into backbone src/"
                assert in_module, f"{module_id}: {package_name} missing from its module root"
