# Sprint B7.3 — Accepted Claims

Version: `0.6.0-alpha.9`.

B7.3 introduces the canonical truth layer consumed by later decision modules.
It transforms resolved knowledge clusters into immutable accepted claims without
altering observations, candidates, clusters, or authority decisions.

## Admission rule

Only authority decisions with one of these statuses enter the canonical layer:

- `accepted_complementary`
- `accepted_consistent`
- `resolved_by_hierarchy`
- `resolved_by_date`

Unresolved clusters remain in `pending`; they can never silently become accepted
claims.

## Provenance

Every accepted claim retains:

- knowledge cluster ID
- authority decision ID
- source candidate IDs
- source document IDs
- authority framework
- applied rule
- complete decision trace

## Determinism

Claim fingerprints and IDs are derived from the semantic key, accepted value,
authority decision and knowledge-cluster fingerprint. Re-running an unchanged
project produces the same canonical claim IDs.

## CLI

```bash
crow accepted build ./crow-project.json
```

Optional explicit inputs:

```bash
crow accepted build ./crow-project.json \
  --fusion ./crow-knowledge-fusion.json \
  --resolution ./crow-authority-resolution.json
```

Output: `crow-accepted-claims.json`.
