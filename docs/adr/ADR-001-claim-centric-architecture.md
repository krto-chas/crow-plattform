# ADR-001: Claim-centric architecture

## Status
Accepted

## Context
Crow must combine conflicting information from drawings, specifications, AF documents and other sources.

## Decision
All extracted facts are represented as Claims with provenance. Conflicts, authority decisions and downstream commercial effects reference Claim IDs.

## Consequences
Traceability is preserved from estimate output back to source material. Modules must not bypass Claims.
