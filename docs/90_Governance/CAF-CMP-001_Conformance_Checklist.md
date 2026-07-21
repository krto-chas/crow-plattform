# CAF-CMP-001 Conformance Checklist

Conformance is demonstrated by passing gates, not by filling in forms. A release or module is conformant when all applicable rows are green.

## Repository gates (run by CI on every push)

| Gate | Command | Pass criterion |
|---|---|---|
| Lint | `ruff check .` | 0 errors |
| Types | `mypy` (strict) | 0 errors |
| Tests | `pytest -q` | all tests pass |
| Architecture | `crow review --root .` | ARC-001…ARC-004 PASS |
| Packaging | `python -m build` | wheel + sdist build |

## Module gates (per module, before registration)

| Gate | Command | Pass criterion |
|---|---|---|
| Contract | `crow module validate <entrypoint> --backbone-version <v> --domain-model-version <v>` | PASS: module is Crow-compatible |
| Discovery | `crow module list` | module appears via `crow.modules` entry point |
| Trust | manifest signature verification | status `trusted` |

## Release gates (per release)

- `B*_VERIFICATION.json` present for the sprint, `quality` section all `pass` (see CAF-REL-001).
- CHANGELOG entry exists for the exact release string (checked by ARC-004).
- Version strings consistent across `pyproject.toml`, README and CLI defaults.
- For validated releases: isolated wheel-only install and end-to-end demo pass (`verify_release.py` pattern from 0.5.0).
