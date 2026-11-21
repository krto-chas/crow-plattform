# CROW GRC – idéregister och beslutslogg

**Status:** levande planeringsdokument  
**Uppdaterad:** 2026-11-21  
**Beslutsfattare:** produktägaren

## Fastlagda riktlinjer
| ID | Princip | Status |
| --- | --- | --- |
| GRC-001 | GRC är en valbar fristående modul i CROW Platform, inte OVK- eller Edge-kod | Beslutad arkitekturriktning |
| GRC-002 | Kärnan kan köras helt utan GRC eller andra verksamhetsmoduler | Beslutad plattformsprincip |
| GRC-003 | Evidens, revisionshistorik och godkännanden ska vara spårbara | Beslutad arkitekturriktning |
| GRC-004 | Människa godkänner riskacceptans och formella kontrollbedömningar | Föreslagen säkerhetsprincip |

## Idébank
| ID | Funktion | Status | Beroenden / kommentarer |
| --- | --- | --- | --- |
| GRC-I01 | Riskregister med riskägare och riskbehandling | Föreslagen P0 | Ingen annan verksamhetsmodul |
| GRC-I02 | Kontrollbibliotek och ISO/IEC 27001:2022-mappning | Föreslagen P1 | Versionsstyrda krav |
| GRC-I03 | SOC 2 Trust Services Criteria-stöd | Föreslagen P1 | Ingen automatisk attestering |
| GRC-I04 | NIS2-relaterad kravmappning | Föreslagen P1 | Juridisk tillämplighet per kund |
| GRC-I05 | Revisionsloggar och granskningsbeslut | Föreslagen P0 | Central audit |
| GRC-I06 | Behörighets- och access reviews | Föreslagen P1/P2 | Valfri identitetsadapter |
| GRC-I07 | Incidenthantering och åtgärdsplaner | Föreslagen P1 | Kan länkas till Security-fynd |
| GRC-I08 | Backup- och återställningsbevis | Föreslagen P1 | Skilj backup från restore-test |
| GRC-I09 | Automatisk evidens från CI/CD | Föreslagen P1 | Read-only GitHub/CI-adapter |
| GRC-I10 | Automatisk evidens från drift/monitorering | Föreslagen P2 | Valfria adapters |
| GRC-I11 | Evidens från CROW Security/Edge | Föreslagen P2 | Fungerar även utan Edge |
| GRC-I12 | Ledningsdashboard och rapporter | Föreslagen P0/P2 | Förklarbara bedömningar |
| GRC-I13 | Policyer, undantag, årlig kontrollöversyn | Föreslagen P1 | Godkännande och audit |
| GRC-I14 | Security Health Score med synlig osäkerhet | Idé/P3 | Undvik falsk precision |

## Beslut som återstår
- Första pilot: CROW:s interna GRC eller en extern kund?
- Vilket ramverk och vilka kontroller ska ingå i MVP?
- Exakt fördelning av plattformsövergripande audit/evidence och modulens GRC-domänlogik.
- Vilka adapterkällor ska byggas först?
- Behov av formell revisions-/exportmall.

## Regel för fortsatt dokumentation
Vid varje relevant diskussion: lägg till eller uppdatera berörd rad, ange datum och status, länka till arkitekturbeslut och skapa PR. Ingen idé räknas som implementerad utan kod och verifiering.
