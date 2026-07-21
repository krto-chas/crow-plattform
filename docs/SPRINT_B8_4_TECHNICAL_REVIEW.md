# Sprint B8.4 — Technical Review and Decision Approval

Version: `0.6.0-alpha.13`.

B8.4 adds a human review workflow for technical decision candidates and
technical validation issues.

## Statuses

- `proposed`
- `approved`
- `rejected`
- `needs_information`
- `superseded`

## Audit model

Every state change creates an immutable `ReviewEvent` containing:

- target and target type;
- previous and new status;
- reviewer;
- mandatory reason;
- timezone-aware timestamp;
- previous event reference;
- deterministic fingerprint.

The current status is stored in a `ReviewRecord`, while the complete event
history remains available for audit.

## Transition constraints

Normal review states cannot be rewritten arbitrarily. Approved or rejected
records can only be superseded. Superseded records are terminal.

## Validation gate

Unresolved blocking validation issues prevent the technical approval gate from
opening. A blocking issue must be explicitly approved or rejected by a reviewer;
Crow never silently ignores it.

## CLI

Initialize review records:

```bash
crow review init ./crow-project.json
```

Set a review status:

```bash
crow review set ./crow-project.json <target-id> approved \
  --reviewer "name@example.com" \
  --reason "Technically verified against accepted project data."
```

Output:

```text
crow-technical-reviews.json
```
