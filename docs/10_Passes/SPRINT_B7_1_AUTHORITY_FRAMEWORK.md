# Sprint B7.1 — Authority Framework

Version: `0.6.0-alpha.7`.

B7.1 introduces a deterministic authority engine for resolving contradictory
claim variants. It separates three concerns:

1. **Consistency:** whether values actually contradict each other.
2. **Complementarity:** information present in only one document remains part
   of the project scope when no contradictory value exists.
3. **Authority:** when values conflict, the configured document hierarchy
   determines which source has precedence.

## Default AB 04 hierarchy

Highest authority first:

1. Contract
2. Changes to AB 04 listed in AF
3. AB 04
4. Order
5. Tender
6. Special measurement and compensation rules
7. Unit-price list / priced bill of quantities
8. Supplementary provisions issued before tender
9. Administrative specifications
10. Unpriced bills of quantities
11. Technical descriptions
12. Drawings
13. Other documents

Technical descriptions therefore outrank drawings when their statements
contradict one another.

## Complementarity

The hierarchy is only evaluated for conflicting value variants. A unique
statement is accepted as complementary information; it is not discarded merely
because a higher-ranked document is silent.

## Same-rank conflict

When conflicting documents have the same authority type, the latest issue date
wins. If date metadata is absent or tied, the case remains unresolved.

## Project override

A project manifest can provide an alternative hierarchy sourced from, for
example, `AFC.111` or `AFD.111`. B7.1 consumes this override explicitly.
Automatic discovery from AF text belongs to B7.2.

## CLI

Create a manifest template:

```bash
crow authority template ./crow-authority-manifest.json
```

Resolve a project:

```bash
crow authority resolve ./crow-project.json \
  --manifest ./crow-authority-manifest.json
```

Output:

```text
crow-authority-resolution.json
```
