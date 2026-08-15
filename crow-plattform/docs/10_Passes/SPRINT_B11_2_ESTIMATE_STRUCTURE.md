# Sprint B11.2 — Estimate Structure and Bill of Quantities

Version: `0.6.0-alpha.21`.

B11.2 converts a flat approved estimate into a deterministic hierarchy:

`StructuredEstimate → EstimateSection → EstimateGroup → BillOfQuantityLine`.

Grouping is controlled by an explicit JSON profile. Rules are evaluated by
priority and stable rule ID. Every source estimate line must occur exactly once.

The structured estimate provides hierarchical positions, section and group
subtotals, aggregated document provenance and a stable structure fingerprint.

CLI:

```bash
crow estimate structure-template ./estimate-structure.json
crow estimate structure ./crow-project.json \
  --structure-id STRUCTURE-001 \
  --profile ./estimate-structure.json
```

Output: `crow-structured-estimate.json`.
