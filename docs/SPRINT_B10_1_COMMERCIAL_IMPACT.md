# Sprint B10.1 — Commercial Impact Foundation

Version: `0.6.0-alpha.17`.

B10.1 converts scope impacts into traceable commercial impact records.

## Pricing statuses

- `priced`
- `missing_quantity`
- `missing_unit_rate`
- `review_required`
- `not_applicable`

Crow does not invent a price or quantity. Missing commercial inputs remain
explicit unresolved states.

## Price book

A price book contains deterministic unit-rate records. Each rate can match:

- category;
- property name;
- scope-impact type;
- unit.

A matched rate defines:

- cost type;
- currency;
- unit rate;
- description;
- priority and version.

Cost types:

- `labour`
- `material`
- `equipment`
- `subcontract`
- `other`

## Calculation

For a priced item:

```text
amount = quantity × unit_rate
```

The calculation is performed only when:

- the scope item does not require review;
- quantity exists;
- a matching unit rate exists.

## Provenance

Each commercial impact links to:

- scope impact;
- technical delta;
- approved technical decision;
- review event;
- accepted claims;
- authority decisions;
- source documents;
- scope rule;
- price book and unit rate.

## CLI

Create a price-book template:

```bash
crow commercial template ./crow-price-book.json
```

Build commercial impacts:

```bash
crow commercial build ./crow-project.json \
  --price-book ./crow-price-book.json
```

Optional explicit scope input:

```bash
crow commercial build ./crow-project.json \
  --price-book ./crow-price-book.json \
  --scope ./crow-scope-impacts.json
```

Output:

```text
crow-commercial-impacts.json
```

B10.1 establishes deterministic commercial impact records. It does not yet
apply contractual entitlement, markup, tax, escalation, risk allowance or
commercial approval.
