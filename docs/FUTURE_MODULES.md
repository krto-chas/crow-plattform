# Future Modules

This document records planned Crow modules that are intentionally outside the Sprint A Backbone scope.

The purpose is to preserve architectural intent without allowing future concepts to destabilize the foundation release.

## Backbone first

Sprint A closes only when the following foundation is stable:

- Claim and provenance contracts
- Evidence and Decision Graphs
- Authority and Human Review
- Technical and commercial decision flow
- Module SDK and conformance
- Project aggregate
- Transactions and audit
- Trust and migration policy
- Public API and compatibility boundaries

No future language or intelligence module may introduce a new dependency from Backbone to a domain module.

## Crow Decision Language — CDL

**Planned module:** `crow.cdl`

**Status:** Proposed and deferred.

CDL will describe executable decision rules as versioned, testable and signable data.

Potential responsibilities:

- authority rules
- technical rules
- commercial rules
- validation rules
- knowledge-fusion rules
- parsing and validation
- rule AST
- rule packages
- rule signing
- deterministic execution adapters

CDL will consume stable Backbone interfaces. Backbone will not depend on CDL.

## Crow Knowledge Language — CKL

**Planned module:** `crow.ckl`

**Status:** Proposed and deferred.

CKL will describe domain knowledge independently of executable rules.

Potential responsibilities:

- entity types
- properties and units
- relationships
- taxonomies
- controlled vocabularies
- domain schemas
- knowledge package versioning
- knowledge package signing

CKL will provide knowledge models to modules such as Vent, VS, El, Geo, Dog and Compliance.

## Intended separation

```text
CKL
  describes what Crow knows

CDL
  describes how Crow evaluates rules

Backbone
  provides execution, provenance, decisions and auditability
```

## Entry criteria

CDL or CKL work may start only when:

1. Backbone public contracts are frozen for the relevant 0.5.x line.
2. A real domain module has validated the current extension points.
3. The architecture review finds no need to move language-specific concerns into Core.
4. Rule and knowledge packages can be represented without bypassing Claim provenance.
5. Human Review remains available for unresolved authority or interpretation.

## Non-goals for Sprint A

Sprint A does not include:

- a CDL parser
- a CKL parser
- a rule compiler
- a language runtime
- a rule marketplace
- AI-generated production rules
- automatic legal or contractual precedence decisions
