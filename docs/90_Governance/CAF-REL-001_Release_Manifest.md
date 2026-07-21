# CAF-REL-001 Release Manifest

Every sprint release produces a verification manifest `B<sprint>_VERIFICATION.json` at repository root. This documents the format already in use (authoritative examples: `B11_3_VERIFICATION.json` and earlier).

## Required fields

```json
{
  "release": "0.6.0-alpha.22",
  "sprint": "B11.3 Estimate Revision and Versioning",
  "quality": {
    "ruff": "pass",
    "mypy_strict": "pass",
    "pytest": "190 passed",
    "wheel": "pass",
    "sdist": "pass"
  },
  "integration_demo": { "…": "sprint-specific evidence with ids, totals and currency" }
}
```

- `release` — exact release string, must match the CHANGELOG entry.
- `quality` — one key per repository gate in CAF-CMP-001; values are `pass` or the failure summary. A manifest with a non-pass value must not be tagged.
- `integration_demo` — machine-readable evidence from the sprint's end-to-end demo (identifiers, counts, monetary totals with currency).

## Distribution artefacts

Validated releases additionally ship an `ARTIFACT_MANIFEST.json` listing each distributed file with its SHA256 checksum, verified by `verify_release.py` in an isolated environment (established in the 0.5.0 Foundation release).
