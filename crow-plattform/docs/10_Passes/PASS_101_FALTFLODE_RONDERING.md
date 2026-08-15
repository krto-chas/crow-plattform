# Pass 101 — Fältflöde 2.0: rondering

## Mål
Fältappen omdesignad kring den verkliga arbetsgången vid en OVK-förrättning, med
målet att en UA-lägenhet ska ta under 30 sekunder och en lägenhet med full mätning
under ett par minuter. Arbetsgången i appen speglar nu förrättningen steg för steg:
trapphus → lägenhet (visuell runda → mätning av samtliga don → övriga noteringar) →
nästa lägenhet.

## Domänutökningar i `crow_ovk_field`

### Enhetsstatus och täckning
- `UnitStatus`: `ej_paborjad` → `ua` / `anmarkning` / `bom`. UA och anmärkning
  kräver `checked_at`; bom kräver `bom_at` (tid och datum stämplas automatiskt i
  appen) med valfri notering.
- Serverside statuskonsistens: en UA-enhet får inte bära anmärkningar
  (minor/major; info är tillåtet), och en bom-enhet får varken bära anmärkningar
  eller mätningar. Synk- och valideringssvaren rapporterar `unit_status_counts`
  och `coverage_complete` — täckningen är därmed bevisbar och trapphus 4-missar
  syns direkt.

### Nyckelspårning
`KeyLog` per enhet: mottagen/återlämnad med obligatoriska tidsstämplar, återlämning
kräver föregående mottagning, och huvudnyckel kräver alltid en skriven kommentar
för spårbarhetens skull.

### Mätning vid varje don
`FieldMeasurement` med `MeasurePointType` (frånluft/tilluft/överluft), Decimal-värden
i l/s (`parse_flow_value` accepterar svensk kommanotation), projekterat värde och
härledd avvikelse. Ej mätbara don kräver skriven orsak **och** en kopplad anmärkning
(`terminal_not_measurable`) — fotot på varför binds via anmärkningen, så
beviskedjan don → orsak → foto håller ihop.

### Fönsterventiler
`WindowVentCheck` är en ren finns/finns ej-kontroll — aldrig mätning. Kontrollerna
är helt dolda i FT/FTX-fastigheter; systemtypen (S/F/FX/FT/FTX) lagras i
fältkontexten och valideras på servern. "Saknas" registrerar både kontrollen och
en anmärkning.

### Feltypslexikon 0.2
Fyra nya operativa typer: `kitchen_fan_central_system` (köksfläkt mot centralt
system), `window_vent_missing`, `terminal_not_measurable` och
`general_damage_observation` (t.ex. vattenläckage — noteras och fotograferas).

## Appen (`field.html` + `field.js`)
- **Start**: projekt, besiktnings-ID, besiktningsman, systemtyp och
  nummerserie-generator för Lantmäteriets fyrsiffriga nummer
  ("1001-1004, 1101-1104" → enhetslista).
- **Rondering** (signaturelementet): segmenterad progressstapel där varje segment
  är en enhet och färgas grön/gul/röd när den klaras, med räknare för klara,
  anmärkningar, bom och mätningar. Lägenhetsnumret är radens största objekt.
- **Enhetsvyn** följer arbetsgången: nyckelknappar (mottagen/huvudnyckel/återlämnad)
  → BOM-knapp → rum-chips → snabbanmärknings-chips med autogenererad beskrivning →
  mätrader med stora numeriska fält och "Ej mätbar"-knapp → anteckning + foto.
- **Ett tryck klart**: "Klar – UA" (grön) eller "Klar – med anmärkning (n)" (gul)
  stämplar status + tid och öppnar automatiskt nästa opåbörjade enhet.
- Foto binds automatiskt till senaste anmärkning — inget separat kopplingssteg.
- Offline-first behållet: IndexedDB, service worker (cache v2), utkast med alla
  nya fält; äldre snapshots utan de nya fälten förblir giltiga (alla nya fält har
  defaults).

## Ägarskap och gate
Layoutmanifest 1.14: `test_ovk_field_round.py` i `owned_tests`; ägarskapsvakten
utökad. Gate: `ruff format` → `ruff check` → `mypy --strict` → `pytest`. Tester
täcker nyckelregler, statustidsstämplar, Decimal-parsning och avvikelse,
UA/bom-konsistens, ej mätbar-kopplingen, fönsterventilreferenser, synk-roundtrip
med täckningsrapport samt systemtypsvalidering i kontexten.
