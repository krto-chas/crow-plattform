"""Begränsa Bash-anrop från Crow-agenter till uttryckligen tillåtna kommandon."""

import json
import re
import sys

COMMON = {
    "git status --porcelain",
    "git rev-parse HEAD",
    "git branch --show-current",
    "git log --oneline -5",
}
VERIFY = {
    "ruff format --check .",
    "ruff check .",
    "mypy",
    "mypy --strict modules/*/src modules/*/tests",
    "pytest -q",
    "bash scripts/verify-agent-modules.sh",
    "python -m crow_module_conformance.cli review --root .",
    "python --version",
}
DIFF = re.compile(r"git diff [0-9a-f]{40} [0-9a-f]{40}(?: --stat)?")


def allowed(role: str, command: str) -> bool:
    """Tillåt endast fasta kommandon och diff med fullständiga SHA."""
    if role not in {"reviewer", "verifier"}:
        return False
    return (
        command in COMMON
        or DIFF.fullmatch(command) is not None
        or (role == "verifier" and command in VERIFY)
    )


def main() -> int:
    """Avvisa okända kommandon och ogiltiga hook-anrop."""
    try:
        role = sys.argv[1]
        payload = json.load(sys.stdin)
        command = payload["tool_input"]["command"]
        if isinstance(command, str) and allowed(role, command):
            return 0
    except (IndexError, KeyError, TypeError, ValueError):
        pass
    print("Crow: Bash-kommandot är inte tillåtet för agenten.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
