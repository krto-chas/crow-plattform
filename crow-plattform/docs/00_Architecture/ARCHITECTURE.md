# Crow Architecture

**Status:** RC0 – Architecture Freeze Candidate  
**Scope:** Crow Platform 1.0  
**Audience:** arkitekter, utvecklare, granskare och produktägare

## 1. Syfte

Crow är en **Decision Intelligence Platform**. Plattformens uppgift är att omvandla ostrukturerat och strukturerat projektunderlag till spårbara, reproducerbara och förklarbara beslutsunderlag.

Crow är inte i första hand ett kalkylsystem, ett dokumentarkiv eller en AI-assistent. Dessa kan vara tillämpningar ovanpå plattformen, men kärnan är en kontrollerad beslutskedja där varje slutsats kan härledas tillbaka till källor, regler, granskningar och versioner.

> Crow bygger inte bara resultat. Crow bygger motiverade beslut.

## 2. Problemformulering

Tekniska och kommersiella beslut fattas ofta från dokument som motsäger varandra, är ofullständiga eller har oklar auktoritet. Traditionella system lagrar vanligen slutresultatet men inte hela resonemanget. Det skapar flera problem:

- källan till ett beslut blir svår att verifiera,
- dokumentrevisioner kan göra tidigare slutsatser ogiltiga,
- kunskap fastnar hos enskilda personer,
- ekonomiska konsekvenser kan inte reproduceras,
- AI-genererade svar kan uppfattas som säkra trots svagt underlag,
- ansvar och mänskliga godkännanden blir otydliga.

Crow löser detta genom att separera observation, tolkning, auktoritet, beslut, teknisk påverkan och kommersiell konsekvens i explicita domänobjekt.

## 3. Arkitekturella mål

### 3.1 Proveniens först

Varje betydelsefullt objekt ska kunna härledas till sitt ursprung. Proveniens är inte metadata som läggs till i efterhand; den är en del av domänmodellen.

### 3.2 Determinism

Samma verifierade indata, samma regelversion och samma policyversion ska ge samma resultat. Deterministiska delar får inte bero på dolda promptar, globalt tillstånd eller ordningsberoende sidoeffekter.

### 3.3 Förklarbarhet

Beslut ska kunna förklaras genom strukturerad evidens: vilka observationer som stödde ett claim, vilken auktoritetsregel som användes, vilken teknisk regel som aktiverades och hur den kommersiella effekten beräknades.

### 3.4 Reproducerbarhet

Ett tidigare beslut ska kunna återskapas från sparade artefakter och versionsbundna regler. Fingerprints används för stabil identifiering och förändringsdetektion.

### 3.5 Mänskligt ansvar

Crow kan automatisera analys och beräkning men ska inte dölja osäkerhet. Konflikter och otillräckligt underlag ska kunna lämnas öppna för mänsklig granskning.

### 3.6 Domänoberoende kärna

Plattformskärnan ska inte innehålla ventilations-, bygg-, energi- eller compliance-specifika antaganden. Domänlogik tillförs genom separata moduler och deklarativa regler.

### 3.7 Säkerhet som plattformsansvar

Tvärgående säkerhetsfunktioner, såsom authorization, audit och tenant isolation, ska centraliseras i Backbone. Moduler deklarerar behov men får inte skapa egna alternativa säkerhetsmodeller.

## 4. Plattform och applikationer

Crow delas konceptuellt i två lager.

### Crow Platform

Den generella plattformen ansvarar för:

- dokument- och projektidentitet,
- observationer och claims,
- kunskapsfusion och konfliktmodellering,
- auktoritetsupptäckt och auktoritetsbeslut,
- accepterade claims,
- tekniska och kommersiella beslut,
- proveniens, audit och revision,
- modulkontrakt och conformance,
- deterministisk persistens och serialisering.

### Crow Applications

Domänspecifika produkter använder plattformens kontrakt. Exempel är Crow Ventilation, Crow Construction, Crow Energy, Crow Compliance och framtida verksamhetsområden. En applikation får tillföra terminologi, regler, mallar och användarflöden men får inte kringgå plattformens invariants.

## 5. Beslutskedjan

Den aktuella referenspipelinen är:

```text
Document
  → Observation
  → ClaimCandidate
  → KnowledgeCluster
  → Review
  → Authority Discovery
  → Authority Resolution
  → AcceptedClaim
  → TechnicalDecision
  → TechnicalReview
  → TechnicalDelta
  → ScopeImpact
  → CommercialImpact
  → CommercialAdjustment
  → CommercialReview
  → EstimateLine
  → EstimateStructure
  → EstimateRevision
```

Varje steg har ett avgränsat ansvar:

- **Document** bevarar källans identitet och revision.
- **Observation** beskriver vad som faktiskt kan avläsas.
- **ClaimCandidate** uttrycker en möjlig tolkning av observationer.
- **KnowledgeCluster** samlar relaterade och eventuellt motstridiga claims.
- **Authority Resolution** avgör vilka källor eller regler som har företräde.
- **AcceptedClaim** är ett claim som får användas som beslutsunderlag.
- **TechnicalDecision** tillämpar versionerade tekniska regler.
- **TechnicalDelta** jämför beslutet med en explicit baseline.
- **ScopeImpact** uttrycker vad förändringen betyder för omfattning och mängd.
- **CommercialImpact** översätter teknisk påverkan till ekonomisk påverkan.
- **CommercialReview** utgör godkännandepunkt före kalkyl.
- **EstimateLine** representerar den atomära kalkylraden.
- **EstimateStructure** grupperar rader deterministiskt.
- **EstimateRevision** förklarar skillnader mellan två kalkylversioner.

Detaljer finns i [DECISION_PIPELINE.md](DECISION_PIPELINE.md) och kommande `DOMAIN_MODEL.md`.

## 6. Runtime- och modularkitektur

Crow är utformad som en **modulär monolit** med explicita paketgränser och publika kontrakt. Detta ger en gemensam transaktions- och revisionsmodell utan att låsa framtida deploymentval.

Varje modul följer i huvudsak samma mönster:

```text
models.py   → immutabla domänmodeller
engine.py   → deterministisk domänlogik
service.py  → fil-/projektintegration och orkestrering
__init__.py → publik API-yta
py.typed    → deklarerat typstöd
```

Moduler ska:

- använda publika kontrakt,
- undvika privata korsimporter,
- validera input explicit,
- producera stabila fingerprints där identitet krävs,
- serialisera deterministiskt,
- vara testbara utan nätverk eller extern tjänst.

## 7. Backbone

**Backbone** är plattformens gemensamma exekverings- och styrningslager. Det omfattar publika kontrakt, projektaggregat, plugin discovery, conformance, proveniens, audit, revision, persistenskontrakt och framtida central authorization.

Backbone ska vara domänneutralt. Det ska inte avgöra hur en ventilationsritning tolkas, men det ska avgöra vilka kontrakt en ventilationsmodul måste följa och hur dess resultat blir spårbara, validerade och säkert exekverade.

## 8. AI:s roll

AI får användas för:

- dokumentextraktion,
- klassificering,
- förslag till claims,
- semantisk gruppering,
- språk- och presentationsstöd.

AI får inte:

- själv fastställa dokumentauktoritet utan versionerad policy,
- tyst ändra deterministiska belopp,
- utöka användarens behörigheter,
- kringgå human review,
- ersätta källproveniens med ett genererat påstående.

AI-komponenter producerar kandidater eller rekommendationer. Plattformens regelmotorer och granskningssteg avgör vad som blir accepterat beslutsunderlag.

## 9. Säkerhetsmodell

Säkerhetsarkitekturen bygger på följande gränser:

1. Authentication delegeras till en extern OIDC-kompatibel identitetsleverantör.
2. Authorization är ett Backbone-kontrakt och verkställs centralt före modul exekveras.
3. Moduler deklarerar permissions i signerade manifest men verkställer dem inte själva.
4. Deny by default gäller.
5. Tenant isolation ska verkställas både i applikationslagret och genom databasens row-level security i flerorganisationsdrift.
6. Nekade beslut och administrativa behörighetsändringar skrivs till append-only audit trail.
7. AI använder samma read-only `AuthorizationContext` som andra moduler och får aldrig bredda effective permissions.

Se [SECURITY_ARCHITECTURE.md](../03_Security/SECURITY_ARCHITECTURE.md) och [ADR-011](../adr/ADR-011-backbone-authorization.md). ADR:n är accepterad som målarkitektur men delar av runtime-implementationen återstår efter RC0.

## 10. Persistens och versionshantering

Crow använder explicit serialiserade artefakter och stabila fingerprints för att stödja audit, jämförelse och reproduktion. Följande skiljs åt:

- **objektidentitet** – stabil identitet inom domänen,
- **content fingerprint** – hash av kanoniskt innehåll,
- **revision identity** – identitet för en tidsbunden version,
- **regel- och policyversion** – den logik som producerade resultatet.

Gamla beslut ska inte skrivas över. Nya revisioner skapas och skillnader uttrycks som egna objekt.

## 11. Arkitekturens gränser

Crow garanterar inte att en källa är sann. Plattformen garanterar att källan, tolkningen, auktoritetsregeln, granskningen och beslutet kan särskiljas och följas.

Crow eliminerar inte mänskligt ansvar. Plattformen gör ansvarspunkterna synliga.

Crow gör inte probabilistisk AI deterministisk. Den avgränsar AI-resultat från de deterministiska beslut som bygger vidare på dem.

## 12. Förändringsregler under Architecture Freeze

Under RC0 gäller:

- ingen ny domänfunktionalitet utan separat beslut,
- publika kontrakt ändras endast för verifierad inkonsistens eller säkerhetskrav,
- dokumentation ska skilja mellan implementerad arkitektur och målarkitektur,
- nya ADR:er måste ange kompatibilitet och konsekvenser,
- diagram och exempel ska härledas från faktiska kontrakt,
- varje väsentlig arkitekturprincip ska kunna kopplas till en framtida fitness function.

## 13. Vidare läsning

- [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)
- [DESIGN_PRINCIPLES.md](DESIGN_PRINCIPLES.md)
- [THE_CROW_PHILOSOPHY.md](THE_CROW_PHILOSOPHY.md)
- [ARCHITECTURAL_STYLE.md](ARCHITECTURAL_STYLE.md)
- [DECISION_PIPELINE.md](DECISION_PIPELINE.md)
- [Security Architecture](../03_Security/SECURITY_ARCHITECTURE.md)
- [Crow Constitution](../CONSTITUTION.md)
