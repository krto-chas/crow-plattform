# Sprint B9.3 — Quantity and Scope Impact

Version: `0.6.0-alpha.16`.

B9.3 converts structured technical deltas into explicit scope impacts.

## Scope impact types

- `added_work`
- `omitted_work`
- `changed_work`
- `no_scope_change`
- `review_required`

## Rule model

A scope-impact rule may match:

- category;
- property name;
- change direction.

It then defines:

- scope-impact type;
- quantity basis;
- output unit;
- multiplier or fixed quantity;
- description template;
- priority and version.

Quantity bases:

- `delta_quantity`
- `approved_quantity`
- `baseline_quantity`
- `fixed`
- `none`

## Deterministic defaults

When no rule matches:

- added delta becomes added work;
- removed delta becomes omitted work;
- unchanged delta becomes no scope change;
- quantified modification becomes changed work;
- unquantified modification becomes changed work requiring review.

Crow does not invent quantities.

## Provenance

Every scope impact links back to:

- technical delta;
- baseline item;
- approved technical decision;
- review event;
- accepted claims;
- authority decisions;
- source documents;
- applied scope rule.

## CLI

Create a scope rule template:

```bash
crow scope template ./crow-scope-rules.json
```

Build scope impacts:

```bash
crow scope build ./crow-project.json \
  --rules ./crow-scope-rules.json
```

Optional explicit delta input:

```bash
crow scope build ./crow-project.json \
  --rules ./crow-scope-rules.json \
  --deltas ./crow-technical-deltas.json
```

Output:

```text
crow-scope-impacts.json
```

B9.3 describes quantity and scope impact only. It does not assign prices,
contractual entitlement or commercial approval.
