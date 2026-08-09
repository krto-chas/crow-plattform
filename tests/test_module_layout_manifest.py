from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "modules" / "module_layout_manifest.json"


def _manifest() -> dict[str, object]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _has_source_artifacts(package_root: Path) -> bool:
    if not package_root.exists():
        return False
    return any(
        path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
        for path in package_root.rglob("*")
    )


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


def test_module_dependencies_reference_declared_modules() -> None:
    manifest = _manifest()
    modules = manifest["modules"]
    assert isinstance(modules, list)
    entries = [entry for entry in modules if isinstance(entry, dict)]
    module_ids = {str(entry["module_id"]) for entry in entries}

    for entry in entries:
        module_id = str(entry["module_id"])
        requires = entry.get("requires_modules", [])
        assert isinstance(requires, list)
        assert module_id not in requires
        assert set(str(item) for item in requires).issubset(module_ids)

    pressure = next(entry for entry in entries if entry["module_id"] == "crow.provtryckning")
    ovk = next(entry for entry in entries if entry["module_id"] == "crow.ovk")
    assert pressure["requires_modules"] == ["crow.vent"]
    assert ovk["requires_modules"] == []


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
        migrated = entry.get("migrated_packages", [])
        pending_packages = entry.get("migration_pending_packages", [])
        assert isinstance(migrated, list)
        assert isinstance(pending_packages, list)
        assert set(map(str, migrated)).isdisjoint(set(map(str, pending_packages)))
        assert set(map(str, migrated)) | set(map(str, pending_packages)) == set(map(str, packages))
        assert pending is bool(pending_packages)

        for package in packages:
            package_name = str(package)
            root_package = ROOT / "src" / package_name
            module_package = module_root / package_name
            root_has_source = _has_source_artifacts(root_package)
            module_has_source = _has_source_artifacts(module_package)
            if package_name in migrated:
                assert not root_has_source, (
                    f"{module_id}: {package_name} leaked back into backbone src/"
                )
                assert module_has_source, f"{module_id}: {package_name} missing from its module root"
            else:
                message = f"{module_id}: pending package {package_name} is missing"
                assert root_has_source or module_has_source, message
