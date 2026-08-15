# ADR-008: Crow Decision Language as a future module

## Status
Proposed — deferred until after Backbone stabilization.

## Context
Crow will eventually need reviewable and versioned decision rules that can be maintained separately from Python implementation code.

Introducing a language runtime inside Sprint A would expand the Backbone scope before the public contracts have been validated by a real domain module.

## Decision
Reserve the name **Crow Decision Language (CDL)** and plan it as the independent module `crow.cdl`.

CDL may consume stable SDK and Decision Engine interfaces. Backbone must not depend on CDL and must not contain a CDL parser, AST or runtime.

## Consequences
The concept is preserved without delaying the Foundation Release. Extension points will be validated through ordinary Python-based domain modules first.
