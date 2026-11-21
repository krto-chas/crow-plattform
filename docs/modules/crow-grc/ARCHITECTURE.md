# CROW GRC – målarkitektur och krav

**Version:** 0.1 – initialt arkitekturunderlag  
**Status:** föreslagen, ej implementerad  
**Datum:** 2026-11-21  
**Föreslaget modul-ID:** `crow.grc`  
**Ägare/beslutsfattare:** produktägaren

## 1. Syfte
Bygg ett modulärt GRC-stöd (Governance, Risk & Compliance) för riskregister, policyer, kontroller, avvikelser, incidenter, revisionsloggar, uppföljning och evidens. Stödet ska kunna användas av en enskild organisation eller av CROW som extern rådgivare till flera separata kundorganisationer. Modulen är inte ett automatiskt certifierings- eller juridiskt bedömningssystem.

## 2. Arkitektonisk placering
```text
CROW Platform – domänneutral kärna
  ├─ Identity / Authorization / Tenant isolation / Audit / Evidence-kontrakt
  ├─ CROW GRC (fristående valbar modul)
  │    ├─ Riskregister och riskbehandling
  │    ├─ Kontrollbibliotek och ramverksmappning
  │    ├─ Policyer, undantag, godkännanden och uppgifter
  │    ├─ Incidenter och förbättringsåtgärder
  │    ├─ Evidens, revision och rapporter
  │    └─ Integrationer (valfria adapters)
  ├─ CROW Security (fristående valbar modul)
  │    └─ Asset Discovery / Findings / Edge
  └─ CROW OVK (fristående valbar modul)
```

**Obligatorisk regel:** GRC får inte ha hårt beroende till CROW Security, Edge eller OVK. Integrationer sker genom publika versionerade kontrakt och valfria adapters. GRC ska starta, fungera och testas helt utan andra verksamhetsmoduler. Inga GRC-specifika roller, datatyper eller regler läggs i kärnan.

## 3. Målgrupper och roller
Roller ska vara modulägda och kontrolleras i backend: GRC-administratör, riskägare, kontrollägare, evidensansvarig, revisor/granskare och läsbehörig ledning. En person kan ha flera roller. Extern CROW-rådgivare ges uttrycklig, tidsbegränsad och granskningsbar kundåtkomst; aldrig implicit tillgång till alla tenants. Separera den som föreslår från den som formellt godkänner riskacceptans eller kontrollutfall när arbetsflödet kräver det.

## 4. Funktionsområden
### 4.1 Riskregister
- Risk-ID, beskrivning, verksamhetstillgång/process, hot, sårbarhet, riskägare och kategori.
- Sannolikhet, konsekvens, inneboende och kvarstående risk med versionerad bedömningsmodell.
- Riskbehandling: minska, undvika, överföra eller acceptera; åtgärdsplan, ansvarig, förfallodatum, status.
- Riskacceptans kräver namngiven behörig beslutsfattare, motivering, datum och omprövningstid.
- Risker kan kopplas till tillgångar, fynd, incidenter, kontroller och evidens via referenser.

### 4.2 Kontrollbibliotek och ramverk
- Kontroll-ID, syfte, ägare, frekvens, scope, kontrolltyp, metod, effektivitet, status och revisionshistorik.
- Stöd för versionsstyrda ramverksprofiler och mappningar till **ISO/IEC 27001:2022**, **SOC 2 Trust Services Criteria** och **NIS2-relaterade krav**.
- En kontroll kan mappas till flera ramverkskrav; mappning ska vara spårbar och versionsbunden.
- Applicerbarhet och undantag kräver motivering och godkännande.
- Juridisk tillämplighet (bl.a. NIS2 och svensk implementering) ska bedömas separat per kund och tidpunkt. Ingen automatisk compliance-garanti.
- SOC 2 är ett attesterings-/revisionsramverk, inte en ISO-certifiering; systemet får inte likställa dem.

### 4.3 Evidens och revisionsspår
- Evidens kan bestå av dokument, revisionshändelser, konfigurationsutdrag, testresultat, signerade rapporter eller referenser till källsystem.
- Metadata: källa, tenant, scope, insamlingstid, kontrollperiod, insamlingsmetod, integritetshash, schema-/regelversion, ansvarig och åtkomstklass.
- Evidensstatus: `collected`, `review_required`, `verified`, `rejected`, `expired`.
- Ett lyckat backupjobb är **inte** bevis på fungerande återställning; restore-test ska registreras separat med verifierat utfall.
- Insamlad evidens ska vara reproducerbar där möjligt och åtkomstskyddad; revisionsloggar ska skyddas mot tyst ändring/radering.
- Automatisk insamling får inte själv intyga att en kontroll är effektiv eller att ett ramverkskrav är uppfyllt.

### 4.4 Incidenter och avvikelser
- Incident-/avvikelse-ID, klassning, påverkan, tidslinje, källor, ansvarig, åtgärder, evidens och uppföljning.
- Workflow för triage, utredning, beslut, avslut och lärdomar.
- Eventuella rapporteringsfrister beror på rättslig tillämplighet och ska konfigureras/verifieras, inte antas generellt.

### 4.5 Policyer, uppgifter och ledningsrapportering
- Versionshanterade policyer, ägare, godkännande, giltighet, återkommande översyn och undantag.
- Uppgifter och påminnelser för kontroller, riskbehandling, revisioner och omprövning.
- Ledningsöversikt: risker, förfallna åtgärder, kontrollstatus, evidensluckor, incidenter och beslut som behöver fattas.
- Transparens: redovisa datatäckning och osäkerhet; undvik vilseledande enkelpoäng som döljer okända kontroller.

## 5. Datamodell – föreslagna entiteter
`GrcScope`, `FrameworkVersion`, `Requirement`, `Control`, `ControlMapping`, `ControlAssessment`, `Risk`, `RiskTreatment`, `RiskAcceptance`, `PolicyDocument`, `Exception`, `Incident`, `CorrectiveAction`, `EvidenceRecord`, `EvidenceLink`, `AuditEvent`, `ReviewDecision`.

Alla tenantbundna objekt ska ha serververifierad tenant-identitet och åtkomstpolicy. Versionshistorik och referenser ska stödja att äldre rapporter kan återskapas mot då gällande kontroll-/ramverksversion.

## 6. Integrationer och automatisk evidensinsamling
Valfria, separat behörighetsstyrda adapters kan senare läsa:
- CI/CD: byggstatus, tester, kodgranskning, beroende- och sårbarhetsskanning, signerade releaser.
- Drift: backupstatus, genomförda restore-tester, patchnivåer, incidenter, loggning, övervakning.
- Identitet: användarlivscykel, privilegier, MFA-täckning, access reviews, exempelvis via Entra ID.
- CROW Security: upptäckta tillgångar, fynd, nätverkssegmentering och Edge-hälsa.
- Dokument- och ärendehantering: policyer, avvikelser, uppföljningsuppgifter.

Adaptrar ska ha minsta möjliga läsrättigheter, explicita scopes, loggad åtkomst och tidsbegränsade tokens. Hemligheter får inte exponeras i evidens, UI eller loggar. Källsystemets observationer ska bevaras som observationer tills kontrollägare eller auktoriserad granskare godkänner tolkningen.

## 7. Säkerhet, isolering och drift
- Ingen cross-tenant-åtkomst via användare, API, integration, export, bakgrundsjobb eller cache.
- Backend-verifierade roller och objektspecifika rättigheter; deny-by-default.
- Kryptering under överföring och vid lagring, kontrollerad nyckelhantering, sekretessklassning och retention.
- Audit av inloggning, åtkomst, export, ändringar, undantag, riskacceptans och granskning.
- Dataminimering och tydliga gallringsregler; kundägarskap och rättslig grund måste beaktas.
- Separation mellan CROW:s interna GRC och varje kunds GRC-data.
- Ingen automatisk radering av incidentbevis vid normal statusförändring.

## 8. UX-principer
Skandinavisk, luftig och lättförståelig desktopvy med responsivt stöd. Startyta med `Mina uppgifter`, `Risker`, `Kontroller`, `Evidens`, `Incidenter` och `Rapporter`. Visa ägare, status, förfallodatum och varför ett utfall bedömts på ett visst sätt. Ledning får en beslutsvy, granskare får evidensspår, kontrollägare får arbetskö. Undvik att presentera automatisk insamling som formellt godkänd compliance.

## 9. Utvecklingsfaser
**P0 – grund:** separat plugin, tenant-/rollmodell, kontrollregister, riskregister, manuella evidensposter, gransknings- och godkännandeflöden, audit, rapportutkast.

**P1 – uppföljning:** ramverksversioner/mappning, policyer, incidenter, uppgifter, återkommande kontroller, CI/CD- och backup/restore-adapters.

**P2 – integrationer:** CROW Security/Edge, identitets- och driftsystem, automatisk evidensinsamling, evidensluckor och ledningsrapporter.

**P3 – fördjupning:** fler ramverk, risktrender, avancerad kontrollanalys och automatiserad men granskningsbar risk-/kontrollkorrelation.

## 10. Acceptanskriterier
1. Kärnan startar med noll verksamhetsmoduler.
2. GRC kan installeras och avaktiveras utan ändring av kärnan.
3. GRC fungerar när Security, Edge och OVK saknas.
4. Användare kan inte läsa/ändra annan tenants data, inklusive via export och bakgrundsjobb.
5. Riskacceptans kräver explicit behörig mänsklig sign-off och revisionsspår.
6. Kontrollutfall kan härledas till aktuell ramverksversion, evidens, metod och bedömare.
7. Evidens kan vara inhämtad men fortfarande ej verifierad.
8. Backupstatus kan inte ensamt markeras som lyckat återställningstest.
9. Integrationsfel får inte tyst ge godkänd kontrollstatus.
10. Automatiserade tester omfattar roller, isolering, versionering, audit, negativa fall och modulens oberoende.
11. Rapporter anger kontrollperiod, scope, underlagsbrister och granskningsstatus.
12. Systemet utfärdar inte automatiskt SOC 2-attestering, ISO-certifikat eller juridisk NIS2-försäkran.

## 11. Kommande masterprompt och CI
Läs först aktuellt repo, `AGENTS.md`, `docs/CONSTITUTION.md`, `docs/MODULE_CONTRACT.md`, relevanta ADR och `docs/engineering/`. Följ modul-SDK och befintliga testmönster. Leverera små PR:er med tydlig verifiering och ingen merge/driftsättning utan produktägarens beslut. Skapa tester för tomkörning, moduloberoende, kundisolering, rollkontroller, evidensintegritet och riskgodkännanden.

## 12. Öppna arkitekturbeslut
- Prioritering: intern CROW GRC först eller kundportal först?
- Val av databas, kryptering och lagring av känsliga evidensfiler.
- Konkreta framework-källor/licenser och hur versioner ska uppdateras.
- Kontrollbibliotekets startomfattning och juridiskt ansvar för regulatorisk tolkning.
- Hur rapporter signeras och vilka retentionkrav som ska gälla.
- När och hur externa integrationsadapters ska certifieras.

**Dokumentationsstatus:** denna text beskriver önskad arkitektur och verifierbara krav, inte färdig implementation eller bekräftad efterlevnad.
