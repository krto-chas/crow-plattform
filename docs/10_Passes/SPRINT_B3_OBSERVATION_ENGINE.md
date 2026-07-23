# Sprint B3 — Observation Engine

Version `0.6.0-alpha.4`.

B3 converts page content into immutable, traceable observations. It does not
create claims, resolve conflicts or make decisions.

## Observation types

- text
- number
- unit
- reference
- date
- heading

## Provenance

Every observation contains:

- document id,
- page id and page number,
- region id,
- character offsets,
- source text,
- extraction source,
- confidence,
- page fingerprint.

## CLI

```bash
crow observe ./project/crow-project.json
```

The result is persisted as `crow-observations.json`.

## Architectural boundary

An observation says that content was found. It does not say what the content
means. Domain interpretation belongs to later claim and knowledge-fusion layers.
