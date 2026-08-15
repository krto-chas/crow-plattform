# Pass 51 — Ritningsdata: lägenheter, plushöjder och textlagerbedömning

## Syfte
Automatisera det som lästes manuellt ur planritningarna i Berghällen-anbudet:
lägenhetsinventering (4T-PPNN), plushöjder och skalmätning — med explicit
flaggning när textlagret inte räcker.

## Byggt — nytt paket `crow_vent_drawing`
- `parser.py` — ritningsnummertolkning (V-57-1-PSSDD → plan/del),
  lägenhetsextraktion med RoK och area, plushöjder (+NN,NN → Decimal).
  Area markeras auktoritativ endast när ritningens plan matchar lägenhetens
  plan: förrådstabeller på plan 09 listar samma id med förrådsyta.
- `assessment.py` — `assess_drawing_text`: bostadsplanritning utan
  lägenhetsetiketter ⇒ `needs_raster_review` (raster/OCR/DWG krävs).
- `measurement.py` — `point_distance_m`: PDF-punktkoordinater × skalnämnare
  → verklig längd (Decimal, 2 dec), för längdbedömning ur etikettkoordinater.
- Env-gated verifiering (`CROW_BERGHALLEN_DRAWINGS`) mot de riktiga
  ritningarna: trh-1 8, trh-2 7, trh-3 10, trh-4 10, radhus 3 lgh.

## Fynd som korrigerar facit (rev 2)
Multi-extractorkörningen avslöjade att den manuella rasterläsningen i anbudet
undervärderade **trapphus 4: 10 lgh, inte 5** (44-1001–44-1302, plan 10–13).
pdftotext tappar delar av textlagret på 4xx04-serien; pypdf läser komplett.
Nya totaler: 38 lgh, 114 schaktsträngar, ca 947 m schaktkanal. Beskrivningens
35 lgh (hus C+D) stämmer därmed med ritningarna — den tidigare beställarfrågan
om lägenhetsantal utgår, och kalkylen för det vunna anbudet behöver revideras
upp med 15 strängar och en gjutetapp för trh 4.

Detta är plattformens kärnargument i praktiken: enkälleläsning ger tyst
undertäckning; tvingande korsläsning + review-flagga fångar den.

## Grindar
Ruff 0, mypy strict 0 (215 filer), 455 tester + 2 env-gated skips
(båda körda gröna mot riktiga kundfiler i byggmiljön).
