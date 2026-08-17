# OVK-protokollmallar — fältinventering

Transkription av referensmallarna (skärmbilder från befintlig iPad-app,
2026-08-17). Detta är specifikationen för Crow-plattformens protokollutdata:
i Crow är protokollet en **utdata från fältinsamlingen**, inte ett formulär
som fylls i för hand. Passreferenser anger var respektive del implementeras.

## A: Allmänt (→ pass 102, fastighetsentitet)

- Referensnr
- Adresser: fastighetsbeteckning; byggnadens adress + postnr + ort;
  byggnadsägare + postadress + postnr + ort; faktureringsadress + postnr + ort
- Förvaltare: fastighetsansvarig/förvaltare, telefonnr, fax/e-post
- Byggnad: internt byggnadsnamn, internt byggnadsnr, verksamhet, BRA i m²,
  antal lägenheter, antal lokaler

## B1: System (→ pass 101/104)

- Systemnr, besiktningskategori (1–7), besiktningsresultat, uppdragstyp,
  systemtyp, notering
- Datum: förra besiktning, denna besiktning, nästa besiktning, ombesiktning
- Bilagereferenser: D (åtgärder), L (flöde/drift/effekt), E (aggregatprotokoll),
  intyg
- Fritext: möjliga energibesparande åtgärder i systemet

## B2: Aggregat (→ pass 101, besiktningstäckning)

Per aggregat: systemdel, fläkttyp (–/F/FT/FTX/T/S), installationsår, placering,
projekterat flöde, uppmätt flöde, betjänar.

Detta är täckningslistan i pass 101: varje aggregat får explicit status
besiktigad / ej besiktigad (med skriftlig STATED-motivering) / ej tillämplig.

## B3 + D: Anmärkningar (→ pass 103/104)

Kolumner: pos (1.1–4.6), anmärkning (fritext), utfall (– / 1 / 2), kostnad kr.

Utfallsskalan mappar mot fältappens klassning: "–" = 0 (upplysning),
1 = godkänt men bör åtgärdas snarast, 2 = väsentlig brist → EG.

Positionstaxonomi (blir installerbart JSON-lexikon i pass 104):

- **1 Handlingar:** 1.1 Ritningar · 1.2 DU-instruktioner · 1.3 Föregående
  OVK-protokoll · 1.4 Proj. värden/luftflödesprotokoll · 1.5 Övrigt
- **2 Föroreningar:** 2.1 Uteluftskanal · 2.2 Filterdel · 2.3 Batterier ·
  2.4 VVX · 2.5 Fläktdel · 2.6 Kanaler · 2.7 Don · 2.8 Rensningsmöjligheter ·
  2.9 Fläktrum · 2.10 Övrigt
- **3 Funktioner:** 3.1 Filterdel · 3.2 Batterier · 3.3 VVX · 3.4 Spjäll ·
  3.5 Styr/Regler/Övervakning · 3.6 Fläktar · 3.7 Luftflöden · 3.8 Kanaler ·
  3.9 Don · 3.10 Övrigt
- **4 Klimat:** 4.1 Temperatur · 4.2 Odör · 4.3 Drag · 4.4 Ljud ·
  4.5 Brukarsynpunkter · 4.6 Övrigt

## E: Aggregatprotokoll (→ pass 104, teknikdata)

- **Aggregat:** aggregatbenämning (obligatorisk för OVK1), fabrikat, typ,
  placering, betjänar, VVX-typ
- **E2 Tilluft / E3 Frånluft** (samma struktur): q tot l/s, pt Pa, pk Pa,
  Δp värmebatteri, Δp kylbatteri, Δp efterfilter, Δp vvx, tillufttemperatur —
  vardera projekterat + uppmätt. Filter 1/2: typ/klass, antal filter,
  höjd/bredd/djup (cm), antal påsar. Drifttimmar/v: delfart + helfart.
  Anmärkning (fritext).
- **E2/E3 Motor:** fabrikat/typ, varvtal n/min, fläkthjulstyp, fläktskiva diam,
  motorskiva diam; helfart + delfart: P märkeffekt kW, P mätt effekt kW,
  märkström A, driftström A, cos φ, frekvens Hz, nfl fläktvarvtal

## L + Luftflödesprotokoll (→ pass 105, flödesprotokoll)

- Huvud: aggregatbenämning, ritning, flödesenhet (l/s | m³/h), driftstid
  start/stopp, märkeffekter, anmärkning
- Per rum: rumsnr, benämning, anmärkning; tilluft respektive frånluft:
  proj, uppmätt, % av proj, mätmetod (val från lista)
- Fristående luftflödesprotokoll: rumsnr/placering, typ, pi pa, beräknat,
  uppmätt per till-/frånluft; totalrad
- Sammanfattningsfält: totalt, sannolikt M

## Signering (→ pass 107, avslutsflöde)

- Besiktningsman: namn, telefonnr, fax/e-post, företag, postadress, postnr, ort
- Certifiering: certifieringsorgan, certnummer, giltighetstid, behörighetsnivå
- Underskrift och kommentar: kommentar (fritext), **ritad namnteckning**
  (penna/finger), ort, datum
- "Samtliga ventilationssystem för byggnaden ingår i besiktning: Ja/Nej" —
  motsvarar fastighetsnivåmarkeringen i pass 101
  (`samtliga_besiktade` / `delvis_besiktade` / `systemforteckning_ej_bekraftad`)

## Övriga formulär (parkerade, egen modul senare)

Servicechecklistor fläktrum/undercentral (kontrollpunkter 1–28 fläktar,
32–48 undercentral, 53–60 inställningar; utfallskoder 0–9), lägenhetsbesiktning,
media-avläsning, egenkontroll, åtgärdslista, nyckelkvittens, SBA.

Utfallskoder 0–9 i servicechecklistan: 0 ej aktuell/ingår ej ·
1 kontrollerad/funktionstestad UA · 2 justerad/kalibrerad · 3 rengjord/smord ·
4 utbyte av förslitningsdetalj (debiteras) · 5 enhet ej åtkomlig ·
6 kontrollerad med konstaterad brist · 7 enhet som måste bytas ut snarast ·
8 akut åtgärd vidtagen direkt (tid/material specificeras) ·
9 förekommer ej, men borde finnas.
