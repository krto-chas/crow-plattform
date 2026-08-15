# Migration from Original RC1

The original CAF RC1 corpus (109 documents in md+docx) is superseded by this package. Mapping:

| Original | Disposition |
|---|---|
| CAF-000/001, CAF-GLS-001/002 | merged → CAF-001 Glossary (with definitions) |
| CAF-002 Architecture Principles | rewritten → CAF-002 (Crow-specific, incl. conventions) |
| CAF-003…009 (Metamodel, Method, Governance, Repository, Capability, Language, Lifecycle) | archived — framework apparatus without Crow content; the living metamodel is the SDK contracts and `docs/` |
| CAF ADR-001…039 (documentation governance series) | archived — the repository ADR series is the only ADR series; surviving conventions folded into CAF-002 |
| CAS-900 | rewritten → index over repository docs |
| CAS-901…904 | archived — replaced by CAF-CMP-001 and repository docs |
| CAS-905…943 incl. duplicate ids CAS-906–910 | archived — replaced by CAF-FUT-001 (duplicates suffixed `-a`/`-b` in the archive for unambiguous reference) |
| CAF-TPL-001, CAF-CMP-002 | archived — replaced by the retained documents' actual form and by CI history + verification manifests |
| All .docx copies | deleted — markdown is the single source |

Future architectural detail belongs in repository documentation (`docs/`), never in CAF.
