from __future__ import annotations

import importlib.util
from pathlib import Path


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


def test_vent_core_packages_are_owned_by_vent_module() -> None:
    for package in ("crow_vent", "crow_vent_drawing"):
        origin = _package_origin(package).as_posix()
        assert "/modules/crow-vent-module/src/" in origin, (
            f"{package} must be loaded from modules/crow-vent-module, got {origin}"
        )


def test_vent_core_has_no_source_artifacts_in_backbone_src() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    for package in ("crow_vent", "crow_vent_drawing"):
        artifacts = _source_artifacts(repository_root / "src" / package)
        assert not artifacts, f"{package} leaked source artifacts into backbone: {artifacts}"
