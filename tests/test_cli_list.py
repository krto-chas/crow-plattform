from crow_example_module import ExamplePlugin

from crow_module_conformance.cli import main
from crow_module_sdk import module_registry


def test_cli_list_handles_no_installed_modules(capsys, monkeypatch) -> None:
    """Deterministic regardless of which modules the environment has installed."""
    monkeypatch.setattr(module_registry, "entry_points", lambda group: ())
    exit_code = main(["module", "list"])

    assert exit_code == 0
    assert "No installed Crow modules discovered" in capsys.readouterr().out


def test_cli_list_reports_discovered_module(capsys, monkeypatch) -> None:
    """Discovery reports modules found via crow.modules entry points."""
    class _Candidate:
        name = "example"

        @staticmethod
        def load():
            return ExamplePlugin

    monkeypatch.setattr(module_registry, "entry_points", lambda group: (_Candidate(),))
    exit_code = main(["module", "list"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "crow.example" in out
