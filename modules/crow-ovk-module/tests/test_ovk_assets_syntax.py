"""Syntaxkontroll av modulens JavaScript-tillgångar.

Övriga UI-tester strängmatchar bara filinnehållet och upptäcker därför inte
ett syntaxfel som hindrar webbläsaren från att ladda skriptet.
"""

from __future__ import annotations

import shutil
import subprocess
from importlib import resources
from pathlib import Path

import pytest

_NODE = shutil.which("node")
_ASSETS = Path(str(resources.files("crow_ovk_module").joinpath("assets")))
_SCRIPTS = sorted(_ASSETS.glob("*.js"))


def test_assets_contain_scripts() -> None:
    assert _SCRIPTS, "inga JavaScript-tillgångar hittades"


@pytest.mark.skipif(_NODE is None, reason="node saknas i miljön")
@pytest.mark.parametrize("script", _SCRIPTS, ids=lambda path: path.name)
def test_script_parses(script: Path) -> None:
    assert _NODE is not None
    result = subprocess.run(  # noqa: S603
        [_NODE, "--check", str(script)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
