# Sprint B4 — Claim Extraction

Version: `0.6.0-alpha.5`.

B4 groups observations into candidate claims. A candidate is not yet accepted
knowledge and does not participate in authority resolution.

## Candidate forms

- `KEY_VALUE`: for example `Luftflöde: 320 l/s`
- `QUANTITY`: for example `160 mm` without an identified subject
- `REFERENCE`: a region references another document or drawing

## Provenance

Each candidate carries:

- all supporting observation ids,
- document, page and region,
- source locators,
- confidence,
- a stable semantic fingerprint.

## Boundary

B4 proposes structured statements. It does not:

- decide whether a candidate is true,
- merge candidates across documents,
- detect conflicts,
- select an authoritative source,
- create commercial impact.

Those operations belong to Knowledge Fusion and later layers.

## CLI

```bash
crow claims ./project/crow-project.json
```

The command reuses `crow-observations.json` when present and otherwise runs the
Observation Engine first. Candidates are stored in
`crow-claim-candidates.json`.
