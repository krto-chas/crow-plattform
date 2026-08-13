from __future__ import annotations

from crow_workbench.shell import app as platform_app

from .observability import configure_runtime_observability
from .runtime import platform_config_root, platform_data_root

_data_root = platform_data_root()
_config_root = platform_config_root(_data_root)
_config_root.mkdir(parents=True, exist_ok=True)
configure_runtime_observability(platform_app, data_root=_data_root, config_root=_config_root)

app = platform_app
