# Pass 44 — Prissättning av konsoliderad mängd (grundkalkylen)

## Vad
`crow_takeoff_consolidation.pricing` sluter kedjan handling → delmängd →
kalkylrad: upplösta konsoliderade rader matchas mot prisboksposter på samma
radnyckel (kind, code, dimension) och ger material- och arbetsbelopp per rad
samt projekttotaler i SEK.

## Modell
- `PriceBookEntry`: nyckel + enhet + materialpris/enhet + montagetid
  (h/enhet), med `*` som dimensionswildcard (exakt träff vinner).
- `PriceBook`: id, valuta, timkostnad, poster.
- `price_consolidated_takeoff(consolidated, price_book)` →
  `crow-takeoff-pricing-v0.1` med priced/unpriced/reservations, material-,
  arbets- och totalsummor, och beställarfrågorna vidareförda.

## Principer
- Endast upplösta rader prissätts. Discrepant/unit_mismatch blir
  reservationer — kalkylen innehåller aldrig en siffra källorna inte bär.
- Opris-satta rader rapporteras med skäl (no_price_entry /
  price_unit_mismatch). Inga tysta förluster.
- Deterministisk: samma indata → identisk payload (testat).

## Designbeslut
Befintliga EstimateLine har delta-förankrad proveniens
(commercial_impact_id, scope_impact_id …) byggd för ÄTA-flöden. Grund-
kalkylens proveniens är källbaserad (source lines + status), så den får ett
eget schema istället för fejkade delta-id:n. Adapter in i EstimateRevision-
jämförelsen är nästa steg när proveniensmodellen generaliseras.

## Verifiering
4 nya tester (totaler/exkluderingar, wildcard + enhetsvakt, schemavakt,
determinism). Totalt 418 gröna, mypy strict 204 filer, ruff 0.
