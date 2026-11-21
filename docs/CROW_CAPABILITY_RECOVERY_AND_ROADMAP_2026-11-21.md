# CROW – systematisk återvinningsgranskning och väg framåt

**Datum:** 2026-11-21  
**Status:** kodankrad granskning, förslag till genomförandeplan; ingen implementation eller merge  
**Underlag:** `main`, tidigare inventering i `docs/REPOSITORY_ARCHITECTURE_RECOVERY_AUDIT_2026-11-21.md`.  
**Princip:** Kod, körbara tester och aktuella verifikationsbevis väger tyngre än historiska påståenden. Filförekomst bevisar inte fungerande produkt.

## 1. Exekutiv slutsats

CROW innehåller en stor återanvändbar **domänneutral analys- och evidensmotor** samt tre installerbara verksamhetsmoduler (OVK, Vent, Pressure Test). Plattformen har också en fungerande modulupptäckt, en Workbench, filbaserad kundkontext, sessioner, entitlementadministration och viss audit. Den är **inte** verifierat färdig som generell flerorganisations-SaaS, och GRC/Security/Edge är ännu målarkitekturer.

**Rekommenderad ordning:** (1) stabilisera OVK 1.0 och verifiera leveransflödet, (2) säkra plattformens gemensamma kontrakt och tenant-isolering, (3) införa gemensam byggnadsidentitet och modulkontext utan att störa OVK, (4) återanvända evidens/assurance för GRC, (5) genomföra Edge/Security som separat, godkänd produktström, (6) senare CDL/CKL/federering.

## 2. Statusvokabulär

- **KOD:** identifierad konkret implementation i `main`; ej liktydigt med end-to-end-verifiering.
- **DEL:** viss implementation finns, men centrala kontrakt, integrationer eller produktionskrav återstår.
- **PLAN:** dokumenterad målbild utan identifierad verksamhetsimplementation.
- **ARKIV:** uttryckligen superseded; inspirationsmaterial, aldrig normativ källa.
- **EJ VERIFIERAT:** kräver tester, driftbevis eller ytterligare kodgranskning.

## 3. Implementationsmatris – exakt var

| Förmåga | Status | Implementation / auktoritativ källa | Bedömning och nästa kontroll |
| --- | --- | --- | --- |
| Modulregister och entry points | KOD | `src/crow_module_sdk/module_registry.py`, `docs/MODULE_REGISTRY.md` | `crow.modules` laddas, dubblett-ID avvisas; verifiera kompatibilitet och felvägar |
| Tom kärna utan moduler | KOD, CI-kontroll | `.github/workflows/core-empty.yml`, `src/crow_workbench/shell.py` | Workflow testar installation, `/health`, `/login`; kontrollera senaste workflow-resultat |
| Publikt modulkontrakt | KOD | `src/crow_module_sdk/plugin.py`, `docs/MODULE_CONTRACT.md` | Protocol har manifest/capabilities/claim schemas/validation/health; web routers är dynamisk extension |
| Modulaktivering i webb | DEL | `src/crow_workbench/shell.py`, `src/crow_entitlements/entitlements.py` | Routrar monteras via `routers(data_root)`; separera modulinstallation från tenant-åtkomst och central auth |
| Lokal autentisering | KOD | `src/crow_entitlements/auth.py`, `context.py` | Scrypt-lösenord, signerade sessionscookies, filbaserade användare; OIDC enligt ADR-011 återstår |
| Tenant-/rollkontext | DEL | `src/crow_entitlements/context.py`, `models.py`, ADR-011 | Session eller environment-fallback; kontrollera att produktion alltid kör fail-closed |
| Entitlements | DEL | `src/crow_entitlements/entitlements.py`, `management.py`, `catalog.py` | Kundbundna JSON-filer och modulstatus; full enforcement på varje endpoint ej verifierad |
| Administrativ audit | DEL | `src/crow_entitlements/audit.py` | JSONL append och admin-endpoint; ingen bevisad tamper-evident/central audit för alla nekanden |
| Central authorization/OIDC/RLS | PLAN | `docs/adr/ADR-011-backbone-authorization.md`, `docs/03_Security/SECURITY_ARCHITECTURE.md` | Explicit accepterad målarkitektur, inte komplett implementerad |
| Building Graph | KOD | `src/crow_building_graph/models.py`, `service.py`, `repository.py` | Objekt, relationer, evidens, revisionshistorik; relationer typbegränsade |
| Gemensam fastighet mellan moduler | PLAN/DEL | `docs/adr/ADR-012-building-graph-as-shared-model.md` | ADR beskriver fem separata modeller; ModuleContext och tenantägd fastighet kräver migrationsplan |
| Kanonisk objektmodell | KOD | `src/crow_canonical/models.py`, `docs/architecture/CROW_CANONICAL_MODEL_0.1.md` | Idag ventilationsobjekt; ingen generell IT-asset-modell |
| Identitetskandidater och manuell resolution | KOD/DEL | `docs/00_Architecture/CCM_IDENTITY_CANDIDATES.md`, `CCM_IDENTITY_REVIEW.md` | Återanvänd mönster, inte okontrollerad asset-merge |
| Graftraversering/reasoning | KOD | `src/crow_reasoning/engine.py` | Traversering av graf-snapshots och relationstyper; kontrollera domänoberoende |
| Evidensindex | KOD | `src/crow_evidence_index/index.py` | Deterministiskt read-only-index; identifierar saknade/dubbla evidensreferenser och checksum-konflikter |
| Assurance-översikt | KOD | `src/crow_assurance/summary.py` | Sammanfattar graf- och evidensgranskningar; **inte** ett generellt ISO/SOC2-kontrollregister |
| Beslut/authority/claims | KOD | `src/crow_authority`, `crow_accepted_claims`, `crow_decision_engine`, `crow_technical_review` | Finns som paket; granska API/kontrakt innan GRC-adapter |
| Import/knowledge | KOD | `src/crow_import_framework/registry.py`, `crow_knowledge_runtime`, `crow_import_orchestrator` | Pluginbaserad import finns; kontrollera externa anslutningars säkerhet |
| OVK | KOD, pilot återstår | `modules/crow-ovk-module/pyproject.toml`, `src/crow_ovk_module/plugin.py`, `docs/OVK_PRODUCT_ROADMAP_1_0.md` | Separat entry point `crow.ovk`; produkten ej verifierat färdig i verklig pilot |
| Vent | KOD | `modules/crow-vent-module/` | Separat verksamhetsmodul; verifiera kompatibilitet med gemensam byggnadsmodell |
| Pressure Test | KOD | `modules/crow-pressure-test-module/` | Separat modul; återanvänder enligt ADR-012 ännu inte en gemensam fastighetsidentitet |
| GRC | PLAN | `docs/modules/crow-grc/ARCHITECTURE.md` | Risker/kontroller/incidenter som verksamhetsmodul saknar identifierad kod |
| Security/Edge | PLAN | `docs/modules/crow-security/edge/ARCHITECTURE.md` | Edge Agent/Gateway/mTLS/discovery ännu inte implementerade här |
| CDL och CKL | PLAN | `docs/FUTURE_MODULES.md`, ADR-008/009 | Skjut upp parser/runtime; återanvänd existerande regelmotorer |
| Federation | PLAN | `docs/90_Governance/CAF-FUT-001_Federation_Roadmap.md` | Icke-normativ, beroende av auth/tenant/trust |
| Gamla CAF/CAS och UML | ARKIV | `docs/90_Governance/Archive/`, `MIGRATION_FROM_RC1.md` | Endast idéåtervinning med explicit nytt beslut |

## 4. Viktiga skillnader mot tidigare antaganden

1. **Plattformen har egen autentisering i kod**, även om målarkitekturen säger extern OIDC. Denna övergång behöver migrerings- och hotmodell, inte bara ett nytt login-gränssnitt.
2. **Audit är inte automatiskt revisionssäker.** `write_audit_event` skriver vanlig JSONL med append; filen är inte i sig immutabel eller kryptografiskt skyddad. GRC får inte marknadsföra den som manipulationssäker evidens.
3. **Assurance är snävare än GRC.** `ProjectAssuranceSummaryBuilder` aggregerar graph/evidence-audits. Riskregister, ramverksmappning, policyattestering och formell riskacceptans är separata domänfunktioner.
4. **Modul-SDK och Workbench-webbgränsen skiljer sig.** SDK:s `CrowModulePlugin` har fem obligatoriska metoder, medan webbroutrar laddas via duck typing `routers(data_root)`. ADR-012 föreslår `ModuleContext`; detta är ett verkligt arkitektur- och migreringsarbete.
5. **Byggnadsgrafen är inte en färdig IT-tillgångsgraf.** Återanvänd graf- och evidensmönster men håll `crow.security` domänmodell separat om inte ett generellt, granskat grafkontrakt tas fram.
6. **Versionsnummer är inte releasebevis.** OVK-paketets `1.0.0` anger paketerad version; OVK 1.0-pilot och leveransgrindar kvarstår enligt produktplanen.
7. **Historiska testresultat är historiska.** `docs/90_Governance/RC_CRITERIA_0.7.0.md` redovisar en lokal kontroll från juli 2026, inte dagens CI-status.

## 5. Beslut som bör fattas före ny kod

| ID | Beslut | Rekommendation | Förutsättning |
| --- | --- | --- | --- |
| D-01 | Produktprioritet | OVK 1.0 till verifierad pilot före ny kommersiell modul | Behåll R1–R6 |
| D-02 | Plattformsidentitet | Gemensamt kund-/tenant- och resource-scope-kontrakt | Säkerhets-ADR och migrering |
| D-03 | Modulkontext | Versionerad `ModuleContext` som ersätter rå `data_root` successivt | ADR-012 och bakåtkompatibilitet |
| D-04 | Gemensam byggnadsmodell | Fastighet på kundnivå, projekt refererar | Migration utan förlorad historik |
| D-05 | Gemensam evidens | Publicera minsta evidens-/assurance-kontrakt, behåll domänansvar | Bevisad tenant-isolering |
| D-06 | GRC-gräns | GRC äger risk/kontroll/policy; Backbone äger identity/audit | Ingen GRC i Core |
| D-07 | Edge-gräns | Separat gateway och device identity, ingen direkt användarsession | Hotmodell och godkänt scope |
| D-08 | Dokumentstyrning | En auktoritativ källa per beslut, moduler länkar | Dokumentindex och statuskontroll |

## 6. Väg framåt – ordnade arbetsströmmar

### Fas 0 – Sanning och verifiering (nu; dokumentation och tester)
**Mål:** en verifierbar baseline.  
**Arbete:** kontrollera aktuellt main-SHA och CI, granska PR-status; kör ruff/mypy/pytest/build/architecture review i reproducerbar miljö; koppla verifikationsmanifest till revision; granska särskilt auth/tenant/OVK kritiska flöden.  
**Leverans:** `CAPABILITY_REGISTER.md` med status, ägare, kodväg, tester, evidens-SHA och öppna gap.  
**Exit:** inga funktioner markeras verifierade utan körbart bevis.

### Fas 1 – OVK 1.0 till användbar pilot (högsta produktprioritet)
**Mål:** ett riktigt uppdrag från fastighetsregistrering till protokoll/intyg och evidensbilaga.  
**Arbete:** R1–R6 enligt `OVK_PRODUCT_ROADMAP_1_0.md`; mobil/offline/synk, historik, återkontroll, granskning, dokumentpaket, felvägar. Fixa regressionsfel före fler funktioner.  
**Exit:** signerad pilotchecklista med verkligt testfall, omstart, offline, återställning och dokumentgranskning.

### Fas 2 – Plattformssäkerhet och kontrakt (minsta nödvändiga, parallellt endast vid säkerhetsbehov)
**Mål:** tydliga gränser mellan autentisering, authorization, tenant, entitlement och module execution.  
**Arbete:** hotmodell; inventera varje API-route och dess scope-kontroll; inför fail-closed-kontrakt och negativa cross-tenant-tester; planera OIDC och RLS utan att påstå att de redan finns; audit-integritet och retention.  
**Exit:** varje endpoint testas mot otillåten kundåtkomst; central policy verifierad.

### Fas 3 – Återanvändbara datakontrakt utan ny monolit
**Mål:** stoppa parallella modeller.  
**Arbete:** avgör ADR-012-status; implementera versionerad modulkontext och tenantägd fastighetsidentitet stegvis; migrera OVK/Vent/Pressure Test med bakåtkompatibla adapters; publicera evidens-/review-kontrakt.  
**Exit:** samma fastighet och objekt-ID återanvänds över uppdrag/moduler; historiken består; tom kärna fungerar.

### Fas 4 – GRC som egen modul
**Mål:** en första nyttig risk-/kontrollprodukt utan Edge-beroende.  
**Arbete:** riskregister, kontrollbibliotek, evidence links, riskacceptans, revisionsgrindar; använd existerande index/assurance där kontrakt tillåter. Ramverksmappningar är versionerade och kräver mänsklig bedömning.  
**Exit:** isolerad GRC-installation med två tenants och negativa behörighetstester; kontrollutfall kan spåras till evidens och godkännare.

### Fas 5 – Security och Edge
**Mål:** godkänd, säker inventering och verifierade observationer.  
**Arbete:** device enrollment, mTLS, återkallelse, signerade uppdrag, offlinekö, scoped discovery, asset identity/review, topology, riskkopplingar via publika kontrakt.  
**Exit:** ingen cross-tenant ingestion; inga osanktionerade scans; testad revocation och idempotens; Edge fungerar utan OVK/GRC.

### Fas 6 – Framtida förmågor
CDL/CKL, avancerad federation, distribuerad governance, avancerad detektion och automatiserad compliance-evidens endast efter konkreta use cases, säkerhetsgrindar och nya ADR:er.

## 7. Prioriterad genomförandebacklog

| Ordning | Uppgift | Ändringsyta | Bevis / acceptans |
| --- | --- | --- | --- |
| 1 | Baseline med CI/testresultat på exakt SHA | `docs/verification` | Kommandologgar och SHA |
| 2 | OVK R1–R6 pilotgap med testfall | `modules/crow-ovk-module`, `docs/OVK_PRODUCT_ROADMAP_1_0.md` | Pilotprotokoll |
| 3 | API-route/tenant-scope-matris | `src/crow_workbench`, `src/crow_entitlements`, moduler | Negativa behörighetstester |
| 4 | Statusbeslut ADR-012 och migreringsordning | `docs/adr/ADR-012...` | Beslut och kompatibilitetstest |
| 5 | Inventera duplicerade fastighetsobjekt | `crow_building_graph`, OVK/Vent/Pressure | Fält- och ID-matris |
| 6 | Gemensamt evidence/review API-förslag | SDK, evidence index, assurance | Kontrakttest |
| 7 | Revidera GRC mot verifierad återanvändning | `docs/modules/crow-grc` | Ingen dubbel core-funktion |
| 8 | Revidera Security/Edge mot graf och auth | `docs/modules/crow-security` | Hotmodell och scope-testplan |
| 9 | Dokumentindex och modulidéregister | `docs/README.md`, `docs/modules` | Länk- och statuskontroll |
| 10 | Framtida CDL/CKL/federering – bevara men avvakta | `docs/FUTURE_MODULES.md`, ADR | Inga förtida beroenden |

## 8. Arbetsregler och stoppsignaler

- Ingen ändring av `main`, merge eller deployment utan produktägarens godkännande.
- Varje beteendeändring: egen PR, små diffar, tester och reviewer/verifier enligt `AGENTS.md`.
- Ny arkitektur ska börja med sökning i `docs/00_Architecture`, `docs/adr`, `docs/90_Governance`, `src`, `modules`, `tests`.
- Ingen automatisk promotion från observerat till verifierat; ingen tyst data- eller identitetsmerge.
- Ingen GRC- eller Edge-implementation som förutsätter att full OIDC/RLS redan finns.
- Inga påståenden om färdig compliance, manipulationssäker audit eller produktionsklar SaaS utan evidens.
- Håll planerad och historisk funktionalitet åtskild från implementerad och verifierad.

## 9. Öppet verifieringsarbete och ärliga begränsningar

Detta dokument är en **kodankrad återvinningsgranskning och genomförbar roadmap**, inte ett bevis på att alla 1 173 filer är radvis granskade. Följande återstår för en komplett verifieringsrapport: körning av hela testsviten på aktuell revision, senaste CI-status, full route-inventering, varje moduls negativa tenant-test, kartläggning av samtliga 91 pass och 59 verifikationsartefakter samt validering i driftsatt miljö. Inga sådana kontroller rapporteras som utförda här.

**Beslutspunkt:** Godkänn ordningsföljden och börja med Fas 0 + OVK-pilotens gaplista. GRC/Edge dokumenteras, men kodstart kräver separat prioriteringsbeslut.
