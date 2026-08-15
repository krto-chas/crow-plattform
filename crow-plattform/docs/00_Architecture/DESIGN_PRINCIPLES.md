# Design Principles

## 1. Provenance-first design

Alla objekt som påverkar beslut ska bära eller referera till tillräcklig information för att deras ursprung ska kunna rekonstrueras. Presentationstext får inte vara den enda lagrade förklaringen.

**Konsekvens:** datamodeller prioriterar identifierare, källreferenser, regelversioner och fingerprints framför bekväma men oförklarliga strängar.

## 2. Immutable domain objects

Domänobjekt behandlas som immutabla värden eller revisioner. En förändring producerar ett nytt objekt i stället för att historiken skrivs över.

**Konsekvens:** audit, jämförelse och reproduktion blir möjliga utan beroende av implicit databasloggning.

## 3. Stable identity and canonical fingerprints

Identitet och innehåll skiljs åt. Fingerprints beräknas från kanoniskt serialiserat innehåll och ska vara stabila över körningar.

**Konsekvens:** ordningen på osorterade samlingar, lokala sökvägar eller runtime-specifika värden får inte påverka hashresultat om de inte är del av domänens identitet.

## 4. Deterministic engines

Motorer ska vara rena eller nära-rena funktioner. De får inte läsa globalt tillstånd, aktuellt klockslag eller nätverksdata utan att detta uttryckligen skickas in som versionerad input.

**Konsekvens:** testfall kan köra samma input flera gånger och kräva identiskt resultat.

## 5. Explicit contracts

Publika modeller, services, CLI-format och modulmanifest är versionerade kontrakt. Privata implementationer får ändras så länge kontrakten bevaras.

**Konsekvens:** modulgränser ska kunna kontrolleras mekaniskt genom conformance och importregler.

## 6. Validation at boundaries

Fel ska upptäckas där data passerar en domängräns. Validering ska vara explicit och ge begripliga fel.

Exempel:

- projekt- och baseline-identitet måste matcha,
- valutor får inte blandas,
- totalsummor måste reconcileras,
- varje estimate line ska förekomma exakt en gång i strukturen,
- beslut får endast använda accepterade claims.

## 7. Human review is a first-class state

Review är inte en kommentar på ett objekt utan ett explicit domänsteg. Ett ärende kan vara öppet, godkänt eller avvisat enligt modellens kontrakt.

**Konsekvens:** systemet får inte tolka frånvaro av review som godkännande.

## 8. Rule engine before prompt logic

Regler som påverkar tekniska eller ekonomiska slutsatser ska vara versionerade och deterministiskt exekverbara. Prompttext får inte fungera som dold affärsregel.

**Konsekvens:** AI får föreslå en regelmatchning, men en explicit regel eller mänsklig review måste bära beslutet.

## 9. Security enforced by Backbone

Authentication kan delegeras externt, men authorization och tenant-gränser är plattformskontrakt. Moduler deklarerar permissions och får ett read-only authorization context.

**Konsekvens:** deny by default och central enforcement används; ingen modul får skapa en bypass.

## 10. Modular monolith by default

Crow använder modulär monolit så länge gemensam transaktion, typkontroll och enkel reproduktion ger större värde än distribuerad deployment.

**Konsekvens:** paketgränser behandlas som om de vore tjänstegränser, utan att introducera nätverkskomplexitet i förtid.

## 11. Services orchestrate; engines decide

- `models.py` uttrycker tillstånd och invariants.
- `engine.py` innehåller deterministisk domänlogik.
- `service.py` hanterar laddning, sparning och projektorkestrering.
- CLI/API-lager översätter användarinput men duplicerar inte regler.

## 12. Deny ambiguity, not only invalid data

Ett syntaktiskt giltigt objekt kan fortfarande vara semantiskt tvetydigt. Motorer ska kunna avstå från beslut när authority, baseline eller underlag är oklart.

## 13. Evidence before narrative

Förklaringar lagras strukturerat. Mänskligt läsbar text genereras från denna evidence.

**Konsekvens:** rapportformuleringar kan ändras utan att beslutets faktiska grund förloras.

## 14. Documentation is part of the contract

En modul är inte färdig när endast koden fungerar. Publik yta, invariants, fel, provenance och exempel ska dokumenteras.

## 15. Architecture fitness functions

Principer ska där det är möjligt översättas till automatiska kontroller.

| Princip | Kandidat till fitness function |
|---|---|
| Immutability | verifiera att domänmodeller är frozen/immutable |
| Determinism | kör samma fixtures flera gånger och jämför serialisering/fingerprint |
| Provenance | neka konstruktion av beslutsobjekt utan obligatoriska referenser |
| Modulgränser | AST/importkontroll mot privata korsimporter |
| Permission declaration | conformance jämför använda och deklarerade permissions |
| Tenant isolation | integrationstest med två tenants och RLS-policy |
| Reconciliation | property-based tests för totalsummor och deltas |
| Documentation | CI verifierar publika paket mot dokumentationsindex |
