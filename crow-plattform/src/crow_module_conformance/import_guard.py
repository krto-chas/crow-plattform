from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

FORBIDDEN_PREFIXES = (
    "crow_core.internal",
    "crow_backbone.internal",
    "crow_module_sdk._internal",
)


@dataclass(frozen=True, slots=True)
class ForbiddenImport:
    path: str
    line: int
    module: str


def scan_forbidden_imports(
    source_root: Path,
    forbidden_prefixes: tuple[str, ...] = FORBIDDEN_PREFIXES,
) -> tuple[ForbiddenImport, ...]:
    violations: list[ForbiddenImport] = []
    if not source_root.exists():
        return ()

    for path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imports: list[tuple[str, int]] = []
            if isinstance(node, ast.Import):
                imports.extend((alias.name, node.lineno) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append((node.module, node.lineno))

            for module, lineno in imports:
                if any(
                    module == prefix or module.startswith(prefix + ".")
                    for prefix in forbidden_prefixes
                ):
                    violations.append(
                        ForbiddenImport(
                            path=str(path.relative_to(source_root)),
                            line=lineno,
                            module=module,
                        )
                    )
    return tuple(violations)
