# ADR-005: Transactional project runs

## Status
Accepted

## Decision
Project state and all generated Decision Graphs are persisted atomically through a Unit of Work.

## Consequences
Partial runs are never exposed after failure.
