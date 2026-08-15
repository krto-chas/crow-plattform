from __future__ import annotations

import os
from pathlib import Path


def _path_from_environment(name: str) -> Path | None:
    configured = os.getenv(name)
    if configured is None or not configured.strip():
        return None
    return Path(configured).expanduser()


def platform_data_root() -> Path:
    configured = _path_from_environment("CROW_PLATFORM_DATA_ROOT")
    if configured is not None:
        return configured
    return Path.cwd() / ".crow-workbench"


def platform_config_root(data_root: Path | None = None) -> Path:
    configured = _path_from_environment("CROW_PLATFORM_CONFIG_ROOT")
    if configured is not None:
        return configured
    root = data_root if data_root is not None else platform_data_root()
    return root / "config"
