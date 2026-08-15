from crow_module_conformance.cli import main


def test_cli_validates_example_module(capsys) -> None:
    exit_code = main(
        [
            "module",
            "validate",
            "crow_example_module.plugin:ExamplePlugin",
            "--backbone-version",
            "1.0.0",
            "--domain-model-version",
            "1.0.0",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "PASS" in output
