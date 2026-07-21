# Sprint B11.3 — Estimate Revision and Versioning

Version: `0.6.0-alpha.22`.

B11.3 adds deterministic comparison between two structured estimates.

The revision engine matches Bill of Quantities rows by the stable
`estimate_line_id` and classifies each row as:

- `added`
- `removed`
- `modified`
- `unchanged`

Modified rows include field-level changes for position, description, quantity,
unit, unit rate, net amount, adjustment amount, total amount and currency.
Each change contains an amount delta and a human-readable explanation.

Revision validation requires matching project, baseline and currency. The sum
of all line deltas must reconcile exactly to the estimate total delta.

CLI:

```bash
crow estimate revision ./crow-project.json \
  --revision-id REV-002 \
  --previous ./estimate-rev-1.json \
  --current ./estimate-rev-2.json
```

Output: `crow-estimate-revision.json`.
