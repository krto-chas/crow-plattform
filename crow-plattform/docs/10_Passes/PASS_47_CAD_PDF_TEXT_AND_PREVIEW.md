# Pass 47 — CAD-PDF-textreparation och inline-förhandsvisning

## Bakgrund (skarp körning mot Mandelblomman)
Textextraktionen ur relationsritningens PDF gav skiftad teckenkodning:
CAD-exporter bäddar in fontsubset vars teckenkarta är förskjuten +0x1D
från ASCII. `(175e` = ENTRÉ, `+$1'/b**$5(` = HANDLÄGGARE,
`XQGHUYnQLQJ` = undervåning, `Pð` = m².

## Textreparation: `crow_document_intelligence.cad_pdf_text`
- Token-vis remappning: +0x1D för ASCII-intervallet plus specialtabell för
  ÅÄÖÉ/åäö/²³. En token remappas bara när kandidaten är övervägande
  plausibel svenska OCH råformen är implausibel (konsekvent versaliserade
  rena ord som TRAPPHUS lämnas orörda; blandcasemönstret XQGHUYnQLQJ
  fångas). Rena tal/datum/skalor (2014-02-12, 1:50) remappas aldrig —
  mått väger tyngre än det sällsynta skiftade sifferordet.
- Evidensbevarande: dokument-endpointen levererar reparerad text i `text`,
  originalet i `raw_text` och antal remappade tokens — lagrad extraktion
  muteras inte.

## Inline-förhandsvisning
`FileResponse(..., filename=...)` satte `Content-Disposition: attachment`,
vilket fick webbläsaren att ladda ner PDF:en istället för att visa den i
Explorer-iframen. Båda filendpoints (documents + imports) skickar nu
`content_disposition_type="inline"` — förhandsvisningen fungerar direkt.

## DWG-konverteraren (diagnos, ej kodändring)
Konverteringsstatusen är strukturerad och synlig: Import Manager →
markera DWG-filen → Model Inspector visar `conversion.status` + `reason`.
Trolig status: `converter_unavailable` → installera ODA File Converter
(gratis, registrering hos opendesign.com) och sätt på Windows:
`setx CROW_ODA_CONVERTER "C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe"`
(starta om terminalen efteråt). Visar den annan status: skicka reason.

## Notera om "läsa ritningen"
PDF-ritningen är presentationsformatet — text och evidens hämtas därifrån,
men geometrin (kanaler, mängder) ska komma ur DWG/DXF-källan via
geometrikedjan. När ODA-konverteraren är igång faller det på plats.

## Verifiering
3 nya tester byggda på de verkliga Mandelblomman-strängarna. Totalt 423
gröna, mypy strict 205 filer, ruff 0.
