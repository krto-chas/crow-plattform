import pytest
from crow_example_module import ExamplePlugin

from crow_module_sdk import DuplicateModuleError, ModuleRegistry


def test_registry_registers_and_lists_module() -> None:
    registry = ModuleRegistry()

    registered = registry.register(ExamplePlugin())

    assert registered.module_id == "crow.example"
    assert registry.get("crow.example") == registered
    assert registry.list() == (registered,)


def test_registry_rejects_duplicate_module_id() -> None:
    registry = ModuleRegistry()
    registry.register(ExamplePlugin())

    with pytest.raises(DuplicateModuleError):
        registry.register(ExamplePlugin())
