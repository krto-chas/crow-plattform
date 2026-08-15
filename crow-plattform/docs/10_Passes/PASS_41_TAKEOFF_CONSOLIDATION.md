# Pass 41 — Multi-source takeoff consolidation

## Syfte
Kalkylens delmängder ska kunna hämtas ur flera handlingstyper och stämmas av
mot varandra: DXF-geometri (via crow-vent-quantity-v0.3), Excel/CSV-
mängdförteckningar och beskrivningstext (PDF/DOCX-segment). Ingen källa väljs
tyst framför en annan — avvikelser blir beställarfrågor, i linje med
evidensprincipen.

## Nytt paket: `crow_takeoff_consolidation`
- `models.py` — SourceLine/SourceTakeoff, radnyckel (kind, code, dimension),
  deterministiska line-id (SHA-256), statusmodell: single_source /
  corroborated / discrepant / unit_mismatch.
- `extractors.py` — tre extraktorer med förlustrapportering (skipped med
  reason, aldrig tysta bortfall):
  - `takeoff_from_geometry` adapterar befintlig geometri-takeoff.
  - `takeoff_from_table` läser kalkylbladsrader; identiteter valideras mot
    ventlexikonet (kanalsträngar som `T-125`, komponenter som `TD1`), mängd
    hämtas ur närmaste numeriska cell, enhet ur enhetscell (m/st) oavsett
    om den står före eller efter talet.
  - `takeoff_from_text` fångar "N st <beteckning>" i löptext; kanalsträngar
    utan längd i prosa rapporteras som skipped, inte som mängd.
- `consolidate.py` — sammanslagning per radnyckel: antal kräver exakt
  överensstämmelse, längder tolereras inom 2 % relativt källan med högst
  konfidens; enhetskonflikter medelvärdesbildas aldrig; discrepant/
  unit_mismatch-rader exkluderas ur totaler och genererar beställarfrågor.
  Schema: `crow-takeoff-consolidation-v0.1`.

## Designnoter
- Radnyckeln är domänneutral — VS- och el-moduler kan återanvända
  konsolideringen oförändrad med egna lexikon.
- Nyckelalignment mellan källor förutsätter att alla extraktorer använder
  samma lexikon (RC-011); geometrilinjens component_code måste komma från
  samma klassificering.
- Nästa steg: koppla consolidated lines → estimate lines (prisbok per
  radnyckel) samt XLSX-läsning via import-frameworkets XlsxPlugin i
  orchestratorn.

## Verifiering
Ruff 0 fel, Mypy strict 0 fel, 407 tester (6 nya) gröna. Se
PASS41_VERIFICATION.json.
