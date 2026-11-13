# CROW OVK — Produktvision 2.0

Status: beslutad avgränsning efter PR #174; vision, inte implementerad funktion.
Förutsättning: OVK 1.0 har passerat R1–R6 och fungerar i verklig besiktning.

## Mål

Återanvänd verifierad installationsinventering från OVK för teknisk dokumentation, utan separat CAD-inmatning. Driftkort är ett separat levererbart dokument, inte ett automatiskt bevis på att alla erforderliga handlingar finns.

## Informationsmodell

- Byggnad, våningsplan, trapphus, lägenhet, lokal, rum och beständiga don.
- Fysiskt schakt/skorstensstock skiljs från enskilda luftvägar. Flera separata kanaler kan finnas i samma schakt.
- Don ansluts till kanal, inte en hel lägenhet till ett schakt. Kök och WC kan dela kanal medan bad har separat kanal. Individuella självdragskanaler och gemensamma samlingskanaler stöds.
- Kanalnät med förgreningar, anslutningar, fläktar, aggregat och avluft/uteluft. Tilluft och frånluft skiljs åt.
- Grafisk placering och teknisk topologi hålls separata. Flytt av ett lägenhetsblock ändrar inte kanalanslutningen.
- Mallar kan föreslå anslutningar, inklusive individuella kanaler per lägenhet. Förslag är inte verifierade observationer. Dokumentera källa, verifieringsstatus och revision.

## Utvecklingsordning

1. Våningsplan, schakt, separata kanaler och beständiga referenser.
2. CAD Light: automatisk schematisk elevation från lägenhetsnummer, drag-and-drop, storleksändring, snap-to-grid, zoom, panorering, lager, ångra/gör om. Avvikande entréplan, lokaler och förskjutna schakt ska kunna modelleras. Inte skalenlig CAD som standard.
3. Donanslutningar, förgreningar, brytpunkter, systemfilter och verifiering av nätet. Separera grafiska korsningar från faktiska förbindelser.
4. Systemflödesschema med fläkt/aggregat, betjäningsområde och summerade projekterade/uppmätta flöden. Redovisa omfattning, saknade värden och mätmetod; summan av don är inte automatiskt lika med uppmätt fläktflöde.
5. Installations- och styrkomponenter: frekvensomvandlare, tryckgivare före/efter fläkt, utetemperaturgivare, flödesgivare, larm, tidkanal, brandfunktion, filter, värmeväxlare, batterier, spjäll och frysskydd. Ange reglerprincip, signalrelationer och verifierade inställningar.
6. Automatiska styr- och reglerprincipscheman. Komponentval skapar förslag; faktiska signaler och funktioner måste verifieras.
7. Driftkort: återanvänd fastighet, system, märkskylt, bilder, checklistor, mätdata, börvärden och tekniska data. Fritext för funktion, drift och underhåll. Skilj projekterat, börvärde och uppmätt. PDF/SVG, granskning, revision och spårbar källa. Ingen automatisk avskrivning av OVK-anmärkning.

## Avgränsning

Ingen CAD-editor, schaktmodell eller driftkortsgenerator i 1.0. Lägenhetsmallar, nummerregler, beständiga don och korrekt fältdata ingår i 1.0 eftersom de direkt minskar besiktningsarbetet. React Flow eller annan editor utvärderas först i 2.0; inget ramverksbeslut nu. Generell plattformsutveckling för dessa funktioner skjuts också upp.

## Acceptans

Testa äldre självdragshus med flera kanaler per skorstensstock, delad kök/WC-kanal, avvikande bottenplan, central F-fläkt och FTX. Flytt av grafiska objekt får inte ändra tekniska kopplingar. Export ska vara reproducerbar, läsbar och tydligt märka antaganden. Kontrollant verifierar driftkort och bedömer om ytterligare handlingar krävs.
