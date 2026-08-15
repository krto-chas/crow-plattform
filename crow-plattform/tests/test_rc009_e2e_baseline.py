import json
import os
import subprocess
import sys
from pathlib import Path


def test_rc009_committed_e2e_baseline_is_deterministic() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    completed = subprocess.run(
        [sys.executable, "scripts/verify_e2e_baseline.py"],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        env=env,
    )
    result = json.loads(completed.stdout)
    assert result["status"] == "pass"
    assert result["baseline_id"] == "claim-to-estimate-reference-v1"
    assert len(result["result_sha256"]) == 64
