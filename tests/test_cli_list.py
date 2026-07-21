from crow_module_conformance.cli import main


def test_cli_list_handles_no_installed_modules(capsys) -> None:
    exit_code = main(["module", "list"])

    assert exit_code == 0
    assert "No installed Crow modules discovered" in capsys.readouterr().out
