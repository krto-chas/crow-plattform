# Sprint B7.2 — Authority Discovery

Version `0.6.0-alpha.8`.

B7.2 derives an initial authority manifest from the indexed project documents.
It detects AB 04/ABT 06 references, classifies known document types and searches
AFC.111/AFD.111 for supported explicit precedence overrides.

The discovery result is evidence-backed and confidence-scored. Ambiguous cases
are marked `requires_review`; the engine does not invent a hierarchy.

## CLI

```bash
crow authority discover ./crow-project.json
```

Outputs:

- `crow-authority-discovery.json`
- `crow-authority-manifest.discovered.json`

The discovered manifest can then be supplied to `crow authority resolve`.
