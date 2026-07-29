# Pass 49 — Berghällen golden dataset

## Syfte
Registrera det verkliga förfrågningspaketet för Brf Berghällen (Norrberget etapp 2,
Besqab, bygghandling 2025-01-17) som golden project för provtrycknings- och
kalkylkedjan. Facit härleddes manuellt i det skarpa anbudsarbetet (som vann jobbet)
och blir målbild för Pass 50–56.

## Byggt
- `evidence/reference_datasets/berghallen/manifest.json` — 32 källor (arkivet +
  beskrivning, AF-del, förtydligande, HF, flödesschema och 25 planritningar) med
  SHA-256, roller och referenskvalitet. Kundfilerna hålls utanför repot (RC-011-mönstret).
- `evidence/reference_datasets/berghallen/expected_findings.json` — facit:
  täthetsklass C per kanalfamilj, känd B/C-konflikt (QL vs kravtabell),
  provningsomfattning 100/10/10/100, 3 strängar/lgh, lgh och längder per trapphus
  (33 lgh, 99 strängar, ca 808 m schakt, ca 137 m rektangulärt, tolerans 20 %),
  plushöjder samt beställarfrågor (33 vs 35 lgh m.m.).
- `scripts/build_berghallen_manifest.py` — deterministisk regenerering ur zipen.
- `tests/test_berghallen_dataset.py` — validerar manifestet, facitets interna
  konsistens (summor, 3-strängsregeln, monotona plushöjder) samt env-gated
  checksummeverifiering via `CROW_BERGHALLEN_ARCHIVE`.

## Kända begränsningar
- Trapphus 3/4-planerna saknar vektortextlager; lägenhetsdata där kräver raster
  eller DWG-original (deklarerat i manifestet).
- Längdfacit är bedömningar (±20 %), inte uppmätt verklighet.

## Grindar
Ruff 0, mypy strict 0 (209 filer), 447 tester + 1 env-gated skip
(verifierad grön mot den riktiga zipen separat).
