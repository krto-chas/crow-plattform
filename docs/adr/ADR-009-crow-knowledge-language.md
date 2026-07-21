# ADR-009: Crow Knowledge Language as a future module

## Status
Proposed — deferred until after Backbone stabilization.

## Context
Crow may need a common way to define entities, properties, units, relationships and controlled domain vocabularies across multiple modules.

Embedding a knowledge language in Backbone now would risk coupling the foundation to an unvalidated modelling approach.

## Decision
Reserve the name **Crow Knowledge Language (CKL)** and plan it as the independent module `crow.ckl`.

CKL may publish versioned knowledge packages through stable module contracts. Backbone must remain unaware of CKL syntax and internal representation.

## Consequences
Knowledge modelling can evolve independently. Initial domain modules remain free to prove which abstractions are genuinely reusable.
