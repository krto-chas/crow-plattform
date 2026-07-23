# Pass 43 — DWG-läsning via isolerad ODA-konvertering

## Vad
`crow_dwg_conversion` kör ODA File Converter (gratis binär från Open Design
Alliance) som isolerad subprocess: DWG in → härledd DXF ut, som sedan läses
av den befintliga DXF-kedjan. Crow länkar aldrig mot konverteraren.

## Hardening (gap-analysens punkt 5, tillämpad)
- Filsignatur (`AC…`), filändelse, tom fil och storleksgräns (500 MB default)
  kontrolleras FÖRE anrop; avslag är strukturerade (input_rejected + skäl).
- Timeout (120 s default) och saniterade filnamn i scratch-kataloger;
  konverteraren ser aldrig originalsökvägen.
- Alla utfall är strukturerade ConversionResult — converted /
  converter_unavailable / input_rejected / timeout / failed — aldrig tysta
  förluster, aldrig oväntade exceptions i pipelinen.

## Evidenslänkning
Original-DWG förblir orörd och auktoritativ; härledd DXF får suffixet
`.derived.dxf` och länkas via SHA-256 för både original och derivat plus
konverterarversion (ACAD2018). Policyn följer geometry-adapterns befintliga
formulering.

## Integration
`DwgPlugin` i import-frameworket anropar nu konverteraren: lyckas den
registreras konverteringsbeviset i metadata och användaren hänvisas till den
härledda DXF:en; saknas konverteraren faller pluginen tillbaka till dagens
beteende med status i varningen. Discovery: env `CROW_ODA_CONVERTER` eller
`ODAFileConverter` i PATH.

## Verifiering
Testerna använder en fejkad konverterar-binär med samma CLI-kontrakt, vilket
verifierar hela flödet (discovery, isolering, checksummelänkning, timeout,
felkoder, otillgänglig konverterare) utan den proprietära binären: 6 nya
tester, totalt 414 gröna, mypy strict 203 filer, ruff 0.

## Driftnot
Installera ODA File Converter på servern/klienten (gratis licens, kräver
registrering hos ODA) och sätt CROW_ODA_CONVERTER. Verifiera mot en riktig
projekt-DWG (Mandelblomman) som första skarpa test — jämför den härledda
DXF:ens mängder mot golden-materiallistan.
