# CROW OVK 1.0 – Design och property-first arbetsflöde

Status: produktkrav och genomförandeplan, inte implementeringsbevis.
Datum: 2026-11-15. Kompletterar [OVK-roadmapen](../OVK_PRODUCT_ROADMAP_1_0.md), särskilt R1–R3. Befintliga releasegrindar gäller.

## Produktvision

CROW OVK är ett luftigt, skandinaviskt och intuitivt professionellt arbetsverktyg. Kontoret förbereder; mobilen genomför. Förarbete är valfritt. Samma besiktning, identitet och data används i båda ytorna. Mobilens startsida gäller endast OVK, inte hela plattformens moduler.

## Designstandard

- Tydlig hierarki, generösa mellanrum, återhållsam färg, få samtidiga primärhandlingar. CROW-ögat som identitetsbärare; använd befintlig logotyp.
- Förslag till tokens (valideras visuellt): snow #F7F8FA, stone #E4E7EB, slate #64748B, nordic blue #527D9B, graphite #151B23. Inter med systemfont som fallback. Primärknappens kontrast måste verifieras; mörkare blå vid behov.
- Gemensamma tokens för ljus/mörk yta, typografi, avstånd, radier, fokus, status och komponenter. Inga separata datamodeller eller duplicerade vyer för teman.
- Minst 44 x 44 CSS-pixlar för centrala touchkontroller, tydliga etiketter, synligt tangentbordsfokus, WCAG 2.2 AA som mål. Status uttrycks med text, inte enbart färg. Ingen horisontell scroll i normalt mobilflöde.
- Visa laddning, tomläge, fel, offline och synkstatus med verklig data. Inga mockuppdrag i produktvyer. Använd svenska verksamhetsord; interna ID:n och projektadministration är inte primära fält.
- Desktop: överblick, planering, fastighetsstruktur och granskning. Mobil: nästa arbetsmoment, numerisk inmatning, stora tryckytor, få steg. Bevara befintlig rondering, bilder och lokala utkast.

## Mobil startsida

Visa förberedda uppdrag som användaren får öppna och pågående besiktningar med verklig status. Visa fastighetsbeteckning, adress, relevant datum och eventuell faktisk täckning. Visa inte tomma kortsektioner. Ny besiktning och Fortsätt besikta är alltid synliga. Fortsätt öppnar val av tillgängliga pågående uppdrag eller tydligt tomläge; ett lokalt utkast får inte försvinna vid nätbortfall. Förberedda uppdrag öppnar rätt befintlig besiktning, inte en ny kopia. Vid både förberedda och pågående uppdrag visas båda; pågående arbete prioriteras. Visa bara behöriga uppdrag och respektera tilldelning enligt befintlig behörighetsmodell.

## Ny besiktning

1. Ange fastighetsbeteckning. Sök bland behöriga fastigheter; normalisera beteckning och använd kommun för att skilja lika namn. Visa adress och tidigare besiktning när tillgängligt.
2. Vid träff: föreslå ny besiktning på samma fastighet. Användaren bekräftar rätt fastighet; vid flera träffar väljer användaren. Ingen automatisk sammanslagning.
3. Vid ingen träff: registrera minsta nödvändiga fastighetsuppgifter i samma flöde. Ett sökfel är inte ett tomt sökresultat.
4. Om projekt saknas skapas det i bakgrunden med fastighetsbeteckning som visningsnamn och separat unikt ID. Befintligt projekt kan väljas som avancerat alternativ. Servern validerar kund, projekt, fastighet och behörighet; upprepad begäran får inte skapa dubbletter.
5. Starta en ny besiktning med eget ID, utan krav på fullständig inventering. Komplettera byggnad, system och kontrollpunkter successivt. Okända fakta får inte ersättas med schabloner. Befintliga finaliseringsgrindar kvarstår.

## Återanvändning och historik

Återanvänd befintlig byggnadsstruktur, lägenheter, rum, system, don och projekterade värden där tillgängligt. Tidigare mätningar visas som daterad referens; tidigare anmärkningar visas vid aktivt val. Ny besiktning har nya mätningar, bedömningar, foton och signering. Gamla protokoll och evidens ändras aldrig. Följ ADR-012: kundägd fastighet och graf är målbild; befintligt OVK-register är källa under övergången enligt ADR:ns migrationsordning. Ingen ny parallell fastighetsmodell. Använd befintliga publika kontrakt och dokumentera eventuella luckor innan implementation. Ändra inte ägarskap eller migreringsordning utan godkänt ADR.

## Inventering av befintlig frontend (main, 2026-11-15)

- `modules/crow-ovk-module/src/crow_ovk_module/assets/dashboard.html`: befintlig OVK-översikt med Ny OVK-länk till /ovk/besiktning?new=1, uppdragslista, projektverktyg och egen inline-CSS. Återanvänd uppdragsdata; flytta projektverktyg ur primärt mobilflöde.
- `ovk_dashboard_surface.py`: serverar /ovk och importförhandsvisning; inte i sig en ny starttjänst.
- `assets/field.html`, `field.js`, `field-context.js`: befintlig fältapp. field-context.js använder project_id och inspection_id från URL, återställer utkast och skyddar kontext vid generering. Bevara detta.
- `ovk_fastighet_surface.py`: befintliga fastighets- och struktur-API:n är projektbundna. Kundövergripande sökning kräver verifierad behörighetsmodell och återanvändning av befintliga register; exponera inte en oskyddad global sökning.
- `src/crow_workbench/static/product.css`: befintliga crow-tokens och produktkomponenter. Utvärdera gemensam CSS via publik asset-yta; undvik att modul importerar privata kärnimplementationer.
- `assets/workflow.html`, `workflow.js`, `ovk_workflow_surface.py`: kartlägg planering och tillstånd före ändring. Mappa visningsstatus mot befintliga tillstånd, inte en ny parallell statusmodell.

Inventeringen är en källkodsorientering, inte ett genomfört browser- eller säkerhetstest.

## Leveransordning

| Del | Leverans | Acceptans |
| --- | --- | --- |
| R1a | Mobil startsida och designgrund | Verkliga förberedda/pågående uppdrag, tomläge, Ny/Fortsätt, befintliga länkar fungerar |
| R1b | Fastighetssökning och direktstart | Ny kund utan projekt når fältarbetsyta; befintlig fastighet föreslås och bekräftas; inga dubbletter |
| R1c | Återanvändning och kontorsförberedelse | Samma besiktnings-ID i desktop/mobil, struktur återanvänds, historik separerad |
| R2/R3 | Fältfortsättning och offline | Återuppta rätt plats, lokala utkast överlever omstart, synkstatus och konflikter tydliga |

R1a är första kod-PR. Före implementation: kartlägg exakta uppdrags-API:n, tillstånd, behörigheter och befintliga tester. Ingen ny backend om befintliga kontrakt räcker. Offline skapande av helt ny fastighet/projekt kräver separat verifierad synkstrategi; lova inte detta innan den finns. Befintlig offlinefunktion får inte försämras.

## Acceptans och överlämning

Testa tom kund, endast förberedda, endast pågående, båda, flera fastighetsträffar, tidigare besiktning, nätfel, dubbelklick, fel behörighet, annan kund, fel projekt/besiktnings-ID, återupptagning och oförändrad historik. Testa iPhone/Android och desktop med verkliga webbläsare, tangentbord, kontrast och 320–1440 px vyer. Bevara befintliga R1–R6-grindar och fotobilaga. Dokumentera faktiska resultat och skärmbilder med syntetiska data.

Codex implementerar första kodskivan; Claude Code granskar samma SHA i separat worktree enligt [HANDOFF](../engineering/HANDOFF.md). Verifier kör obligatoriska grindar; extra säkerhetsgranskning vid kundisolering och behörighetsändringar. Product owner godkänner design och merge. Ingen agent får påstå att annan modell eller tester körts utan evidens.
