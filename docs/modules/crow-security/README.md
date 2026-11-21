# CROW Security – dokumentation och idébank

**Status:** planerad modul; dokumentation under utredning  
**Senast uppdaterad:** 2026-11-21  
**Berörd modul:** `crow.security` (föreslaget modul-ID)  
**Beslutsfattare:** produktägaren

CROW Security är en tänkt fristående verksamhetsmodul för inventering, analys, säkerhetsuppföljning och underlag för rådgivning till kundorganisationer. Den ska kunna installeras och avaktiveras oberoende av OVK och andra verksamhetsmoduler.

## Dokument
- [Edge – arkitektur och krav](edge/ARCHITECTURE.md): collector, gateway, säkerhetsgränser, topologi, datamodell, faser och acceptanskriterier.

## Beslutade produktprinciper
- CROW Platform ska kunna starta helt utan verksamhetsmoduler.
- Säkerhetsmodulen ska inte lägga domänlogik i kärnan.
- Kundens ansvar för beslut och förändringar ska hållas isär från CROW:s inventering, analys, rekommendationer och verifiering.
- Logisk och fysisk nätverksmodell ska finnas med i designen från början.

## Öppna frågor
- Produktnamn, exakt modul-ID och licensmodell.
- Val av Edge-hårdvara, operativsystem och livscykelhantering.
- Val av beständig databas och driftmodell för flera kunder.
- Vilka discovery-integrationer som prioriteras i första pilot.

**Ingen Edge-implementation ingår i detta dokumentationsförslag.**
