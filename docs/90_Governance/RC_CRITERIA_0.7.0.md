# RC criteria — Crow Platform 0.7.0

## Status

This document defines the entry criteria for a future `0.7.0-rc.1` candidate.
It does **not** declare the current `0.7.0-alpha.1` baseline to be an RC.

A criterion is complete only when its evidence exists in the repository and the
corresponding command passes in CI. Narrative claims are not evidence.

## Required repository gates

| ID | Criterion | Command/evidence | RC requirement |
|---|---|---|---|
| RC-001 | Lint | `ruff check .` | 0 errors |
| RC-002 | Static types | `mypy` | 0 errors in strict mode |
| RC-003 | Automated tests | `pytest -q` | all tests pass |
| RC-004 | Architecture review | `crow review --root . --release 0.7.0-alpha.1` during alpha; exact RC string after version bump | ARC-001–ARC-004 PASS |
| RC-005 | Distribution build | `python -m build` | wheel and sdist produced |
| RC-006 | Version consistency | `pyproject.toml`, CLI default, Workbench version, CHANGELOG and verification manifest | exact release identity is consistent |
| RC-007 | Verification manifest | `V0_7_0A1_VERIFICATION.json`, replaced by an RC-specific manifest when RC is cut | every gate represented by machine-readable evidence |
| RC-008 | Isolated installation | install built wheel in a clean environment | CLI imports and starts without source tree |
| RC-009 | End-to-end baseline | documented deterministic pipeline run | expected identifiers and outputs match |
| RC-010 | Real-project DXF validation | a non-synthetic DXF fixture or controlled external test input, plus recorded result | parser completes; unsupported entities and losses are reported, never hidden |
| RC-011 | Workbench smoke test | start server and exercise health/project/graph endpoints | no startup or route errors |
| RC-012 | Provenance and disposition | `docs/PROVENANCE.md` | every consolidated source package accounted for |

## RC blockers

The candidate must not be created while any of the following is true:

- CI is not required on every push and pull request.
- A required gate is missing from CI.
- The version identity differs between code, metadata or release evidence.
- A feature is described as implemented without executable code and tests.
- Known data loss is silently ignored by import or geometry processing.
- Generated caches, local environments or build artefacts are included in source packaging.

## Current baseline assessment

The baseline was inspected locally on 2026-07-20. This table records only commands
actually executed in that inspection environment.

| Criterion | Result | Evidence |
|---|---|---|
| RC-001 | pass | `ruff check .` — 0 errors |
| RC-002 | pass | `mypy` — no issues in 142 source files |
| RC-003 | pass | `295 passed` after RC-010 loss-reporting regression coverage |
| RC-004 | pass | ARC-001–ARC-004 PASS for `0.7.0-alpha.1` |
| RC-005 | pass | wheel and sdist built successfully |
| RC-006 | remediation started | CLI default and CI release argument aligned to `0.7.0-alpha.1`; historical README content retained with a current-status header |
| RC-007 | partial | alpha verification manifest exists, but RC manifest does not yet exist |
| RC-008 | pass for install/import/CLI smoke | built wheel installed in a new virtual environment; CLI help and core imports passed |
| RC-009 | pass | `python scripts/verify_e2e_baseline.py`; committed baseline and SHA-256 in `evidence/rc-009/` |
| RC-010 | pass | controlled external DXF verified; `evidence/rc-010/mandelblomman_aggregat1_acceptance.md` and JSON inventory record parser completion and 5,384 unsupported `3DFACE` entities without silent loss |
| RC-011 | pass | `/health` and `/api/projects` returned HTTP 200; automated health test added |
| RC-012 | present | `docs/PROVENANCE.md` |

## Promotion rule

The version may be changed to `0.7.0-rc.1` only in a dedicated release change after
RC-001 through RC-012 are green or explicitly marked not applicable with written,
reviewable justification. The version change itself must not be used to imply that
any criterion has passed.
