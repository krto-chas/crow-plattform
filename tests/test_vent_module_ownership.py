from __future__ import annotations

import importlib.util
from pathlib import Path

MIGRATED_VENT_PACKAGES = (
    "crow_vent",
    "crow_vent_drawing",
    "crow_riser_model",
    "crow_takeoff_consolidation",
    "crow_vent_quote",
    "crow_benchmark_pricing",
)


def _package_origin(package: str) -> Path:
    spec = importlib.util.find_spec(package)
    assert spec is not None, f"{package} is not importable"
    assert spec.origin is not None, f"{package} has no import origin"
    return Path(spec.origin).resolve()


def _source_artifacts(package_root: Path) -> tuple[Path, ...]:
    if not package_root.exists():
        return ()
    return tuple(
        path
        for path in package_root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )


def test_migrated_vent_packages_are_owned_by_vent_module() -> None:
    for package in MIGRATED_VENT_PACKAGES:
        origin = _package_origin(package).as_posix()
        assert "/modules/crow-vent-module/src/" in origin, (
            f"{package} must be loaded from modules/crow-vent-module, got {origin}"
        )


def test_migrated_vent_packages_have_no_source_artifacts_in_backbone_src() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    for package in MIGRATED_VENT_PACKAGES:
        artifacts = _source_artifacts(repository_root / "src" / package)
        assert not artifacts, f"{package} leaked source artifacts into backbone: {artifacts}"


def test_vent_web_surfaces_are_owned_by_vent_module() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    module_root = repository_root / "modules" / "crow-vent-module" / "src" / "crow_vent_module"
    assert (module_root / "vent_surface.py").is_file()
    assert (module_root / "vent_quote_surface.py").is_file()
    assert not (repository_root / "src" / "crow_workbench" / "vent_surface.py").exists()
    assert not (repository_root / "src" / "crow_workbench" / "vent_quote_surface.py").exists()
