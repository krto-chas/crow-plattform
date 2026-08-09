from pathlib import Path

import crow_ovk_module.ovk_field_surface as field_surface
import crow_ovk_module.ovk_surface as import_surface
import crow_ovk_module.ovk_workflow_surface as workflow_surface


def _path(module_file: str | None) -> str:
    assert module_file is not None
    return Path(module_file).resolve().as_posix()


def test_ovk_web_surfaces_are_owned_by_ovk_module() -> None:
    for module in (import_surface, workflow_surface, field_surface):
        path = _path(module.__file__)
        assert "/modules/crow-ovk-module/src/crow_ovk_module/" in path
        assert "/src/crow_workbench/" not in path
