# Pass 54 — Leverabler: offertkalkyl och protokoll som xlsx

## Syfte
Excel som presentationsadapter på riktigt (ADR-0004): kalkyl och
täthetsprovningsprotokoll genereras ur payloader och kunskapskälla —
arbetsböckerna innehåller ingen egen sanning.

## Byggt — nytt paket `crow_offer_export`
- `write_offer_workbook` — Sammanställning (rader, summa, rekommenderat fast
  pris, reservationer synliga) + en flik per trapphus med mängdfakta.
  Beloppen kommer ur offertpayloaden; inga beräkningsformler i vyn.
- `write_protocol_workbook` — protokollet genereras ur
  `PressureTestKnowledge`: kravtabellen (faktorer, ATC, exempel vid 400 Pa)
  och standardregistret kan aldrig divergera från kalkylens värden.
  Provningsraderna får q_max-formel (VLOOKUP mot kravtabellen, ^0,65) och
  GODKÄND/EJ GODKÄND i arket för fältbruk.
- `openpyxl` tillagt som optional extra `export` (ingår i dev), med
  mypy-override; kärnplattformen förblir beroendefri från Excel.

## Skarp validering (byggmiljön)
Hela kedjan körd på riktiga Berghällen-PDF:er: ritningar → 114 strängar →
offert 187 350 kr / fast pris 197 000 kr (rev 2-mängderna) → två xlsx-filer.
Jämfört med det manuella anbudets 175 625/184 000 vid 99 strängar är
skillnaden exakt trapphus 4-korrigeringen — kedjan reproducerar och
förbättrar det manuella arbetet.

## Grindar
Ruff 0, mypy strict 0 (222 filer), 469 tester + 3 env-gated skips.
