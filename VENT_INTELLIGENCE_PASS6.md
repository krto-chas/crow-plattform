# Crow Vent Intelligence — Pass 6

## Implementerat

- `VentTextInterpreter` för deterministisk tolkning av textentiteter.
- Spårbar evidens till källfil, lager, entity handle, lagerprofil och lexikonversion.
- Batchtolkning som behåller okända värden för manuell granskning.
- Konfigurerbar lagerkedja:
  1. projektspecifik profil
  2. beställarprofil
  3. SB11
  4. konfigurerade CoClass-mönster
  5. frihandsprofil
- Tvetydiga komponentkoder, exempelvis `AF`, markeras för granskning om kontext saknas.
- Kanalsträngar och komponentbeteckningar levereras som typade resultat.

## Avgränsningar

- Ingen DWG-geometriparsning har lagts till.
- Ingen fullständig CoClass-tabell har införts; motorn accepterar verifierade projektmönster.
- Ingen BIP TypeID-tabell har införts.
- Okänd text tvingas inte till en klassificering.

## Verifiering

- Ruff: godkänd
- Mypy enligt projektkonfiguration: godkänd, 148 källfiler
- Pytest: 309 godkända
- RC-009-baslinje: godkänd
- Arkitekturgranskning ARC-001–ARC-004: godkänd
- Wheel och sdist: byggda
