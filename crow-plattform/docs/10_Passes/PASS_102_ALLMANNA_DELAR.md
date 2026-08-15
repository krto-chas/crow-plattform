# Pass 102 — Allmänna delar: teknikutrymmen med checklistor

## Mål
Fältronderingen kompletterad med husets allmänna delar enligt fältverkligheten:
fläktrum med aggregat (FX/FT/FTX) kontrolleras mot en checklista, frånluftsfläkt
på tak eller vind får en egen kontrollpunktslista, båda fotodokumenteras med
märkskylt — och en kontrollpunkt utan kommentar är UA.

## Domänutökningar i `crow_ovk_field`
- `TechnicalSpace` (`flaktrum`/`takflakt`): benämning, placering (tak/vind/plan),
  valfritt system-ID.
- `FieldCheckpoint`: kontrollpunkt i utrymme. **Default är `pass` — punkt utan
  kommentar är UA.** En underkänd punkt kräver skriven notering, valideras både i
  modellen och serverside vid synk. Kontrollpunkterna bär redan `OBSERVED`-origin.
- `OvkPhotoEvidence` kan nu bindas till teknikutrymme (`space_id`) istället för
  lägenhet: minst en av bindningarna krävs, mediapipelinen (SHA-256-verifiering)
  är oförändrad. Ny lexikontyp `equipment_nameplate` (0.3) — dokumentation, inte
  brist.
- `nameplate_missing_spaces` ger utrymmen som saknar märkskyltsfoto; synk- och
  valideringssvaren rapporterar `technical_spaces`, `checkpoints`,
  `checkpoint_failures` och `nameplates_missing`.

## Checklistmallar (installationsdata)
`checklists.json` — kundutbytbar, laddas via `importlib.resources`, serveras på
`/api/ovk/field/checklists` och cachas offline (service worker v3):
- **Fläktrum (aggregat), 10 punkter**: filter, fläktdrift, remdrift/koppling,
  värmeväxlare, batterier, spjäll/ställdon, styr och regler mot driftkort,
  larmfunktioner, rensluckor/åtkomlighet, märkning och skyltning.
- **Takfläkt, 6 punkter**: fläktdrift, säkerhetsbrytare, skyddsgaller/huv,
  infästning, åtkomlighet, märkning och skyltning.

Etiketterna är operativa kategorier, inte juridiska slutsatser — samma disciplin
som feltypslexikonet.

## Appen
- Ronderingsvyn har fått kortet **Allmänna delar** med utrymmeslistan och knappar
  för nytt fläktrum respektive takfläkt (benämning + placering).
- Utrymmesvyn skapar checklistan ur mallen med alla punkter som UA. Ett tryck på
  en punkt + obligatorisk kommentar gör anmärkning; ett tryck till återställer.
  Dedikerad märkskyltsknapp öppnar kameran och binder fotot till utrymmet;
  statusraden visar om skylten är dokumenterad.
- Utrymmets radfärg i listan följer anmärkningsläget, och "skylt saknas" syns
  direkt på raden.

## Ägarskap och gate
Bygger på pass 101-grenen (ej main) så att 101 → 102 kan mergas i ordning.
Layoutmanifest 1.15, ägarskapsvakt och package-data (`checklists.json`) utökade.
Gate: `ruff format` → `ruff check` → `mypy --strict` → `pytest`. Tester täcker
mallarna, UA-som-default, noteringskrav vid underkänd punkt, fotobindning
utrymme/lägenhet, referensvalidering, märkskyltstäckning samt ytans
checklist-endpoint och synk-roundtrip med felrapportering.
