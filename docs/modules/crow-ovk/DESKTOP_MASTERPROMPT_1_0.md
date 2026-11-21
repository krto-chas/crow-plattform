# Masterprompt – CROW OVK Desktop 1.0

**Status:** Implementationsunderlag, inte färdig implementation  
**Prioritet:** P0 – färdigställ första kommersiella modulen  
**Utgångspunkt:** befintlig kod och beslut i `krto-chas/crow-plattform`

## Uppdrag
Utveckla CROW OVK Desktop till en sammanhängande professionell arbetsplats från kund och fastighet till genomförd, granskad och levererad OVK. Börja alltid med kodinventering, API-kontrakt och tester; återanvänd befintliga funktioner och bygg inte parallella modeller.

## Bindande arkitektur
- CROW Core ska starta och fungera med **noll** verksamhetsmoduler.
- OVK är ett valfritt plugin. OVK-specifika roller, kontroller, uppdrag, regler, protokoll och dokumentmallar ligger i OVK, inte i Core.
- Core tillhandahåller generiska kontrakt för identitet, tenant-/resursbehörighet, modulregister, evidens, audit, dokument, synk och dataåtkomst där dessa faktiskt är implementerade. Utöka endast vid konkret behov och med godkänt kontrakt.
- Följ `docs/CONSTITUTION.md`, `docs/MODULE_CONTRACT.md`, `docs/90_Governance/CAF-002_Architecture_Principles.md`, `docs/OVK_PRODUCT_ROADMAP_1_0.md`, `docs/design/OVK_PROPERTY_FIRST.md`, ADR-011 och ADR-012.
- Samma fastighet, uppdrag, besiktning och evidens i desktop och fält. Ingen dubbelregistrering, tyst sammanslagning eller påhittade fakta.
- Servern är långsiktig sanningskälla; offlineutkast är versions- och synkhanterade; synk och finalisering är skilda operationer.

## Användare och roller
Stöd både ensam besiktningsman och större organisation med flera användare. En person kan ha flera OVK-roller, exempelvis administratör, arbetsledare, besiktningsman och protokollgranskare. Rollerna är **modulägda**, men behörighetsbeslut verkställs i backend mot tenant, resurs och handling. UI är inte en säkerhetsgräns.

## UX och användarytor
Desktop är initialt en responsiv, desktopanpassad webbyta på befintlig plattform; native-paketering kräver separat beslut. Luftig, skandinavisk design med befintliga CROW-tokens, tydlig vänsternavigation och tillgänglighet enligt WCAG 2.2 AA som mål.

Navigation: **Översikt, Uppdrag, Fastigheter, Dokument/Import, Bevakning, Inställningar**. Granskning, åtgärder och ombesiktningar nås också från relevant uppdrag. Primärhandling: **Ny OVK**.

Översikten visar endast verkliga uppdrag och verifierad status: planerade, pågående, att granska, öppna åtgärder, synkfel och nästa steg. Visa sökning, filtrering, fastighetsbeteckning, adress, ansvarig, system, datum, täckning och status. Hantera tomlägen, fel och laddning utan mockdata.

Fastighetsnavigering: kund → fastighet → byggnad → plan/trapphus → lägenhet/lokal/rum → system/aggregat/don. Tidigare besiktningar och brister visas som historiska referenser, aldrig som nya observationer.

## Arbetsflöde och arbetsledning
1. Välj/registrera kund och fastighet. Sök inom behörigt kundscope; samma fastighetsbeteckning kan förekomma i olika kommuner.
2. Skapa/återanvänd uppdrag och byggnads-/systemstruktur utan dubbletter; kontorsförberedelse är valfri.
3. Planera och tilldela hela uppdrag eller avgränsade delar (byggnad, trapphus, lägenhet/lokal) till flera kontrollanter.
4. Starta fältarbete med exakt samma server-ID och behöriga uppgifter.
5. Ta emot synkroniserade mätningar, bedömningar, anmärkningar och bilder; visa konflikter och ofullständig täckning.
6. Granska per system, byggnad och kontrollpunkt; begär komplettering och lås godkända revisioner.
7. Skapa protokoll, intyg, mätbilagor och fotobilagor automatiskt från verifierad data.
8. Utfärda, leverera, arkivera historik och skapa uppföljning/ombesiktning.

Samtidiga ändringar får inte tyst skriva över varandra. Ingen finalisering när obligatoriska uppgifter eller verifierad evidens saknas.

## Fältintegration
Bevara befintliga `field.html`, `field.js`, fält-API:er, offlineutkast, fotokopplingar och synk. Ingen omskrivning av fältappen utan verifierat behov. Testa sessionsutgång, omstart, dubbeltryck, konflikt, fel kund, nätavbrott och idempotens.

## Protokoll och dokument
Granskningen ska ha dokumentförhandsvisning, navigerbara anmärkningar, foton och mätbilagor. Inga syntetiska system, byggnadsnamn eller schablonvärden i slutligt dokument. Varje export ska vara spårbar till dokumentrevision och evidens-ID/hash. Felaktiga eller saknade bilagor ska synas och blockera slutleverans när de är obligatoriska.

## Genomförande och PR-regler
Dela arbetet i små PR:ar: (1) inventera desktop/API, (2) översikt och uppdrag, (3) fastighetsstruktur, (4) planering/tilldelning, (5) fältsynk och review, (6) protokoll och bilagor, (7) end-to-end-pilot. Varje steg har verkliga testfall, negativa tenant-/behörighetstester, regressionsskydd och explicit acceptans. Följ `AGENTS.md`, befintlig CI och modulkontrakt.

**Definition of Done:** Ett verkligt uppdrag kan skapas på kontoret, genomföras i fält, synkas, granskas, utfärdas och levereras med fullständigt protokoll och bilagor utan manuell dubbelregistrering. OVK 1.0 deklareras inte färdig innan pilot och releasegrindarna R1–R6 är verifierade.
