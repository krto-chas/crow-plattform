# CAF-TPL-002 ADR Template

The repository ADR series (`docs/adr/ADR-nnn-<slug>.md`) is the only ADR series. New decisions use the next free number and this structure, which matches ADR-001…ADR-011:

```markdown
# ADR-nnn: <Decision title>

## Status
Proposed | Accepted | Superseded by ADR-mmm
(For target architecture: state what is implemented today and what is scheduled.)

## Context
Why the decision is needed. Constraints and forces, referencing real packages,
contracts or incidents — not hypotheticals.

## Decision
The decision itself, stated so it can be violated (and therefore verified).
Include code-level shapes (dataclasses, entry points, commands) where they exist.

## Consequences
What becomes easier, what becomes harder, what it costs.
Breaking changes name the version line they require.

## Out of scope
What this ADR deliberately does not decide.
```

Rules: one decision per ADR; superseding never edits history — write a new ADR and update the old one's status; every normative claim in an accepted ADR must be either implemented or explicitly marked target.
