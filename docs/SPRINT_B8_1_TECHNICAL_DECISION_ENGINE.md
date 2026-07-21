# Sprint B8.1 — Technical Decision Engine Foundation

Version: `0.6.0-alpha.10`.

B8.1 introduces a deterministic, domain-independent rule engine operating only
on canonical `AcceptedClaim` objects.

## Boundary

The engine emits proposed `TechnicalDecisionCandidate` records. It does not:

- alter accepted claims;
- calculate price or commercial impact;
- silently approve engineering changes;
- evaluate unresolved claims;
- replace human technical responsibility.

## Rule model

A rule contains:

- stable ID and version;
- priority and enabled state;
- one or more AND-combined conditions;
- output category, severity, title, conclusion and recommended action;
- source describing where the technical rule came from.

Supported operators:

- `equals`
- `not_equals`
- `contains`
- `greater_than`
- `greater_than_or_equal`
- `less_than`
- `less_than_or_equal`
- `exists`
- `regex`

## Provenance

Every emitted candidate records:

- accepted claim ID;
- authority decision ID;
- knowledge cluster ID;
- source document IDs;
- rule and rule-set IDs;
- rule version;
- complete evaluation trace.

## CLI

Create a rule template:

```bash
crow decide template ./crow-technical-rules.json
```

Evaluate accepted claims:

```bash
crow decide run ./crow-project.json --rules ./crow-technical-rules.json
```

Optional explicit accepted-claims file:

```bash
crow decide run ./crow-project.json \
  --rules ./crow-technical-rules.json \
  --accepted ./crow-accepted-claims.json
```

Output:

```text
crow-technical-decisions.json
```
