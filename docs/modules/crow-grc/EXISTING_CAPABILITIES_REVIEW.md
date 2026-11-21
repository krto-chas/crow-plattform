# GRC – kartläggning av befintlig governance och återanvändning

**Datum:** 2026-11-21  
**Status:** kod- och dokumentgranskning, inte produktionsverifiering  
**Syfte:** förhindra dubbelimplementation av governance, audit, assurance, evidence och authorization i den planerade GRC-modulen.

## Viktig distinktion
CROW har redan en omfattande intern governance-arkitektur och flera implementerade stödkomponenter. Detta är **inte samma sak** som en färdig kundvänd GRC-produkt. Den nya GRC-modulen ska komplettera, inte kopiera, befintliga komponenter.

## Aktiva styrande dokument (länkar till källan)
| Källa | Innehåll | Slutsats |
| --- | --- | --- |
| [CAF_README](../../90_Governance/CAF_README.md) | CAF:s aktiva dokumentuppsättning och tillväxtregel | Ingen parallell governance-handbok |
| [CAF-002](../../90_Governance/CAF-002_Architecture_Principles.md) | Evidence-first, determinism, explicit authority, deny-by-default, modulpolicy, ingen dubblerad dokumentation | Bindande designprinciper |
| [CAS-900](../../90_Governance/CAS-900_Architecture_Overview.md) | Index till auktoritativa arkitekturkällor | Länka, kopiera inte |
| [CAF-CMP-001](../../90_Governance/CAF-CMP-001_Conformance_Checklist.md) | Conformance-gates | Återanvänd vid CI |
| [CONSTITUTION](../../CONSTITUTION.md) | Claims, proveniens, Human Review, publika kontrakt | Krav på GRC:s data och beslut |
| [SECURITY_ARCHITECTURE](../../03_Security/SECURITY_ARCHITECTURE.md) | Målarkitektur för auth, permissions, tenant-scope, audit | Vissa delar är uttryckligen ännu inte implementerade |
| [TRUST_POLICY](../../TRUST_POLICY.md) | Signering och modultrust | Nuvarande HMAC är referens, asymmetrisk signering föreslås för produktion |
| [AUDIT_AND_REVISION](../../AUDIT_AND_REVISION.md) | Dokumentrevision och invalidering av härledda claims | Relevanta livscykelregler |

## Implementerade kodkomponenter – granskat i main
| Källa | Faktisk funktion i koden | Återanvändningsprincip |
| --- | --- | --- |
| [crow_assurance/summary.py](../../../src/crow_assurance/summary.py) | Bygger read-only sammanställningar från graph/evidence audits, reviews och verifications | Utred generiskt kontrakt före ny assurance-implementation |
| [crow_audit_explorer/service.py](../../../src/crow_audit_explorer/service.py) | Bygger read-only projektioner av granskningar, fynd och reviewstatus | Återanvänd modeller/projektioner där semantik passar |
| [crow_entitlements/auth.py](../../../src/crow_entitlements/auth.py) | HMAC-signerade användarsessioner och scrypt-lösenord | Återanvänd inte som maskinautentisering; granska säkerhetsmål |
| [crow_entitlements/api.py](../../../src/crow_entitlements/api.py) | Kundkontext, entitlementkontroll och modulsökvägar | Behörighetsmodell måste utvidgas med verifierad objekt-/tenant-isolering |
| [crow_entitlements/audit.py](../../../src/crow_entitlements/audit.py) | JSONL-logg för administrativa händelser | Inte likvärdigt med manipulationsresistent central audit |

**Klassificering:** att kod finns innebär inte att den är generisk, produktionssäker eller direkt återanvändbar för GRC. Granska API, lagringssemantik, multi-tenancy och testtäckning före integration.

## Arkiv: historiskt underlag, ej automatiskt normativt
[Governance Archive](../../90_Governance/Archive/README.md) innehåller tidigare CAF/ADR/CAS-arkitektur, inklusive:
- `CAS-911` Policy, `CAS-912` Risk, `CAS-913` Incident, `CAS-916` Compliance;
- `CAS-908` Audit, `CAS-917` Data Governance och `CAS-933` Governance Metrics;
- tidigare compliance-checklistor och dokumentlivscykel.

Dessa får användas som idé- och kravkällor **efter** jämförelse med aktiv CAF, kod och senare ADR. Kopiera inte gamla regler okritiskt och skapa inte en andra auktoritativ ADR-serie.

## Gränsdragning
**Backbone/plattformen:** generisk identity, tenant scope, audit/event-kontrakt, proveniens/evidence-gränssnitt, manifest/trust, modul- och permissions-policy, versionering och conformance.

**CROW GRC-modulen:** riskregister, riskägare, behandling och acceptans, ramverksmappningar, kontrollägare och kontrollbedömningar, GRC-policyer, incidentarbetsflöden, compliance-vyer, revisionspaket och kundspecifika rapporter.

**Adapters:** valfri import av evidens från CI/CD, drift, identity och CROW Security. Får inte skapa beroende till en annan verksamhetsmodul.

## Föreslagen korrigerad implementeringsordning
1. Inventera befintliga publika API:er och modeller för audit, assurance, evidence, authorization och tenant-scope.
2. Klassificera varje relevant funktion som **implementerad**, **målarkitektur**, **arkiverad** eller **saknas**.
3. Definiera ett minimalt gemensamt kontrakt där återanvändning faktiskt krävs; följ CAF-002 och publika modulkontrakt.
4. Implementera GRC-specifik domänlogik som fristående plugin utan duplicerade plattformstjänster.
5. Verifiera tenant-isolering, Human Review, revisionsspår och tomkörning i CI.
6. Först därefter: ramverksbibliotek och integrationsadapters.

## Risker / öppna frågor
- Är befintliga assurance- och audit-modeller tillräckligt generiska, eller är de hårt bundna till graf/projekt?
- Hur skiljs intern CROW-governance från kundens risk-/compliance-register?
- Hur görs append-only/tamper-evident audit hållbar i flerorganisationsdrift?
- Vilka centrala säkerhetskrav är ännu bara målarkitektur?
- Vilka delar av historiska CAF/CAS ska bevaras som referens, inte återaktiveras?

**Granskningens begränsning:** statisk inspektion av utvalda källfiler och dokument på `main`. Ingen fullständig kodrevision, körning av tester eller verifiering av produktionsdrift har utförts.
