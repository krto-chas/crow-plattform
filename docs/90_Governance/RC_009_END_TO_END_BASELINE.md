# RC-009 — Deterministic end-to-end baseline

## Scope

This gate verifies the existing, public claim-to-estimate reference pipeline. It does
not claim coverage of CAD import or Workbench behavior; those are governed separately.

## Command

```bash
python scripts/verify_e2e_baseline.py
```

The verifier executes the same pipeline twice in a fresh process, compares both
results, and compares the result against the committed baseline:

`evidence/rc-009/claim_to_estimate_reference_v1.json`

The baseline records deterministic identifiers, selected claim, technical delta,
commercial amount, generated estimate/question/reservation and evidence identifiers.
A canonical SHA-256 digest covers the result payload.

## Change control

The baseline must not be regenerated merely to make CI green. Any intentional change
requires review of the semantic output and a corresponding changelog entry. To create
a candidate result for review:

```bash
python scripts/verify_e2e_baseline.py --write
```

The generated diff is the evidence to review. A passing test alone is not approval of
changed business behavior.
