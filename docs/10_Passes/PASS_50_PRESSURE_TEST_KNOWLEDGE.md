# Pass 50 — Provtryckningslexikon och kravextraktion

## Syfte
Första domänsteget mot automatiserad provtryckningsanalys: en enda kunskapskälla
för täthetsklasser/standarder samt STATED-extraktion av krav och omfattning ur
klartext, med konfliktdetektering för Berghällen-fallet (klass B vs C).

## Byggt — nytt paket `crow_pressure_test`
- `tathetsprovning_lexikon.json` — täthetsklass A–D med läckagefaktorer
  (0.027/0.009/0.003/0.001), ATC-mappning (SS-EN 16798-3), formeln
  f_max = c·p^0,65, standardregister (SS-EN 1507/12237/14239/16798-3/12599,
  AMA VVS & Kyla 19) och kanalfamiljstermer.
- `knowledge.py` — `PressureTestKnowledge` med `allowed_leakage_flow`
  (q_max = c·|p|^0,65·A, Decimal-kvantiserad till 6 decimaler, ADR-0009-andan).
- `models.py` — `TightnessRequirement`, `TestScopeRequirement`,
  `TightnessConflict` (med `strictest_class`) och `ClaimOrigin`
  (STATED = klartext med citat/locator, INFERRED = härlett ur standard/regel —
  separationen som efterfrågades i anbudsarbetet).
- `extraction.py` — radbaserad extraktion: `täthetsklass X` binds till närmaste
  kanalfamilj (hanterar sammansatta meningar → ett krav per klassförekomst),
  omfattningsrader `<familj>: NN %`, samt `find_conflicts` per kanalfamilj.

## Medvetna avgränsningar
- Paketet är fristående (ingen import av crow_vent/observation-kedjan) enligt
  ADR-003-mönstret; integration mot observation/claim-pipelinen och authority
  sker i senare pass, liksom flytt in i vent-modulen.
- Extraktionen är radbaserad klartext; PDF-regioner/tabellsemantik kommer via
  befintliga pdf_evidence-kedjan i Pass 51.

## Grindar
Ruff 0, mypy strict 0 (209 filer), 447 tester gröna varav 13 nya för paketet.
