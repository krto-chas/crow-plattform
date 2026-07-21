# Sprint B8.2 — Multi-Claim Technical Reasoning

Version: `0.6.0-alpha.11`.

B8.2 extends the technical decision engine so a rule may combine several
canonical `AcceptedClaim` records.

## Model

A `MultiClaimRule` contains:

- selectors that bind accepted claims to named aliases;
- a restricted arithmetic expression;
- a comparison and expected threshold;
- a traceable technical decision output.

Selectors may constrain:

- subject or subject regular expression;
- predicate;
- unit;
- semantic-key content;
- minimum confidence.

## Safe expressions

Expressions support numeric constants, aliases, parentheses and:

- addition;
- subtraction;
- multiplication;
- division;
- exponentiation;
- unary plus and minus.

Function calls, imports, attribute access and arbitrary Python execution are
rejected.

## Example

For accepted claims:

- airflow = 400 L/s;
- duct area = 0.05 m².

The rule evaluates:

```text
(airflow / 1000) / area = 8 m/s
```

A configured limit of 5 m/s therefore emits a proposed technical decision.

## Provenance

The candidate retains all participating accepted-claim, authority-decision,
knowledge-cluster and document IDs. Candidate confidence is the lowest
confidence among its contributing claims.

## Boundaries

The engine still emits proposed technical decisions only. B8.2 does not approve
changes, select products, calculate prices or generate estimate lines.
