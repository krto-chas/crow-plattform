# RC readiness pass 4 — Project Dataset evidence foundation

Baseline remains `0.7.0-alpha.1`. No release or RC is declared.

## Implemented and locally verified

- Immutable file identity using byte size and SHA-256.
- Explicit source roles and assessed reference quality.
- Header-level format detection for DWG, IFC, PDF, DXF and ZIP.
- Deterministic JSON manifests.
- Real manifests for `V-50-1-01` and `V57 KFU1`.
- Partial supplier quotation recorded without promoting it to a complete quantity truth.

## Deliberate limits

This pass does not parse DWG geometry, compare IFC and DWG objects, extract quantities,
or reconcile the quotation. It establishes the evidence boundary needed before those
functions can be implemented and tested honestly.

## Local verification

- Ruff: pass.
- Mypy strict: pass for 146 source files.
- Pytest: 299 passed.
- Package build: wheel and sdist built successfully.
