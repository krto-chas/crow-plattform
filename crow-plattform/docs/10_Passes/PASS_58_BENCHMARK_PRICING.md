# Pass 58 — Schablonprissättning för entreprenader (`crow_benchmark_pricing`)

> Bygger ovanpå Pass 57-grenen; appliceras efter att Pass 57 mergats.

## Syfte

Erfarenhetsbaserade schablonpriser (nyckeltal) per enhet för
entreprenadprissättning — kr/lgh, kr/rum, kr/m² BTA, kr/hus — med två
användningsfall:

1. **Snabbindikation** innan handlingar finns: kvantitet × spann ger en
   grov prisbild i tre nivåer (låg/normal/hög).
2. **Rimlighetskontroll** av detaljkalkylen: den prissatta
   mängdförteckningen ur Pass 44 (`crow-takeoff-pricing`) jämförs mot
   schablonspannet; utanför spann flaggas avvikelsen med riktning och
   procent mot normalvärdet.

## Ärlighetsprinciper

- Ett schablonresultat är alltid **inferred** — erfarenhetstal, inte
  kalkyl — och payloaden bär det öppet.
- Spannet låg/normal/hög bär osäkerheten i stället för att ett enda
  tal låtsas vara precist. Spannordningen valideras
  (0 < låg ≤ normal ≤ hög).
- Adaptern mot Pass 44-payloaden lägger **förbehåll** när kalkylen har
  oprissatta rader eller reservationer: totalsumman är då en undre
  gräns, och jämförelsen redovisas aldrig utan att ofullständigheten
  syns.

## Arkitektur

- `models.py` — `BenchmarkRange`, `Benchmark`, `QuickEstimate`,
  `BenchmarkComparison`, `ComparisonVerdict` (below/within/above).
- `book.py` — `BenchmarkBook` laddar `schablon_lexikon.json` via
  `importlib.resources`; nyckeltal per disciplin (`vent` nu, `vs`/`el`
  ryms i formatet). Beloppen är exempeltal (installationsdata) som
  ersätts med egna erfarenhetstal — den egna schablonboken blir med
  tiden en av installationens värdefullaste tillgångar.
- `estimate.py` — `quick_estimate`, `compare_detailed_total`,
  `compare_takeoff_pricing` (Pass 44-adapter med schemakontroll och
  förbehåll), payload-serialisering med belopp som strängar.

Rent paket: standardbiblioteket, ingen PDF/UI-koppling.

## Avgränsningar / framtida arbete

- Automatisk kalibrering av spann ur avslutade projekts utfall
  (efterkalkyl → schablonbok) är medvetet framtida arbete.
- Kombinerade schablonobjekt (flera nyckeltal i en indikation, som
  OVK-modulens delposter) ryms i formatet men byggs när behovet finns.
- Workbench-vy för snabbindikation och avvikelsekort hör till
  frontendpasset.

## Grindar

Ruff 0, mypy strict 0 i 217 filer, 13 nya tester (lexikonladdning,
spannvalidering, indikationsskalning, inferred-markering, alla tre
utfallen, Pass 44-adapter med förbehåll och schemakontroll,
determinism).
