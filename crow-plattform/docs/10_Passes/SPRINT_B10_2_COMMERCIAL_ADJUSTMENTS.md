# Sprint B10.2 — Commercial Adjustments

Version: `0.6.0-alpha.18`.

B10.2 applies explicit commercial adjustments to already priced commercial
impact records.

## Adjustment kinds

- `markup`
- `discount`
- `index`
- `risk`
- `other`

## Adjustment types

- `percentage`
- `fixed_amount`

A negative percentage or fixed amount represents a deduction.

## Calculation bases

- `net_amount`
- `running_total`

Rules are applied deterministically in ascending priority and then stable rule
ID order. A rule based on `running_total` includes adjustments applied before
it.

Example:

```text
net amount       1,000
10% markup         100
running total    1,100
5% risk             55
grand total      1,155
```

Only commercial impacts with pricing status `priced` are adjusted. Unresolved
commercial items remain unresolved and are counted separately.

## CLI

Create a profile:

```bash
crow commercial adjustment-template ./crow-adjustments.json
```

Apply adjustments:

```bash
crow commercial adjust ./crow-project.json \
  --profile ./crow-adjustments.json
```

Optional explicit commercial source:

```bash
crow commercial adjust ./crow-project.json \
  --profile ./crow-adjustments.json \
  --commercial ./crow-commercial-impacts.json
```

Output:

```text
crow-commercial-adjustments.json
```

B10.2 calculates net, adjustment and grand totals. Contractual entitlement,
tax, formal approval and final estimate-line generation remain separate stages.
