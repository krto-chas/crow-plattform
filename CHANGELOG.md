# Unreleased — 0.7.0 RC readiness governance

- Validated the DXF importer against a controlled real-project aggregate DXF.
- Added explicit reporting for unsupported and malformed/unparsed DXF entities.
- Added RC-010 inventory and acceptance evidence without committing the source drawing.
- Added a regression test ensuring DXF losses cannot be silently omitted.
- Added explicit RC entry criteria for 0.7.0 against CAF-CMP-001.
- Extended CI with architecture review and distribution build gates.
- Aligned the default architecture-review release identity with 0.7.0-alpha.1.
- Added `build` to development dependencies so the packaging gate is reproducible.
- No release-candidate status is declared by these changes.

# Crow Platform 0.7.0-alpha.1 — Konsoliderad och sanerad

- Versionslinjen omnumrerad ärligt: den tidigare "2.0/2.3/2.4"-numreringen saknade
  släppta mellanversioner och ersätts av 0.7.0-alpha ovanpå 0.6.0-alpha.22.
  Kunskapspaketens plattformskrav uppdaterade i enlighet.
- Kvalitetsgrindarna gröna igen: Ruff 0 fel (från ~450), Mypy strict 0 fel i 142
  filer (från 57), 292 tester passerar. Ny kod formaterad till repo-standard.
- `httpx` tillagt som beroende (krävs av FastAPI:s TestClient; tre testfiler
  kunde tidigare inte samlas in).
- `File(...)`-default ersatt med modulnivå-singleton, `str, Enum` → `StrEnum`,
  oanvända variabler och tvetydiga namn åtgärdade.
- Se docs/PROVENANCE.md för härkomst och disposition av samtliga 28 delpaket
  i 0.6.0-RC-samlingen, inklusive varför "crow-platform-3.0-complete" inte ingår.

## Geometry Framework 0.4

- Spatial index summary for normalized geometry.
- Nearest-object and bounding-box queries.
- Generic proximity relations between text, blocks and geometry.
- Workbench inspector shows and navigates nearby objects.
- Geometry API remains source-format neutral.

# Crow Workbench Beta — Geometry Framework 0.3

- Added format-neutral geometry search and index APIs.
- Added DXF ARC, TEXT, MTEXT and INSERT extraction.
- Added text and block indexes with stable Crow Object IDs.
- Added per-object bounds and measurements.
- Added CAD Explorer search by text, kind, layer and Crow-ID.
- Verified with 219 passing tests, Python compileall and JavaScript syntax validation.

# RC0-D1 — Architecture Foundation

- Added architecture documentation set under `docs/00_Architecture`.
- Added system overview, design principles, architectural style and canonical decision pipeline.
- Added security architecture and integrated Backbone authorization as ADR-011.
- Preserved the submitted ADR-010 proposal as a source record.
- Introduced explicit distinction between implemented runtime and accepted target architecture.

# Changelog

## 0.5.0 — Foundation Release

### Release status
- Första fungerande och externt validerade versionen av Crow Backbone.
- Sprint A är avslutad och de publika kontrakten fryses för `0.5.x`.
- Crow Vent Reference Module `0.2.0` har installerats och körts som separat wheel i isolerad miljö.

### Validated
- Entry-point discovery av extern modul.
- Conformance och förbjudna interna importer: PASS.
- Claim → Conflict → AuthorityDecision → TechnicalDelta → CommercialImpact → ÄTA: PASS.
- Referensfall med kommersiellt delta `3 960,00 SEK`: PASS.
- Ruff, Mypy strict, Pytest och architecture review: PASS.

### Changed
- Paketversion, README och CLI-default synkroniserade till `0.5.0`.
- TODO uppdaterad för avslutad Sprint A och kommande Sprint B.
- Release notes, release manifest och final architecture review addendum tillagda.

### Compatibility
- Bakåtkompatibla tillägg får göras inom `0.5.x`.
- Brytande ändringar i publika SDK- eller conformance-kontrakt kräver en ny versionslinje.

## 0.5.0-rc.3

### Fixed
- CI-grindarna är nu gröna: Ruff (0 fel), Mypy strict (0 fel) och Pytest passerar med den workflow som redan fanns.
- `Claim.conflict_key` använder `builtins.property` explicit eftersom fältet `property` skuggar builtin i klasskroppen.
- Konfliktdetektorn normaliserar numeriska värden: `Decimal("1.0")`, `Decimal("1.00")`, `1` och `1.0` flaggas inte längre som falska konflikter. Regressionstest tillagt.
- `CrowProject.execute` narrowar `authority_policy` korrekt och `_updated` är typad så att mypy strict passerar.
- `import_guard` fångar radnummer inom typkontrollerade grenar.
- Kompakt enradsstil i exempelmodulen, konformitetstestet och `test_decision_graph` omskriven till standardstil.

### Added
- `py.typed`-markörer för `crow_module_sdk` och `crow_module_conformance` (PEP 561), inklusive package-data i pyproject.
- `mypy_path`/`explicit_package_bases` så att bare `mypy` fungerar mot src-layouten.

### Changed
- Versionssträngar synkade: README, pyproject (`0.5.0rc3`) och `crow review`-default (`0.5.0-rc.3`).
- ADR-006 noterar att symmetrisk HMAC endast är en referensimplementation och att asymmetrisk signering (t.ex. Ed25519) krävs innan tredjepartsmoduler distribueras.

## 0.5.0-rc.2

### Added
- Future module roadmap for `crow.cdl` and `crow.ckl`.
- ADR-008 reserving Crow Decision Language as a deferred independent module.
- ADR-009 reserving Crow Knowledge Language as a deferred independent module.
- Explicit entry criteria preventing language work before Backbone stabilization.

### Changed
- CDL and CKL are no longer described as Sprint A capabilities.
- Dependency direction is frozen: future language modules may depend on Backbone contracts, never the reverse.
- Release candidate version advanced to `0.5.0rc2`.

## 0.5.0-rc.1

### Added
- Signerade modulmanifest med deterministisk HMAC-SHA256-referensimplementation.
- Trust policy med krav på signerare, algoritmer och signatur.
- Detektion av osignerade, manipulerade och okända modulmanifest.
- Versionsstyrt migrationsregister med explicit migrationsväg.
- Sju ADR:er för Sprint A:s frysta arkitekturbeslut.
- Automatiserad architecture review och CLI-kommandot `crow review`.
- Formell Sprint A-review med kända begränsningar och release recommendation.
- Tester för trust, manipulering, migrationer och release review.

### Changed
- Projektversionen är nu release candidate `0.5.0rc1`.
- Sprint A är feature-frozen; endast defekter och kontraktsförtydliganden återstår före release.

## 0.5.0-alpha.7

### Added
- Transaktionsgräns för projektkörning, projektpersistens och Decision Graphs.
- Unit of Work-kontrakt med commit och rollback.
- In-memory referensimplementation för atomiska körningar.
- Oföränderliga audit events med aktör och strukturerade detaljer.
- Dokumentrevision med automatisk Claim-invalidation.
- Invalidation av tidigare projektkörningar som beror på reviderade källor.
- Krav på ny Claim-extraktion innan projektet åter kan markeras Ready.
- Persistens av audit events och invalidated Claim-ID:n.
- Tester för commit, rollback, revision, invalidation och audit trail.

## 0.5.0-alpha.6

### Added
- `CrowProject` som sammanhållande aggregatrot.
- Projektdokument med roll, revision, checksumma och aktiv status.
- Projektbundna Claims med proveniensvalidering.
- Aktiverade moduler via Module Registry.
- Readiness-validering och projektstatusmodell.
- Projektkörningar med batchresultat och Decision Graph-ID:n.
- Automatisk Human Review-status för olösta authority decisions.
- JSON-persistens för projektets stabila kärndata.
- Tester för projektregler, körning, review-flöde och persistens.

## 0.5.0-alpha.5

### Added
- Modulregister med dubblettskydd.
- Automatisk plugin discovery via `crow.modules` entry points.
- CLI-kommandot `crow module list`.
- Persistenskontrakt för Decision Graph och computation fingerprints.
- JSON-referensimplementationer med versionsmärkt schema.
- Batch pipeline för flera konflikter i samma projekt.
- Tester för register, persistens, discovery-CLI och batchflöde.

## 0.5.0-alpha.4

### Added
- CLI-kommandot `crow module validate`.
- Semantisk versionsmodell och kompatibilitetsintervall.
- AST-baserad kontroll av förbjudna privata Core-importer.
- Deterministisk snapshot-serialisering.
- Committed snapshot för Claim-to-Estimate-exporterna.
- GitHub Actions-workflow för Ruff, Mypy och Pytest.
- CLI-, versions-, import- och snapshot-tester.

## 0.5.0-alpha.3

### Added
- Automatisk Decision Graph-koppling för hela Claim-to-Estimate-flödet.
- Evidence Graph-integritetsvalidering.
- Deterministiska computation fingerprints.
- IdempotencyStore med dubblettskydd.
- Source invalidation genom grafens beroenden.
- Tester för grafspårning, evidensintegritet, idempotens och invalidation.
- Dokumentation för Decision Graph och omberäkning.

## 0.5.0-alpha.2

### Added
- Conflict detector för inkompatibla Claims.
- Validerad AuthorityPolicy med cykel- och motsägelsekontroll.
- Authority Decision och Human Review.
- Accepted Claim.
- Technical Delta.
- Commercial Impact med Decimal och RoundingPolicy.
- ÄTA Opportunity och kommersiella behandlingar.
- Exportobjekt för kalkylrad, beställarfråga och reservation.
- Deterministiska Markdown- och JSON-förklaringar.
- Golden Claim-to-Estimate-test med 18 420 SEK i kostnadsdelta.

## 0.5.0-alpha.1

### Added
- Crow Constitution och Philosophy.
- Domain Handbook.
- Module Contract och certifieringsmodell.
- Första versionen av Crow Module SDK.
- Generisk konformitetsvaliderare.
- Modulmall.
- Syntetisk referensmodul.
- Grundläggande Decision Graph.
- Automatiserade tester.
\n## 0.6.0-alpha.1 — Sprint B1 Document Intake\n- Added CrowDocument, DocumentIndex, PDF intake, classification, revisions and project CLI.\n
## 0.6.0-alpha.2 — Sprint B1.2 Intake Reliability
- Added persistent import sessions and per-file outcomes.
- Added batch error isolation and idempotent re-import.
- Added stable revision ordering.
- Added rule-based document relations.

## 0.6.0-alpha.3 — Sprint B2 Document Model
- Added Page, Region and normalized geometry models.
- Added embedded PDF text extraction and OCR-required detection.
- Added stable page/region locators and persistence.
\n## 0.6.0-alpha.4 — Sprint B3 Observation Engine\n- Added domain-independent observation model and provenance locators.\n- Added text, number, unit, reference, date and heading extractors.\n- Added stable observation fingerprints and duplicate reporting.\n- Added observation persistence and `crow observe`.\n\n## 0.6.0-alpha.5 — Sprint B4 Claim Extraction\n- Added provenance-rich claim candidate model.\n- Added generic key/value, quantity and reference extraction.\n- Added semantic fingerprints, persistence and summaries.\n- Added `crow claims` with automatic observation generation.\n\n## 0.6.0-alpha.6 — Sprint B5 Knowledge Fusion\n- Added semantic clustering across claim candidates.\n- Added singleton, consistent and conflicting fusion states.\n- Added value variants with confidence and document support.\n- Added persistence, summaries and `crow fuse`.\n\n## 0.6.0-alpha.7 — Sprint B7.1 Authority Framework\n- Added default AB 04 document hierarchy.\n- Added project-specific AFC/AFD.111 hierarchy overrides.\n- Added complementarity handling for non-conflicting information.\n- Added latest-date resolution for conflicts within the same rank.\n- Added deterministic decisions, traces, persistence and CLI.\n
## 0.6.0-alpha.8 — Sprint B7.2 Authority Discovery
- Added AB 04/ABT 06 detection.
- Added automatic document authority classification.
- Added AFC/AFD.111 override discovery with evidence.
- Added review flags for ambiguous authority clauses.
- Added discovered manifest generation and CLI.

## 0.6.0-alpha.9 — Sprint B7.3 Accepted Claims
- Added immutable canonical accepted-claims layer.
- Added strict admission from resolved authority decisions only.
- Added pending claims for unresolved or missing decisions.
- Added deterministic IDs, full provenance, persistence and CLI.

## 0.6.0-alpha.10 — Sprint B8.1 Technical Decision Engine Foundation
- Added deterministic rule evaluation over Accepted Claims.
- Added typed conditions and comparison operators.
- Added traceable TechnicalDecisionCandidate records.
- Added rule-set JSON persistence and templates.
- Added CLI commands `crow decide template` and `crow decide run`.
- Kept commercial impact and automatic approval outside the sprint boundary.

## 0.6.0-alpha.11 — Sprint B8.2 Multi-Claim Technical Reasoning
- Added multi-claim selectors and alias binding.
- Added restricted arithmetic expression evaluation.
- Added derived-value comparisons and combined provenance.
- Added confidence propagation using the weakest contributing claim.
- Added explicit missing-input and invalid-input evaluations.

## 0.6.0-alpha.12 — Sprint B8.3 Technical Validation
- Added validation profiles over Accepted Claims.
- Added missing-information, invalid-value, low-confidence and ambiguity issues.
- Added blocking validation severity and deterministic issue fingerprints.
- Added technical validation CLI, persistence and profile template.

## 0.6.0-alpha.13 — Sprint B8.4 Technical Review
- Added human review records for decisions and validation issues.
- Added approved, rejected, needs-information and superseded states.
- Added immutable audit events with reviewer, reason and timestamps.
- Added constrained state transitions and blocking validation gate.
- Added review CLI and persistence.

## 0.6.0-alpha.14 — Sprint B9.1 Technical Delta Foundation
- Added explicit technical baseline model and template.
- Added deterministic comparison of approved decisions against baseline.
- Added added, removed, modified and unchanged delta classifications.
- Added provenance linking baseline, review event, decision, claims and documents.
- Added delta CLI, persistence and summary.

## 0.6.0-alpha.15 — Sprint B9.2 Structured Delta Semantics
- Added object, property, value-kind and quantity semantics to baselines and deltas.
- Added signed numeric quantity deltas and change direction classification.
- Propagated structured values from single-claim and multi-claim decisions.
- Added backward-compatible persistence defaults for existing delta artifacts.

## 0.6.0-alpha.16 — Sprint B9.3 Quantity and Scope Impact
- Added deterministic scope-impact derivation from technical deltas.
- Added added, omitted, changed, unchanged and review-required scope classes.
- Added configurable quantity bases, multipliers and fixed quantities.
- Added full provenance from scope impact to delta, decision and source documents.
- Added scope CLI, persistence, rule template and summary.

## 0.6.0-alpha.17 — Sprint B10.1 Commercial Impact Foundation
- Added deterministic conversion from scope impacts to commercial impacts.
- Added versioned price books and unit-rate matching.
- Added explicit pricing statuses for missing quantity, rate and review.
- Added labour, material, equipment, subcontract and other cost types.
- Added commercial CLI, persistence, summaries and full provenance.

## 0.6.0-alpha.18 — Sprint B10.2 Commercial Adjustments
- Added percentage and fixed commercial adjustments.
- Added markup, discount, index, risk and other adjustment kinds.
- Added deterministic net-amount and running-total calculation bases.
- Added separate net, adjustment and grand totals.
- Added commercial adjustment CLI, persistence and summaries.

## 0.6.0-alpha.19 — Sprint B10.3 Commercial Review and Approval
- Added human review lifecycle for adjusted commercial calculations.
- Added immutable commercial review events and constrained transitions.
- Added unresolved-item approval gate.
- Added commercial review CLI, persistence and summaries.

## 0.6.0-alpha.20 — Sprint B11.1 Estimate Line Foundation
- Added estimate generation gated by approved commercial review.
- Added stable estimate lines with quantity, unit rate, adjustments and totals.
- Added cross-artifact validation for project, baseline, price book and currency.
- Added full provenance from estimate line back to source documents.
- Added estimate CLI, persistence and summaries.

## 0.6.0-alpha.21 — Sprint B11.2 Estimate Structure and BoQ
- Added deterministic sections, groups and Bill of Quantities lines.
- Added hierarchical positions and validated subtotals.
- Added grouping profiles with priority ordering and fallback classification.
- Added aggregated line and document provenance at group and section level.
- Added estimate structure CLI, template, persistence and summaries.

## 0.6.0-alpha.22 — Sprint B11.3 Estimate Revision and Versioning
- Added deterministic structured-estimate revision comparison.
- Added added, removed, modified and unchanged line classifications.
- Added field-level changes, amount deltas and explanations.
- Added revision fingerprints and source-structure provenance.
- Added reconciliation of line deltas against the estimate total delta.
- Added JSON persistence, summaries, CLI and integration tests.

## Geometry Framework 0.5
- Topology graph for LINE and POLYLINE geometry.
- Connectivity API, components, dangling ends and junction detection.

## Geometry Framework 0.6
- Network tracing from any topology-bearing geometry object.
- Depth-limited traversal and optional stop-at-junction behavior.
- Branch-to-branch network segmentation with lengths and source objects.
- Workbench APIs for traces and network segments.

## Crow Vent 0.1

- Added `crow_vent` domain module.
- Added initial Swedish ventilation component registry.
- Added evidence-based candidate classification and confidence status.
- Added Vent system aggregation and review API.
- Added Vent Explorer to Crow Workbench.

## Crow Platform 2.0 – Building Graph RC1 Sprint 2

- Added domain-neutral building structure service for buildings, floors, spaces and zones.
- Added validated hierarchy creation with `contains`, `located_in` and `belongs_to` relations.
- Added room area properties with unit and evidence support.
- Added deterministic IDs for building structure objects.
- Added building structure tree and summary API.
- Added REST endpoints for buildings, floors, spaces and zones.
- Added validation for parent types, missing spaces and negative room area.
- Test suite: 247 passed.


## 2.0.0-rc1-sprint3
- Added domain-neutral technical system graph.
- Added system hierarchy, building location and service relations.
- Added system-to-system links and downstream impact traversal.
- Added System Graph REST API and regression tests.

## 2.0.0-rc1 Sprint 4

- Added domain-neutral Component Graph.
- Added technical components, system membership, building placement and component relations.
- Added evidence-bearing technical properties and downstream component tracing.
- Added Component Graph REST API and regression tests.

## 2.3.0-rc1 Reasoning Engine Sprint 3

- Added persistent finding repository with atomic JSON writes.
- Added deterministic finding deduplication and occurrence tracking.
- Added lifecycle states: open, acknowledged, resolved and dismissed.
- Added automatic resolution when a rule no longer triggers and reopening on recurrence.
- Added audit history, assignee and reviewer notes.
- Added filtering, severity/status statistics and CSV export.
- Added Workbench endpoints for synchronization, lifecycle updates, history and export.

## 2.3.0rc1-sprint4
- Added data-only Knowledge Pack Runtime.
- Added manifest/dependency/ontology validation and runtime registry.
- Added Crow Vent 1.0.0-rc1 example pack and Workbench evaluation API.

## 2.4.0-rc1 — Inference Engine Sprint 1

- Transitiv inferens, förklaringskedjor och confidence-propagation.
- Konfliktdetektering och separat inferenssnapshot.
- API för körning och förklaring av härledda relationer.

## 2.4.0-rc1 — Inference Engine Sprint 2

- Added iterative rule chaining with a bounded execution plan.
- Added evidence fusion across explicit and derived relation chains.
- Added spatial/system inference support through data-driven transitive rules.
- Added query and conflict APIs for derived facts.
- Upgraded inference snapshot schema to `crow-inference-v0.2`.

## 2.4.0-rc1 — Inference Engine Sprint 4

- Added persistent human review lifecycle for derived relations.
- Added accepted, rejected and promoted inference states with audit history.
- Added guarded promotion of accepted derived facts into the verified Building Graph.
- Added provenance metadata linking promoted graph relations to inference run, rule and reviewer.
- Added automatic inference invalidation after promotion.
- Added review listing, decision and promotion REST APIs.

## RC-readiness pass 20 — explicit IFC relationship expansion

- Extended `crow_ifc_relations` with explicit mappings for:
  - `IfcRelDefinesByType` → `typed_by`
  - `IfcRelAssignsToGroup` → `assigned_to`
  - `IfcRelServicesBuildings` → `serves`
  - `IfcRelAssociatesMaterial` → `associated_with_material`
  - `IfcRelCoversBldgElements` → `covers`
- Added the corresponding canonical relation types.
- Preserved the existing two-stage mapping requirement: both IFC endpoints must already
  have explicit IFC-to-CCM identifiers before an assertion is created.
- No geometry, proximity, inferred flow direction, object creation, or automatic correction
  is performed.

## RC-readiness pass 24

- Added a general evidence-integrity rules package on top of `crow_evidence_index` and `crow_graph_rules`.
- Added deterministic findings for missing references, duplicate evidence IDs, checksum conflicts and unreferenced evidence.
- Added the read-only Workbench endpoint `GET /api/projects/{project_id}/graph/evidence-audit`.
- No automatic repair, checksum selection, graph mutation or evidence mutation is performed.

## RC-readiness pass 28

- Added persistent manual review of findings in immutable evidence-audit runs.
- Added `acknowledge`, `mark_resolved`, and `dismiss` decisions with reviewer, rationale,
  timestamp, graph checksum, ruleset version, and an immutable finding snapshot.
- Added review history and duplicate-decision protection.
- Evidence-audit comparisons now expose prior base-audit review context without mutating
  either audit, the Building Graph, or the evidence registry.
