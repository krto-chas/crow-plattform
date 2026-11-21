# OVK Desktop – backend-gap och första implementationspass

**Status:** statisk kodinventering / plan, inte end-to-end-verifierad  
**Syfte:** bygg desktop mot befintliga API:er, identifiera saknade kontrakt och skydda Core.

## Inventering och gap

| Del | Befintlig källa | Status och konkret gap |
| --- | --- | --- |
| Dashboard | `modules/crow-ovk-module/src/crow_ovk_module/assets/dashboard.html`, `ovk_dashboard_surface.py` | Enkel OVK-sida finns; behöver sammanhållen desktop-arbetsplats med verklig arbetskö |
| Uppdrag och status | `ovk_workflow_surface.py`, `assets/workflow.html`, `assets/workflow.js` | Arbetsflödes-API finns; kartlägg faktiska statusövergångar, tilldelning och samtidighet innan nya API:er |
| Fastighet och struktur | `ovk_fastighet_surface.py` | Projektbundna register; kundövergripande sökning/återanvändning kräver verifierad tenantbehörighet |
| Fält och offline | `ovk_field_surface.py`, `ovk_field_media.py`, `assets/field.js` | Relativt långt utvecklat; fältets funktion och synk måste testas på verklig enhet |
| Granskning | `ovk_reporting_surface.py`, `ovk_workflow_surface.py` | Verifiera täckning, revisionsstatus, godkännande och begäran om komplettering |
| Protokoll | `ovk_protokoll_surface.py` | Produktplanen dokumenterar fallback/syntetiskt system; blockera slutligt dokument utan verifierad systemstruktur |
| Intyg/export | `ovk_intyg_surface.py`, `ovk_export_surface.py` | Kod finns men faktisk dokumentkedja och fotobilagor är ännu inte användartestade |
| Bevakning/ombesiktning | `ovk_bevakning_surface.py`, `ovk_reinspection_surface.py` | Kod finns; testa koppling till historik och öppna brister |
| Modulmontering | `plugin.py`, `src/crow_workbench/shell.py` | OVK-routrar monteras som plugin; Core får inte importera OVK-domänkod |
| Identitet/behörighet | `src/crow_entitlements/`, ADR-011 | Session och entitlements finns; resurs- och tenantkontroll på varje OVK-endpoint måste inventeras/testas |
| Gemensam fastighet | `src/crow_building_graph/`, ADR-012 | Målbild ej fullt integrerad; migrera stegvis, ingen ny parallell modell |

**Viktigt:** Befintlig kod eller testfil är inte ett bevis på att funktionen fungerar i produktion. Alla statusar ska uppdateras mot aktuell revision, CI och manuell pilot.

## Desktop Pass 1 – Översikt, uppdragsmodell och planering

### A. Kartlägg innan kod
1. Lista samtliga OVK-dashboard-, workflow-, fastighets- och field-launch-routes med metoder, payloads, autentisering, tenantkontroll och felkoder.
2. Rita entitets-/ID-flöde för kund, projekt, fastighet, byggnad, system, uppdrag och besiktning.
3. Identifiera befintliga statuser, planeringsfält, tilldelningsfält och synk-/täckningsvärden; inför inte parallella statusmodeller.
4. Koppla varje desktopvy till befintligt API eller dokumenterat backend-gap.
5. Skriv negativa tester för obehörig kund, resurs, roll, dubbelregistrering och samtidig ändring.

### B. Implementera liten första vertikal skiva
- OVK-specifik desktopöversikt med befintliga CROW-designkomponenter.
- Verklig lista över behöriga uppdrag; sök/filter, tydliga statusar, tom-/fel-/laddlägen.
- Primärhandling **Ny OVK**, stegvis uppstart med återanvändning av befintlig fastighet.
- Öppna rätt uppdrag i befintlig workflow-/fältarbetsyta utan att skapa kopia.
- Visa nästa åtgärd, ansvarig och synkstatus endast där backend kan leverera faktiska värden.
- Planering och flerpersonstilldelning specificeras med kontrakt och testfall innan utbyggnad.

### C. Acceptanskriterier
- Tom organisation, ett uppdrag, flera uppdrag och flera behöriga användare visas korrekt.
- Två kunder med liknande fastighetsbeteckning blandas aldrig.
- Ingen manuell inmatning av interna ID:n för normalt flöde.
- Fältstart öppnar samma `inspection_id` och `project_id`.
- Obehörig användare kan inte läsa eller ändra annan kunds uppdrag.
- Dubbelklick eller upprepade API-anrop skapar inte dubbletter.
- Core startar fortfarande utan moduler; OVK kan aktiveras/avaktiveras.
- Ingen regression i befintliga fält-/offline-/mediatester.
- PR visar faktisk CI-status och manuell testplan; ingen merge utan godkännande.

**Beslut 2026-11-21:** kundisolering mellan organisationer tas enligt roadmapens R8 och ingår inte i Pass 1. Kriterierna ovan om annan kunds uppdrag och två kunder med liknande fastighetsbeteckning prövas då. Till dess körs plattformen för en organisation, och nya desktoprutter hämtar sina projekt genom en gemensam omfångsfunktion (ADR-013).

## Backbone-arbete – bara där det behövs
1. Behåll generiska identitets-, tenant- och auktorisationskontrakt i Core, OVK-roller i OVK.
2. Inför inte nya centrala lagrings- eller dokumenttjänster förrän en konkret OVK-konsument kräver det.
3. Utvärdera versionerad `ModuleContext` enligt ADR-012 före ändring av `routers(data_root)`; bakåtkompatibilitet krävs.
4. Revidera evidence/audit och serverbehörigheter med tester; kalla inte filbaserad JSONL manipulationssäker utan bevis.
5. Uppdatera kodankrad capability-/gapmatris efter varje PR.

## Nästa pass efter Pass 1
Pass 2: fastighetsstruktur och tilldelning. Pass 3: synk-/granskningsarbetsplats. Pass 4: protokoll och bilagor. Pass 5: fullständig pilot och releaseacceptans. Anpassa numrering till befintliga passdokument för att undvika kollision.
