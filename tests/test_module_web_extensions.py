from pathlib import Path

from crow_module_sdk.module_registry import ModuleRegistry
from crow_module_sdk.web import CrowWebModule
from crow_workbench.shell import create_app


def test_first_party_domain_modules_are_discoverable() -> None:
    registry = ModuleRegistry()
    registered = registry.discover()
    by_id = {item.module_id: item for item in registered}

    assert {"crow.vent", "crow.provtryckning", "crow.ovk"} <= set(by_id)
    for module_id in ("crow.vent", "crow.provtryckning", "crow.ovk"):
        assert isinstance(by_id[module_id].plugin, CrowWebModule)


def test_workbench_mounts_module_routes_from_registry(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    paths = {
        path
        for route in app.routes
        if (path := getattr(route, "path", None)) is not None
    }

    assert "/vent" in paths
    assert "/provtryckning" in paths
    assert "/ovk" in paths
    assert "/ovk/besiktning" in paths
    assert "/ovk/falt" in paths
