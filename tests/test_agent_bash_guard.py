"""Regressionstester för agenternas Bash-begränsning."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / ".claude" / "hooks" / "agent_bash_guard.py"


@pytest.mark.parametrize(
    ("role", "command", "expected"),
    [
        ("reviewer", "git status --porcelain", 0),
        ("reviewer", "git diff " + "a" * 40 + " " + "b" * 40, 0),
        ("reviewer", "pytest -q", 2),
        ("verifier", "pytest -q", 0),
        ("verifier", "bash scripts/verify-agent-modules.sh", 0),
        ("verifier", "pytest -q; git push", 2),
        ("reviewer", "git status --porcelain > output", 2),
        ("reviewer", "git diff $(touch x) HEAD", 2),
        ("unknown", "git status --porcelain", 2),
    ],
)
def test_agent_bash_guard(role: str, command: str, expected: int) -> None:
    """Endast godkända kommandon får passera."""
    result = subprocess.run(
        [sys.executable, str(GUARD), role],
        input=json.dumps({"tool_input": {"command": command}}),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == expected
