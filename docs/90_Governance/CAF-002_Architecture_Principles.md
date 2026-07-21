# CAF-002 Architecture Principles

1. **Evidence before assumptions.** No claim, decision or release exists without traceable provenance or verification artefacts. What cannot be evidenced is a question to the client, not a fact.
2. **Deterministic behaviour.** Same input produces same output: deterministic identifiers (SHA256), explicit rounding policies, versioned rules. Non-determinism is confined to clearly marked human review.
3. **Explicit authority.** Precedence between conflicting sources is never implicit. Authority policies are declared, versioned and confirmed before they select claims.
4. **Deny by default.** Missing configuration means no access, no acceptance, no pricing — never a silent fallback (ADR-011).
5. **Modules declare intent; Backbone enforces policy.** Modules state capabilities, schemas and permissions in signed manifests. Enforcement, conformance and audit live in one place: the Backbone.
6. **Code is authoritative; documentation explains code.** When documentation and code disagree, the code is right and the documentation has a defect.
7. **No duplicated documentation.** Architecture is described once, in the repository (`docs/`). CAF documents point; they never restate. A document exists only if it carries a decision that was made or is read before performing a task.

## Conventions (folded from archived ADR series)

- **Numbering:** CAF-nnn (framework), CAF-TPL/REL/CMP/FUT-nnn (templates, releases, compliance, roadmap), CAS-9nn (architecture summaries). Identifiers are never reused.
- **Versioning:** documents follow the release they accompany; superseded documents move to `Archive/` unchanged.
- **Status:** every normative statement is either implemented (with code reference) or explicitly marked target architecture.
- **The repository ADR series (ADR-001…) is the only ADR series.**
