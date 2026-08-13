from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ModuleInstallPlan:
    module_ids: tuple[str, ...]
    repository_roots: tuple[Path, ...]


def find_repository_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    candidates = (current, *current.parents)
    for candidate in candidates:
        if (candidate / "modules" / "module_layout_manifest.json").is_file():
            return candidate
    raise FileNotFoundError(
        "Could not find modules/module_layout_manifest.json from the current path"
    )


def _load_manifest(root: Path) -> list[dict[str, Any]]:
    path = root / "modules" / "module_layout_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Module layout manifest root must be an object")
    modules = payload.get("modules")
    if not isinstance(modules, list):
        raise ValueError("Module layout manifest must contain a modules list")

    entries: list[dict[str, Any]] = []
    for item in modules:
        if not isinstance(item, dict):
            raise ValueError("Every module manifest entry must be an object")
        entries.append(item)
    return entries


def build_module_install_plan(root: Path) -> ModuleInstallPlan:
    entries = _load_manifest(root)
    by_id: dict[str, dict[str, Any]] = {}
    for entry in entries:
        module_id = str(entry["module_id"])
        if module_id in by_id:
            raise ValueError(f"Duplicate module id in layout manifest: {module_id}")
        by_id[module_id] = entry

    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(module_id: str) -> None:
        if module_id in visited:
            return
        if module_id in visiting:
            raise ValueError(f"Cyclic module dependency detected at {module_id}")
        try:
            entry = by_id[module_id]
        except KeyError as error:
            raise ValueError(f"Unknown module dependency in layout manifest: {module_id}") from error

        visiting.add(module_id)
        requires = entry.get("requires_modules", [])
        if not isinstance(requires, list):
            raise ValueError(f"requires_modules must be a list for {module_id}")
        for dependency in sorted(str(item) for item in requires):
            visit(dependency)
        visiting.remove(module_id)
        visited.add(module_id)
        ordered.append(module_id)

    for module_id in sorted(by_id):
        visit(module_id)

    roots: list[Path] = []
    for module_id in ordered:
        repository_root = root / str(by_id[module_id]["repository_root"])
        if not (repository_root / "pyproject.toml").is_file():
            raise FileNotFoundError(f"Module package missing pyproject.toml: {repository_root}")
        roots.append(repository_root)

    return ModuleInstallPlan(module_ids=tuple(ordered), repository_roots=tuple(roots))
