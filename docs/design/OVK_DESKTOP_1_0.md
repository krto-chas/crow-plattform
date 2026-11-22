# CROW OVK Desktop 1.0 – arbetsflöde och saknade kontrakt

Status: produktkrav och genomförandeplan, inte implementeringsbevis.
Datum: 2026-11-21. Underlag: kodläsning av `main` @ `330f0d4`; inga tester eller webbläsare kördes för inventeringen.
Konkretiserar [masterprompten för Desktop 1.0](../modules/crow-ovk/DESKTOP_MASTERPROMPT_1_0.md) och [backend-gapet med första pass](../modules/crow-ovk/DESKTOP_BACKEND_GAP_AND_PASS_1.md). Kompletterar [OVK-roadmapen](../OVK_PRODUCT_ROADMAP_1_0.md) och [property-first](OVK_PROPERTY_FIRST.md). Besluten finns i [ADR-013](../adr/ADR-013-ovk-desktop-workspace.md). Befintliga releasegrindar gäller.

## Mål

En användare startar ett verkligt uppdrag, förbereder det på kontoret, genomför besiktningen i fält, synkroniserar, granskar, utfärdar och levererar kompletta dokument utan att registrera något två gånger.

Första piloten är en ensam besiktningsman. Flera användare ska fungera, men får inte göra det enkla fallet tyngre.

## Ord

- **Organisation**: företaget som använder Crow. I koden `customer_id`.
- **Kund**: den som besiktningen görs åt, fastighetsägaren eller beställaren.
- **Uppdrag**: en planerad eller pågående besiktning av en byggnad. I koden en `inspection` med `planning`.
- **Del**: en mängd lägenheter, lokaler eller teknikutrymmen i ett uppdrag som tilldelas en besiktningsman.

## Arbetsytor

Gemensamt skal med fast vänsternavigation. Varje yta visar verkliga data, tomläge, laddning och fel.

| Yta | Innehåll | Bygger på |
|---|---|---|
| Översikt och arbetskö | Mina uppdrag, att granska, att utfärda, öppna åtgärder; nästa steg per rad | `/ovk`, `dashboard.html` |
| Uppdrag och planering | Skapa, schemalägg, tilldela, följ framdrift | `/ovk/besiktning`, `InspectionPlanning` |
| Kunder och fastigheter | Kund, fastighet, byggnad, trapphus, lägenhet, lokal, system | `/ovk/fastighet`, strukturregistret |
| Besiktningar och uppföljning | Framdrift, täckning, tillträde, återbesök, synkstatus | fältögonblicksbilden |
| Granskning | Mätvärden, anmärkningar, foton, saknade uppgifter, komplettering | `workflow.js`, protokollutkast |
| Protokoll, intyg och bilagor | Förhandsgranska, utfärda, leverera | `/ovk/intyg`, exporten |
| Bevakning och ombesiktningar | Nästa OVK, frister, åtgärder | `/ovk/bevakning`, `/ovk/ombesiktning` |
| Administration och inställningar | Användare, roller, besiktningsmän, företagsuppgifter | besiktningsmannaregistret, `/admin` |

Projektverktyg, import av äldre protokoll och tidrapportering finns kvar men ligger inte i huvudflödet.

## Flöde och tillstånd

Kund och fastighet → byggnad och system → planerat uppdrag → tilldelning → fältarbete → synk → granskning → eventuell komplettering → godkänt underlag → utfärdande med underskrift → leverans → bevakning → eventuell ombesiktning.

Visningsstatusarna utgår från roadmapen. De härleds ur befintliga uppgifter och lagras inte som ett eget tillstånd. Går underlaget inte att läsa, eller hänger det inte ihop, redovisas uppdraget som oläsbart i stället för att få en status.

| Status | Härleds ur |
|---|---|
| Ej planerad | post utan planering och utan fältdata |
| Planerad | planering finns, ingen ögonblicksbild |
| Pågående | ögonblicksbild finns, fältarbetet inte klarmarkerat, posten inte klar att utfärda |
| Att granska | fältarbetet klarmarkerat men posten inte klar att utfärda |
| Leveransklar | posten protokollklar och protokollkällan svarar mot fältets ögonblicksbild; inget intyg. Saknas klarmarkering i fält visas en upplysning |
| Utfärdande avbrutet | utfärdandemanifest finns utan intyg |
| Utfärdad | ett intyg med ställningen gällande |
| Åtgärder öppna | utfärdat med brister och inget ombesiktningsärende |
| Ombesiktning | senaste ombesiktningsärendet är öppet |

Utfärdande kräver inte att fältarbetet är klarmarkerat i fältappen (beslut 2026-11-21). Målet är att det klarmarkeras i fält när arbetet är klart; saknas markeringen visas det som en upplysning, inte som ett hinder.

Levererad tillkommer när leveranser registreras (D8); till dess är Utfärdad sista steget. Godkänd granskning för aktuell revision kontrolleras vid utfärdandet och vägs in i Leveransklar när granskningsarbetsplatsen byggs (D7).

Besiktningsresultat, täckning, synkstatus och leveransstatus visas var för sig.

## Roller

| Handling | Administratör | Arbetsledare | Besiktningsman | Granskare |
|---|---|---|---|---|
| Användare och roller | ja | | | |
| Kunder och fastigheter | ja | ja | ja | |
| Skapa och planera uppdrag | ja | ja | egna | |
| Tilldela och omfördela | ja | ja | | |
| Fältarbete och synk | | | tilldelade delar | |
| Granska och begära komplettering | | | egna | ja |
| Godkänna underlag | | | egna | ja |
| Utfärda och leverera | | | ansvarig för uppdraget | |

En organisation med en enda aktiv användare har alla roller utan inställning.

## Saknade kontrakt

Varje punkt är ett eget arbete. Ingen ny backend där en befintlig rutt räcker.

1. **Uppdragsöversikt.** En serverrutt som ger organisationens uppdrag med härledd status, täckning och nästa steg. I dag hämtar webbläsaren alla projekt och sedan besiktningar per projekt.
2. **Behörighetskontroll.** En gemensam beroendefunktion för OVK-rutter som tar önskad handling och läser kärnans session (ADR-013 punkt 2), samt en gemensam omfångsfunktion för vilka projekt en rutt får se (punkt 3).
3. **Kund.** Kundpost i OVK-modulen som fastigheter pekar på. Befintliga fält för byggnadsägare och förvaltare ligger kvar på fastigheten.
4. **Fastighetssökning.** Sökning över organisationens befintliga fastighetsregister och "ny besiktning på samma fastighet". Ägarskapet flyttas inte (ADR-012).
5. **Trapphus och våning** i strukturregistret, så att delar kan tilldelas per trapphus. Trapphus finns som egen lista i byggnadens struktur (namn och adress); varje lägenhet eller lokal kan peka på sitt trapphus, och enhetslistan är fortsatt platt så att den frysta besiktningsstrukturen och fältappen är oförändrade. Gathus och gårdshus registreras som egna byggnader. Lägenhetsnummer är unika per trapphus, så samma nummer får finnas i flera trapphus. Registret lagrar numret i trapphuset ("1101") och fryser strukturen oförändrad i besiktningen. Fältappen gör trapphusen till portar: porten anges på ett ställe, ronderingen visar en port i taget med fyrsiffriga nummer, och när portens sista enhet är gjord frågar appen om nästa port eller avslut. Enheten bär portens namn som egen uppgift (`port`) i fältunderlaget, och protokoll och listor skriver numret med porten framför ("54-1101"). En port kan också anges i fält; vid återföringen föreslås den som nytt trapphus. Återföringen söker porten bland de trapphus besiktningen frös, så att ett namnbyte efteråt inte bryter kopplingen; en enhet vars trapphus tagits bort ur registret förs inte över. Utan trapphus och portar är fältappen oförändrad. Ett ventilationssystem per port registreras som eget system i byggnaden. Våning är inte en egen uppgift. Trapphus är enligt ADR-012 en neutral strukturtyp som kärnan ska äga; det ligger i OVK:s strukturregister tills registret flyttas till byggnadsgrafen (ADR-012 punkt 8). Kärnans typ heter `stairwell`; adaptern i ADR-012:s migreringssteg 5 ska föra över trapphusets namn och adress dit.
6. **Koppling användare till besiktningsman**, så att utfärdande kan begränsas till uppdragets besiktningsman.
7. **Tilldelning.** Tilldelningsposter med historik. Först hela uppdraget till en besiktningsman, senare delar.
8. **Revisionskontroll på besiktningsposten.** Införd: `GET` och `PUT …/inspections/{id}` svarar med postens revision i `X-OVK-Record-Revision`. En sparning av en befintlig post ska bära den i `X-OVK-Base-Revision`; annars svarar rutten 428 `OVK_RECORD_REVISION_REQUIRED`, och 409 `OVK_RECORD_REVISION_CONFLICT` när posten har ändrats sedan dess. En ny post behöver ingen revision, och en upprepad sparning med oförändrat innehåll släpps igenom.
9. **Fältdata till kontoret.** Läsning av framdrift, tillträde, återbesök och avslutat fältarbete ur ögonblicksbilden.
10. **Komplettering.** Granskarens begäran, kopplad till en lägenhet, ett rum eller en anmärkning, synlig i fältappen.
11. **Bilagor.** Åtgärdslista (D), aggregatprotokoll (E) och fotobilaga (F) enligt [mallarna](../ovk-protokollmallar.md) och roadmapens avsnitt 6–7.
12. **Underskrift.** Ritad namnteckning, ort och datum, låst med dokumentrevisionen.
13. **Leveransregistrering.** Mottagare, tid och vad som skickades.
14. **Revisionsspår** för planering, tilldelning, fastighetsändringar och leverans.
15. **Synk per del** för delade uppdrag (ADR-013 punkt 4). Specificeras och byggs efter solopiloten.

## Utanför Desktop 1.0

- Kundisolering mellan organisationer: roadmapens R8. Plattformen körs för en organisation tills dess.
- PostgreSQL för OVK-data: efter 1.0 enligt ADR-012.
- Automatisk utsändning via e-post eller kommunintegration.
- CAD Light och ritningsnavigering.

## Leveransordning

| Steg | Leverans | Acceptans |
|---|---|---|
| D1 | Inventering | Genomförd 2026-11-21 |
| D2 | Det här dokumentet och ADR-013 | Godkänt av product owner |
| D3 | Skal, navigation och översikt med arbetskö (kontrakt 1–2) | Verkliga uppdrag med härledd status; alla befintliga sidor nås från skalet; inga interna ID:n i normalflödet |
| D4 | Kunder och fastigheter (kontrakt 3–5) | Ny besiktning på befintlig fastighet utan att lägga upp den igen; inga dubbletter |
| D5 | Planering och tilldelning för en besiktningsman (kontrakt 6–8) | Uppdrag skapas, planeras och öppnas i fältappen med samma identitet; samtidig ändring avvisas |
| D6 | Kontoret läser fältdatat (kontrakt 9) | Synkad framdrift, tillträde och avslut syns utan omladdning av annat än sidan |
| D7 | Granskningsarbetsplats (kontrakt 10) | Foto öppnas från bristen; saknade uppgifter listas; komplettering når fältappen |
| D8 | Bilagor, underskrift och leverans (kontrakt 11–14) | Paket mot referensmall; ofullständigt underlag kan inte utfärdas; leverans registrerad |
| D9 | Tester genom hela kedjan och pilot | Verkligt uppdrag från start till leverans utan dubbelregistrering |
| D10 | Delade uppdrag (kontrakt 15) | Två besiktningsmän, ett protokoll, ingen överskrivning |

Varje steg levereras i små PR:ar med acceptanskriterier och tester. Fältappen ändras bara när ett kontrakt kräver det.

## Protokollutkast som ersätts

Ett nytt protokollutkast från fältdata ersätter besiktningens post. Har posten ändrats sedan den senast byggdes (granskningsbeslut, täckning, inmatade uppgifter) svarar `POST …/protokoll-utkast` 409 `OVK_DRAFT_REPLACE_CONFIRMATION_REQUIRED` tills begäran bär `confirm_replace: true`. Posten sparas då undan först, under `projects/{projekt}/ovk-utkast-sparade/{besiktning}/`, och går att ta tillbaka med `POST …/protokoll-utkast/sparade/{id}/aterstall`. Återställningen sparar på samma sätt undan det den ersätter och behåller besiktningens nuvarande planering. Återställningen behåller också besiktningens nuvarande objekt och system. De tjugo senaste kopiorna per besiktning behålls, även efter utfärdande; de innehåller hela posten och följer projektets säkerhetskopiering. Ett orört, byggt utkast och en nyplanerad post ersätts utan fråga.

En återställd kopia som byggdes från äldre fältunderlag stämmer inte med protokollkällan. Den går att läsa, men ett nytt utkast måste byggas innan intyg kan utfärdas; svaret anger det i `protokollkalla_aktuell`. Rutterna för sparade utkast löser projektet genom omfångsfunktionen (ADR-013 punkt 3). En öppen besiktningssida kan inte längre skriva över ett nybyggt eller återställt utkast (kontrakt 8).
