# Sprint A Architecture Review

## Review target
`0.5.0`

## Scope completed

- claim-centric domain foundation,
- provenance and evidence integrity,
- conflict and authority resolution,
- technical and commercial decision pipeline,
- Decision Graph,
- idempotency and invalidation,
- module contract, registry and discovery,
- project aggregate and transaction boundary,
- audit and document revision,
- signed manifest trust policy,
- versioned migration policy,
- CLI, snapshots and CI.

## Architectural assessment

The foundation is internally coherent and module-oriented. The highest-risk decisions are
explicitly recorded as ADRs. Human Review remains mandatory where document authority is not
confirmed. Commercial outputs remain traceable to source Claims.

## Known limitations accepted for RC1

- HMAC signing is a reference implementation, not a public marketplace signing model.
- JSON repositories are reference adapters, not production concurrency solutions.
- Batch pricing input is supplied externally.
- Project run persistence excludes full historical run reconstruction in the JSON project adapter.
- Ruff and Mypy are delegated to CI where dependencies are installed.

## Release recommendation

Proceed to `0.5.0-rc.1` for integration testing against the first real domain module.
No new foundation capabilities should be added before RC feedback; only defects, contract
clarifications and migration fixes should enter Sprint A.


## Deferred architecture concepts

Crow Decision Language (CDL) and Crow Knowledge Language (CKL) are recorded as future independent modules.

They are explicitly excluded from Sprint A runtime scope. This preserves the dependency direction:

```text
CDL / CKL / domain modules -> stable Backbone contracts
Backbone -X-> CDL / CKL internals
```

The first real domain-module integration will be used to validate extension points before either language is designed in detail.


## Final release addendum — 0.5.0

The release candidate was validated against Crow Vent Reference Module `0.2.0` as an independently packaged wheel. The module was discovered through the public entry-point contract, passed conformance and import-boundary checks, and completed the end-to-end commercial reference scenario.

Final recommendation: **RELEASE**.

The `0.5.x` public SDK and conformance surface is now considered stable. Sprint B may add document-intelligence capabilities without moving PDF, OCR, AI, CDL or CKL concerns into Backbone Core.
