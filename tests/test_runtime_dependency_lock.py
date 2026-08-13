from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements" / "runtime-direct.lock"
PROJECTS = (
    ROOT / "pyproject.toml",
    ROOT / "modules" / "crow-vent-module" / "pyproject.toml",
    ROOT / "modules" / "crow-pressure-test-module" / "pyproject.toml",
    ROOT / "modules" / "crow-ovk-module" / "pyproject.toml",
)
_INTERNAL = {"crow-plattform"}
_NAME = re.compile(r"^[A-Za-z0-9_.-]+")
_PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s]+)$")


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _declared_external_dependencies() -> set[str]:
    names: set[str] = set()
    for project_path in PROJECTS:
        data = tomllib.loads(project_path.read_text(encoding="utf-8"))
        project = data["project"]
        dependencies = list(project.get("dependencies", []))
        if project_path == ROOT / "pyproject.toml":
            dependencies.extend(project.get("optional-dependencies", {}).get("export", []))
        for dependency in dependencies:
            match = _NAME.match(dependency)
            assert match is not None, f"Cannot parse dependency: {dependency}"
            name = _normalize(match.group(0))
            if name not in _INTERNAL:
                names.add(name)
    return names


def _locked_dependencies() -> dict[str, str]:
    locked: dict[str, str] = {}
    for raw_line in LOCK.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _PIN.fullmatch(line)
        assert match is not None, f"Runtime lock entry is not an exact pin: {line}"
        name = _normalize(match.group(1))
        assert name not in locked, f"Duplicate runtime lock entry: {name}"
        locked[name] = match.group(2)
    return locked


def test_runtime_lock_exactly_covers_declared_external_dependencies() -> None:
    declared = _declared_external_dependencies()
    locked = set(_locked_dependencies())

    assert locked == declared, (
        f"runtime-direct.lock drift: missing={sorted(declared - locked)}, "
        f"unexpected={sorted(locked - declared)}"
    )


def test_runtime_lock_contains_no_floating_versions() -> None:
    locked = _locked_dependencies()

    assert locked
    assert all(
        version and not any(token in version for token in "*<>=!~")
        for version in locked.values()
    )
