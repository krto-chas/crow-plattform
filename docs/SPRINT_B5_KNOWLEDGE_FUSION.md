# Sprint B5 — Knowledge Fusion

Version `0.6.0-alpha.6`.

B5 groups semantically equivalent claim candidates across documents. It makes
disagreement visible but does not choose an authoritative value.

## Fusion states

- `SINGLETON`: one candidate only
- `CONSISTENT`: several candidates support the same normalized value
- `CONFLICTING`: the same semantic key has multiple value variants

## Semantic key

Clusters are keyed by:

- candidate type,
- normalized subject,
- predicate,
- unit.

The value is deliberately excluded so conflicting values can land in the same
cluster.

## Boundary

Knowledge Fusion does not:

- rank documents,
- resolve authority,
- accept or reject a claim,
- generate a decision,
- calculate commercial impact.

## CLI

```bash
crow fuse ./project/crow-project.json
```

The command runs missing upstream stages automatically and persists
`crow-knowledge-fusion.json`.
