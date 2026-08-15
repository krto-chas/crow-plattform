# Sprint B11.1 — Estimate Line Foundation

Version: `0.6.0-alpha.20`.

B11.1 converts an approved commercial calculation into stable estimate lines.

## Approval gate

Estimate generation requires:

- commercial review status `approved`;
- a concrete approval event;
- zero unresolved commercial items;
- matching project, baseline, price book, adjustment profile and currency;
- matching approved and calculated grand totals.

Crow refuses to generate estimate lines when any gate fails.

## Estimate line fields

Each line contains:

- stable line ID and line number;
- description and cost type;
- quantity and unit;
- unit rate;
- net amount;
- adjustment amount;
- total amount;
- currency;
- immutable fingerprint.

## Provenance

Every estimate line links to:

- commercial impact;
- scope impact;
- technical delta;
- technical decision and review;
- accepted claims;
- authority decisions;
- source documents;
- scope rule;
- price book and unit rate;
- adjustment profile and applied adjustment IDs;
- approved commercial review event.

## Determinism

Lines are ordered by stable commercial impact ID. Fingerprints include the
estimate ID, line number, source impact, amounts and commercial approval event.

## CLI

Build an estimate:

```bash
crow estimate build ./crow-project.json \
  --estimate-id EST-2026-001
```

Optional explicit inputs:

```bash
crow estimate build ./crow-project.json \
  --estimate-id EST-2026-001 \
  --commercial ./crow-commercial-impacts.json \
  --adjusted ./crow-commercial-adjustments.json \
  --review ./crow-commercial-review.json
```

Output:

```text
crow-estimate.json
```

B11.1 creates estimate lines from approved commercial data. It does not yet
provide line grouping, tax, export formats, document rendering or estimate
revision workflows.
