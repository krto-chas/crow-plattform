# CAF-001 Glossary

Normative terminology for Crow. Where a term is implemented in code, the code is authoritative.

## Pipeline vocabulary

**Document** — An imported source file (PDF, drawing, specification) with identity (SHA256), revision and role. Implemented in `crow_document_intelligence`.

**Observation** — A source-bound structured finding extracted from a document region, carrying provenance down to character offsets. Implemented in `crow_observation_engine`.

**Claim** — A domain assertion about the project extracted from documents: subject, property, value, unit and provenance (e.g. "duct S01 diameter = 125 mm per drawing K-57-1-001 rev A"). Implemented as `crow_module_sdk.Claim`. Not to be confused with security token claims, which belong to the authorization model (ADR-011).

**ClaimCandidate** — A claim proposal produced by extraction that has not yet been accepted as decision-grade knowledge. Implemented in `crow_claim_extraction`.

**KnowledgeCluster** — A grouping of claims about the same subject and property, classified as SINGLETON, CONSISTENT or CONFLICTING. Implemented in `crow_knowledge_fusion`.

**Authority** — The explicit, versioned rule set that determines which source prevails when claims conflict (e.g. "I/O-listan gäller före driftkort"). Implemented in `crow_authority` and `crow_authority_discovery`.

**AcceptedClaim** — A claim promoted to decision-grade knowledge after fusion and authority resolution. Implemented in `crow_accepted_claims`.

**TechnicalDelta** — The structured difference between a technical decision and a project baseline, supporting numeric, text, boolean and enum values. Implemented in `crow_technical_delta`.

**ScopeImpact** — The change in scope or quantity implied by a technical delta. Implemented in `crow_scope_impact`.

**CommercialImpact / ÄTA** — The economic consequence of a scope impact, expressed in SEK; the basis for ÄTA (ändrings-, tilläggs- och avgående arbeten). Implemented in `crow_commercial_impact`.

**EstimateLine / EstimateStructure / EstimateRevision** — Atomic priced lines, their deterministic grouping, and the comparison of two structured estimates (added / removed / modified / unchanged with total delta). Implemented in `crow_estimate_line`, `crow_estimate_structure`, `crow_estimate_revision`.

## Platform vocabulary

**Backbone** — The domain-neutral platform core: contracts, conformance, authority, audit, persistence and (target) authorization enforcement.

**Module** — A separately distributed component implementing the plugin contract, discovered via the `crow.modules` entry point, declaring its capabilities in a signed manifest.

**Manifest** — A module's signed self-description (`ModuleManifest`): identity, version, domain, compatibility ranges and (target, ADR-011) declared permissions.

**Conformance** — Mechanical verification that a module or repository satisfies its contract: `crow module validate`, `crow review`, and the CI gates in CAF-CMP-001.

**Evidence** — Objective, verifiable information supporting a decision: provenance, verification JSON files, audit events. No claim, decision or release without evidence.

**Provenance** — The traceable origin of a piece of information: document, revision, page, location. Implemented as `crow_module_sdk.Provenance`.

**Audit trail** — The append-only record of project events and (target) authorization denials and administrative changes.
