# Sprint B9.1 — Technical Delta Foundation

Version: `0.6.0-alpha.14`.

B9.1 compares an explicit technical baseline with human-approved technical
decision candidates.

## Delta types

- `added`
- `removed`
- `modified`
- `unchanged`

Only review records with status `approved` and target type
`technical_decision` are treated as the approved current state.

## Baseline

The baseline is a separate, versionable JSON artifact. Each item contains a
stable ID, comparison key, category, title, value, unit and source.

Comparison keys are normalized and deterministic. Duplicate baseline keys or
multiple approved decisions with the same key are rejected rather than silently
merged.

## Provenance

Each delta records:

- baseline item ID;
- approved decision ID;
- approving review event ID;
- accepted claim IDs;
- authority decision IDs;
- source document IDs;
- comparison trace.

## CLI

Create a baseline template:

```bash
crow delta template ./crow-technical-baseline.json --project-id <project-id>
```

Build technical deltas:

```bash
crow delta build ./crow-project.json \
  --baseline ./crow-technical-baseline.json
```

Optional explicit inputs:

```bash
crow delta build ./crow-project.json \
  --baseline ./crow-technical-baseline.json \
  --decisions ./crow-technical-decisions.json \
  --reviews ./crow-technical-reviews.json
```

Output:

```text
crow-technical-deltas.json
```

B9.1 classifies technical change only. It does not calculate commercial impact,
price, quantity or entitlement.
