# ADR-003: Stable module boundary

## Status
Accepted

## Decision
Modules depend only on the public Backbone contract and Module SDK. Private Core imports are forbidden and checked statically.

## Consequences
Modules remain independently versionable and replaceable.
