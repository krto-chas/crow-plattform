# CROW OVK Desktop 1.0 – arbetsflöde och saknade kontrakt

Status: produktkrav och genomförandeplan, inte implementeringsbevis.
Datum: 2026-11-21. Underlag: kodläsning av `main` @ `330f0d4`; inga tester eller webbläsare kördes för inventeringen.
Kompletterar [OVK-roadmapen](../OVK_PRODUCT_ROADMAP_1_0.md) och [property-first](OVK_PROPERTY_FIRST.md). Besluten finns i [ADR-013](../adr/ADR-013-ovk-desktop-workspace.md). Befintliga releasegrindar gäller.

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
| Pågående | ögonblicksbild finns, fältarbetet inte avslutat, posten inte klar att utfärda |
| Att granska | fältarbetet avslutat men posten inte klar att utfärda; eller posten klar att utfärda men fältarbetet inte markerat som avslutat |
| Leveransklar | posten protokollklar och protokollkällan svarar mot fältets ögonblicksbild; fältarbetet avslutat eller ingen fältdata; inget intyg |
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
5. **Trapphus och våning** i strukturregistret, så att delar kan tilldelas per trapphus.
6. **Koppling användare till besiktningsman**, så att utfärdande kan begränsas till uppdragets besiktningsman.
7. **Tilldelning.** Tilldelningsposter med historik. Först hela uppdraget till en besiktningsman, senare delar.
8. **Revisionskontroll på besiktningsposten.** `PUT …/inspections/{id}` saknar förväntad revision i dag; fältsynken har det.
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
