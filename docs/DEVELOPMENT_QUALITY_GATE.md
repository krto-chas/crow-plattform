# Development quality gate

Install the development tools in the active Python environment from the repository root:

```sh
python -m pip install -e ".[dev]"
python -m pre_commit install
```

Before committing Python changes:

```sh
python -m ruff format .
python -m ruff check .
python -m ruff format --check .
python -m pre_commit run --all-files
```

Review the diff after formatting. Run mypy and relevant tests using the same
module installation and test commands as CI before pushing.

The installed hook checks staged Python files without rewriting them.
It uses Ruff from the active Python environment and the repository's
pyproject.toml configuration. Hooks are installed per clone, not by GitHub.
Do not bypass a failed hook; correct the source and stage it again.

For API-based commits or environments without a local checkout, hooks do
not execute. Format and lint the exact proposed changes in a compatible
environment before publishing whenever possible. If unavailable, disclose
that limitation and wait for CI; never report unexecuted checks as passed.

GitHub CI remains the final quality gate. A pull request is ready for merge
only after all required checks pass on its latest head commit.
