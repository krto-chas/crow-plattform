# Sprint B10.3 — Commercial Review and Approval

Version: `0.6.0-alpha.19`.

B10.3 introduces a separate human review lifecycle for the adjusted commercial
calculation.

## Statuses

- `proposed`
- `approved`
- `rejected`
- `needs_information`
- `superseded`

## Approval gate

A commercial calculation cannot be approved while unresolved commercial items
remain. Approval therefore requires:

```text
unresolved_count == 0
```

The review captures the project, baseline, price book, adjustment profile,
currency and grand total that were presented for approval.

## Immutable events

Every transition creates an immutable event containing:

- previous and new status;
- reviewer;
- reason;
- timezone-aware timestamp;
- prior event reference;
- deterministic fingerprint.

Approved and rejected reviews can only transition to `superseded`. Superseded
reviews are terminal.

## CLI

Initialize review:

```bash
crow commercial review-init ./crow-project.json
```

Optional adjusted source:

```bash
crow commercial review-init ./crow-project.json \
  --adjusted ./crow-commercial-adjustments.json
```

Update review:

```bash
crow commercial review-set ./crow-project.json approved \
  --reviewer "Commercial Manager" \
  --reason "Calculation and supporting evidence verified."
```

Output:

```text
crow-commercial-review.json
```

An approved commercial review becomes the gate for later estimate-line and
decision-package generation.
