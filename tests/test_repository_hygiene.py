from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tracked_paths() -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(line for line in result.stdout.splitlines() if line)


def test_generated_python_artifacts_are_not_tracked() -> None:
    offenders = [
        path
        for path in _tracked_paths()
        if "__pycache__/" in path or path.endswith((".pyc", ".pyo")) or ".egg-info/" in path
    ]
    assert offenders == [], "Tracked generated artifacts:\n" + "\n".join(offenders)
