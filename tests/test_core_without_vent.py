from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_platform_backbone_starts_without_vent_module(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    runtime_root = tmp_path / "runtime"
    script = r'''
import builtins
import os
import sys
from pathlib import Path

runtime_root = Path(sys.argv[1])
os.environ["CROW_PLATFORM_DATA_DIR"] = str(runtime_root / "data")
os.environ["CROW_PLATFORM_CONFIG_DIR"] = str(runtime_root / "config")

real_import = builtins.__import__


def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "crow_vent" or name.startswith("crow_vent."):
        raise ImportError("crow_vent intentionally unavailable in core startup test")
    return real_import(name, globals, locals, fromlist, level)


builtins.__import__ = blocked_import

import crow_cad_text
import crow_canonical
import crow_module_sdk.module_registry as module_registry

module_registry.entry_points = lambda **kwargs: ()

from crow_workbench.shell import create_app

app = create_app(runtime_root / "data", runtime_root / "config")
paths = set(app.openapi()["paths"])
assert "/health" in paths
assert "/api/vent/registry" not in paths
assert "/vent" not in paths
assert crow_cad_text.CadTextExtractor is not None
assert crow_canonical.CanonicalGraphBridge is not None
'''
    environment = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "-c", script, str(runtime_root)],
        cwd=repository_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        "Platform backbone could not start with crow_vent unavailable:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
