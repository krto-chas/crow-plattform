# Project Dataset

`crow_project_dataset` records real project inputs without pretending that unsupported
formats have been parsed. A dataset manifest stores file identity, role, reference
quality, format detection, size and SHA-256.

The original project files are deliberately not copied into the source repository.
Evidence manifests reference their filenames and immutable hashes. This avoids
redistribution, repository bloat and accidental modification of source evidence.

## Reference quality

- `authoritative`: an original project source for the information it carries.
- `partial`: useful as comparison evidence but known to be incomplete.
- `supporting`: corroborating material, not the sole source of truth.
- `unknown`: quality has not been assessed.

## Current evidence datasets

- `v50-1-01`: DWG, IFC, PDF drawing and partial supplier quotation.
- `v57-kfu1`: five DWG drawings and one KFU archive.

The manifests do **not** claim geometric DWG parsing, IFC-to-DWG equivalence or
quantity accuracy. Those require separate executable verification.

## Rebuild

Use `scripts/build_reference_dataset.py`. Rebuilding against unchanged source files
must yield byte-identical JSON. Any hash change means that the source evidence changed
and requires review.
