# CROW – inventering av befintlig arkitektur, idéer och återanvändbara komponenter

**Datum:** 2026-11-21  
**Status:** första breda inventering och riktad källgranskning; inte fullständig rad-för-rad-revision  
**Underlag:** Git-trädet för `main` (1 323 trädposter, 1 173 filer), centrala arkitekturdokument, governance, ADR, modulkontrakt, produktroadmap och utvalda implementationer.  
**Ägare/beslut:** produktägaren  
**Syfte:** bevara och återupptäcka befintliga idéer innan nya moduler, arkitekturer och masterpromptar skapas.

## 1. Sammanfattning
Repot är **inte** ett tomt modulskal. Det innehåller en betydande Decision Intelligence-arkitektur med proveniens, claim/authority/review, grafmodeller, import, tekniska beslut, assurance, revisionsspår och modulkonformitet. En ny GRC- eller Security-modul får inte duplicera dessa förmågor.

Samtidigt är stora delar av plattformens flerorganisationssäkerhet **målarkitektur** och flera gamla dokument är **arkiverade och ersatta**. Skilj implementerat, accepterad målarkitektur, föreslaget, arkiverat och historiskt. Att en fil finns är inte ett bevis på att funktionen är produktionsklar.

## 2. Översikt av hela filträdet
Inventering via rekursivt Git-träd för `main`:
- 1 173 filer, 1 323 poster inklusive kataloger.
- `docs/`: 370 filer, inklusive `00_Architecture/` (13), `10_Passes/` (91), `90_Governance/` (143), `verification/` (59), `adr/` (12), produktroadmaps och kontrakt.
- `src/`: 289 filer, cirka 225 Pythonfiler, fördelade på ett stort antal `crow_*`-paket.
- `modules/`: 267 filer, varav OVK 167, Vent 72 och Pressure Test 27.
- `tests/`: 139 filer; totalt 212 filer i trädet matchar `test_*.py` under valfri katalog.
- `dist/`: 30 filer; `deploy/`: 17; `scripts/`: 11; `knowledge/`: 5; `evidence/`: 13.
- `.github/workflows/`: tre workflows; `.claude/` och `.codex/` har separata reviewer/verifier-konfigurationer.

**Begränsning:** Filträdet är fullständigt inventerat vid kontrollen. Endast utvalda filers innehåll är läst; ingen fullständig analys av samtliga 1 173 filer eller körning av testsviten har gjorts.

## 3. Arkitekturen som måste läsas först
`docs/00_Architecture/README.md` ger uttrycklig läsordning:
1. [The Crow Philosophy](../00_Architecture/THE_CROW_PHILOSOPHY.md)
2. [Architecture](../00_Architecture/ARCHITECTURE.md)
3. [System Overview](../00_Architecture/SYSTEM_OVERVIEW.md)
4. [Design Principles](../00_Architecture/DESIGN_PRINCIPLES.md)
5. [Architectural Style](../00_Architecture/ARCHITECTURAL_STYLE.md)
6. [Decision Pipeline](../00_Architecture/DECISION_PIPELINE.md)
7. [Security Architecture](../03_Security/SECURITY_ARCHITECTURE.md)

Komplettera med [kodankrade diagram](../00_Architecture/DIAGRAMS.md), [Constitution](../CONSTITUTION.md), [ADR-index](../adr/), [modulkontrakt](../MODULE_CONTRACT.md) och [CAF](../90_Governance/CAF_README.md).

**Återupptäckt:** CROW är beskrivet som en **Decision Intelligence Platform**, inte primärt ett OVK-, kalkyl-, dokument- eller säkerhetssystem. Den generella kärnan omvandlar observationer till förklarbara, reproducerbara beslut. GRC och Security bör använda samma mönster, inte skapa alternativa beslutsmotorer.

## 4. Befintliga förmågor att återanvända
| Område | Befintlig källa / kod | Relevans för framtida moduler | Status |
| --- | --- | --- | --- |
| Claim, proveniens, konflikt | `src/crow_module_sdk`, `crow_claim_extraction`, `crow_knowledge_fusion`, `docs/00_Architecture/DECISION_PIPELINE.md` | Evidensdriven risk-/säkerhetsbedömning | Kod finns; domänpassning kräver kontroll |
| Authority och Human Review | `crow_authority`, `crow_authority_discovery`, `crow_accepted_claims`, ADR-002 | Kontrollbedömningar, policykonflikter, sign-off | Kod finns |
| Deterministiska regler och beslut | `crow_decision_engine`, `crow_technical_validation`, `crow_technical_review` | GRC-kontroller, Security-regler, beslutsförklaring | Kod finns; kan vara tekniskt/kommersiellt orienterad |
| Graf och relationer | `crow_building_graph`, `crow_canonical`, `crow_reasoning`, ADR-012 | Nätverks-/tillgångsgraf, digital twin, beroenden | Kod finns; generalitet och tenant-gränser ej verifierade |
| Evidens och audit | `crow_evidence_index`, `crow_evidence_rules`, `crow_assurance`, `crow_audit_explorer` | GRC-evidens, revisionspaket, findings | Kod finns; vissa projektspecifika |
| Import och kunskap | `crow_import_framework`, `crow_import_orchestrator`, `crow_knowledge_runtime` | Read-only integrationsadapters och dokumentintag | Kod finns; lämplighet ej verifierad |
| Modul-SDK och conformance | `crow_module_sdk`, `crow_module_conformance`, `docs/MODULE_REGISTRY.md` | Alla framtida moduler | Implementerat entry-point-register |
| Trust, signering och release | `docs/TRUST_POLICY.md`, CAF-CMP, `docs/verification/` | Signerade moduler och revisionsbar release | HMAC referens; produktionshärdning återstår |
| Kundkontext/entitlements | `crow_entitlements`, ADR-011 | Tenant- och rollstyrning | Delvis implementerat, målarkitektur ej uppnådd |

**Viktig gräns:** Building Graph är idag beskriven och modellerad med byggnads-/installationssemantik. Återanvänd grafprinciper och kontrakt först efter bedömning; lägg inte nätverksobjekt direkt i en byggnadsdomänmodell utan explicit arkitekturbeslut.

## 5. Förbisedda framtida koncept
### CDL och CKL
[Future Modules](../FUTURE_MODULES.md) dokumenterar redan:
- **CROW Decision Language (CDL)**: versionerade, testbara, signerbara besluts- och valideringsregler.
- **CROW Knowledge Language (CKL)**: domänkunskap, relationer, ontologier, taxonomier, vokabulärer och signerade kunskapspaket.

Dessa är **föreslagna och uppskjutna**, inte levererade språk. Läs ADR-008/009 och entry criteria innan ny regelmotor eller compliance-DSL designas. GRC/Security bör i första hand utnyttja befintliga besluts- och kunskapskontrakt.

### Gemensam graf
[ADR-012](../adr/ADR-012-building-graph-as-shared-model.md) identifierar redan **fem parallella representationer av samma byggnad** och avser skapa en gemensam byggnadsmodell med stabil identitet. Dokumentet är märkt `Proposed`, medan utvecklingspolicyn hänvisar till det som styrande. Verifiera beslutets faktiska status och implementation innan ny datamodell införs.

### Identitetskandidater och explicit review
[CCM Identity Candidates](../00_Architecture/CCM_IDENTITY_CANDIDATES.md) och [CCM Identity Review](../00_Architecture/CCM_IDENTITY_REVIEW.md) visar ett värdefullt mönster: `same_as_candidate` kräver manuell verifiering och får inte tyst slå ihop objekt. Det är direkt relevant för Edge asset discovery, där IP/MAC/hostname kan förändras och vara tvetydiga.

### Fysisk kontra logisk modell
[IFC Explicit Relation Import](../00_Architecture/IFC_EXPLICIT_RELATION_IMPORT.md) skiljer explicit källrelation från antagen fysisk verklighet. [OVK 2.0 Vision](../OVK_PRODUCT_VISION_2_0.md) skiljer grafisk placering från faktisk teknisk topologi. Båda principerna är relevanta för Securitys logiska/fysiska nätverkskarta.

### Federering och governance
[CAF Federation Roadmap](../90_Governance/CAF-FUT-001_Federation_Roadmap.md) innehåller en **icke-normativ** ordning: central authorization, distribution split, tenantbaserad modulaktivering, asymmetrisk signering och senare federation. Historiska CAS-905…943 är ersatta och ska inte behandlas som aktiva krav.

## 6. Produktstrategi och prioritet
[OVK 1.0 roadmap](../OVK_PRODUCT_ROADMAP_1_0.md) säger uttryckligen att OVK är första kommersiella produkten och att **nya generella plattformsinitiativ och nya produkter ska vänta** tills 1.0 är användbar och verifierad i pilot, med undantag för nödvändig säkerhet, dataintegritet och driftstabilitet.

**Konsekvens:** Dokumentera GRC, Edge, Security, CDL och CKL nu, men påbörja inte bred implementation eller ändra OVK:s releasegrindar utan nytt produktägarbeslut.

[OVK 2.0 Vision](../OVK_PRODUCT_VISION_2_0.md) omfattar redan CAD Light, schakt, kanaltopologi, systemflödesscheman, styrprinciper och driftkort. Dessa ska inte av misstag återintroduceras som nya OVK 1.0-krav.

## 7. Dokumentation och arkiv – undvik dubbel auktoritet
[CAF-002](../90_Governance/CAF-002_Architecture_Principles.md) anger: **ingen dubblerad arkitekturdokumentation**. [CAS-900](../90_Governance/CAS-900_Architecture_Overview.md) är ett index, inte en andra arkitekturbeskrivning. [MIGRATION_FROM_RC1](../90_Governance/MIGRATION_FROM_RC1.md) förklarar varför 109 ursprungliga CAF-dokument arkiverats.

Nya modulmappar under `docs/modules/` ska därför vara **modulspecifika krav, beslut och länkar**. Gemensamma principer och plattformskontrakt ska länkas till sina auktoritativa källor och inte kopieras.

## 8. Konkreta inkonsekvenser och risker
1. **Dokumentationsindex:** `docs/README.md` listar inte den nya `docs/modules/`-strukturen. Länka in den efter produktägarens godkännande.
2. **GRC-planen:** nyligen tillkomna GRC-dokument måste förankras i CAF, Backbone och befintlig assurance/evidence, inte formulera nya parallella grundtjänster.
3. **ADR-012 status:** dokumentet säger Proposed, medan `docs/engineering/DEVELOPMENT.md` och `REVIEW.md` behandlar dess principer som gällande. Status och omfattning behöver synkroniseras.
4. **Roadmap-drift:** `TODO.md` visar Sprint B-arbete som öppet trots att flera motsvarande `crow_*`-paket finns. Det är inte bevis på att funktionerna är klara, men checklistan behöver aktualitetskontroll.
5. **Målarkitektur kontra drift:** ADR-011 och `SECURITY_ARCHITECTURE.md` säger uttryckligen att full tenant-/permission-enforcement återstår. Dokumentera inte detta som produktionsklart.
6. **Modulgräns:** `crow_module_sdk/plugin.py` exponerar ett begränsat plugin-protokoll; nya GRC/Edge-API:er får inte antas vara stödda utan kontraktsarbete.
7. **Kundägd Edge:** hardware-bound identity, gateway, säker ingestion och offlinekö saknas i verifierad befintlig kod; får inte förväxlas med vanlig användarsession.
8. **Domänkoppling:** befintlig graf, assurance och beslutsmotorer är delvis orienterade mot bygg/teknik/projekt. Återanvändning kräver gränsgranskning, inte kopiering.
9. **Verifieringsstatus:** 212 testfiler betyder inte 212 godkända tester. Ingen testkörning har gjorts i denna inventering.
10. **Förslag kontra beslut:** arkiverade CAS, framtida CDL/CKL och planerade integrationsmönster är inte automatiskt normativa.

## 9. Återvinningslista / rekommenderad backlog
| ID | Förslag | Prioritet för dokumentation | Kodprioritet |
| --- | --- | --- | --- |
| REC-01 | Etablera en enda repo- och arkitekturöversikt med länkar till auktoritativa dokument | Hög | Ingen |
| REC-02 | Revidera GRC-kraven mot existerande Backbone/assurance/evidence | Hög | Efter OVK 1.0-beslut |
| REC-03 | Lägg till modulidéer för CDL och CKL genom länkar till befintliga ADR och Future Modules | Hög | Uppskjuten |
| REC-04 | Utred gemensamma grafkontrakt och ADR-012-status innan Security digital twin | Hög | Uppskjuten |
| REC-05 | Synkronisera docs/README och roadmap med aktuell implementation | Medel | Ingen |
| REC-06 | Skapa gap-matris för tenant isolation, central authorization och audit | Hög | Säkerhetsstyrt |
| REC-07 | Kartlägg återanvändbara read-only adapters/importkontrakt för GRC/Edge | Medel | Uppskjuten |
| REC-08 | Inventera äldre pass-/verifikationsartefakter för faktisk featurestatus | Hög | Ingen |
| REC-09 | Kartlägg OVK 1.0:s releasegrindar mot implementation och testbevis | Hög | Hög, enligt befintlig roadmap |
| REC-10 | Lägg in automatisk dokumentlänkskontroll och statuskonformitet i CI | Medel | Låg |

## 10. Arbetsprincip framåt
Inför varje ny modulidé, masterprompt eller större arkitekturbeslut:
1. Sök först i `docs/00_Architecture`, `docs/adr`, `docs/FUTURE_MODULES.md`, `docs/90_Governance`, `docs/10_Passes`, `src`, `modules` och `tests`.
2. Skilj **implementerat**, **beslutad målarkitektur**, **föreslaget**, **arkiverat** och **saknas** med fil- och kodreferens.
3. Dokumentera det **nya** i rätt modulmapp, länka till auktoritativ arkitektur och bevara öppna frågor.
4. Undvik att skapa nya kontrakt eller duplicerade tjänster utan ADR och konkreta testbehov.
5. Bevara OVK 1.0-prioriteten. Ingen merge eller driftsättning utan produktägarens beslut.

## 11. Nästa granskning (ännu ej genomförd)
För en verkligt fullständig repo-audit återstår filvis granskning av samtliga implementationer, testspecifikationer, alla 91 passdokument och 59 verifieringsartefakter, jämförelse med aktiv CI, dependency-analys och faktisk testkörning. Detta dokument är en bred **repo-inventering och riktad arkitekturrevision**, inte en färdig säkerhetsrevision av varje kodrad.
