# Sprint B9.2 — Structured Technical Delta Semantics

Version: `0.6.0-alpha.15`.

B9.2 extends technical deltas with structured engineering semantics.

## Structured fields

A baseline item and resulting delta can now carry:

- object reference;
- property name;
- value kind;
- prior and approved quantities;
- unit;
- signed quantity delta;
- change direction.

Value kinds:

- `text`
- `number`
- `boolean`
- `enum`

Change directions:

- `increase`
- `decrease`
- `changed`
- `added`
- `removed`
- `unchanged`

## Decision propagation

Technical decision candidates now retain structured values from their accepted
claims. Single-claim rules propagate subject, predicate, value, unit and numeric
quantity. Multi-claim rules propagate their calculated numeric result.

## Numeric example

Baseline:

```text
object_ref: AHU-03
property_name: air_velocity
value: 5.0
unit: M/S
```

Approved decision:

```text
value: 8.0
unit: M/S
```

Delta:

```text
baseline_quantity: 5.0
approved_quantity: 8.0
quantity_delta: 3.0
change_direction: increase
```

Text and enum changes remain structured but receive the generic direction
`changed` when no meaningful arithmetic delta exists.

B9.2 still does not calculate commercial impact. It establishes the semantic
technical change record consumed by later quantity and pricing stages.
