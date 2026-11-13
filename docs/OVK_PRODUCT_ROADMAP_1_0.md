# CROW OVK — Produktplan och roadmap till 1.0

**Beslutad produktinriktning:** 2026-11-13  
**Status:** Produktplan för granskning; inga implementerings- eller releaseanspråk.  
**Teknisk baslinje:** main efter PR #152, commit `80af667a3f9ad29c0184e552970bb99443c46e82` (Pass 110b).  
**Ägare:** CROW OVK, första kommersiella produkten på CROW Plattform.

## 1. Produktbeslut

CROW OVK ska bli den första färdiga, intäktsgenererande produkten på plattformen. Målet är en verklig besiktning från kunduppdrag till levererat protokoll, intyg, mätbilagor och fotografisk evidensbilaga utan parallell manuell protokollproduktion.

Frys nya generella plattformsinitiativ under denna releaseperiod. Backbone, Building Graph, Document Intelligence och andra moduler används där de redan hjälper OVK. Ny generell funktion får endast motiveras av ett konkret OVK-behov eller nödvändig säkerhet, dataintegritet eller driftsstabilitet. Ingen ny CROW-produkt innan OVK 1.0 är användbar och kan skapa intäkter.

Principer:

- Fältarbete först: protokollet är utdata från besiktningen, inte ett separat formulär som måste matas in igen.
- Samma besiktning, samma serveridentitet och samma evidens i mobil- och skrivbordsytan. Ingen parallell datamodell eller dubbla manuella registreringar.
- Offline-first i fält, servern som långsiktig sanningskälla; synk och finalisering är olika operationer.
- Besiktningsmannen äger bedömningen. OBSERVED/STATED/INFERRED, provenance, versionshistorik och review bevaras. Inga okända fakta får gissas.
- Korrekt dokumentation, snabbhet och verifierbarhet framför fler moduler. Produktgrindar mäter faktiskt arbetsflöde, inte antal tester eller commits.
- OVK-modulen äger OVK-domänlogik; håll befintliga Backbone-kontrakt och modulgränser intakta.

## 2. Marknadsreferenser och positionering

| Referens | Lärdom | Prioritering i CROW |
|---|---|---|
| [OVK-Plan](https://ovkplan.se/) | Komplett OVK-administration, systemanpassade kontroller, import, protokoll, intyg, leverans och bevakning | Matcha kärnflödet i 1.0; gör onboarding och återkommande uppdrag enkla |
| [Yta — OVK-flöde](https://www.yta.app/dokumentation/kontroller/sa-har-genomfor-du-en-ovk-i-yta/) | Fastighet, byggnad, rum och installationer som sammanhängande modell; planritning som alternativ navigering | Återanvänd befintlig objektstruktur; full ritningsnavigation efter 1.0 |
| [Approvent — branschartikel 2021](https://pvmagasinet.se/bransch/ny-mobilapp-for-ovk/) | Mobil arbetsgång och minimalt efterarbete | Snabb rondering och färdig leverans på surfplatta |

Marknadsbilden baseras på publicerad information, inte praktiska konkurrenttester. Inga påståenden om att konkurrenter saknar fotofunktioner utan ny verifiering. CROW positioneras genom kombinationen av fotografisk evidens, automatisk bildbilaga, spårbar verifiering av åtgärder och återanvändbar teknisk historik.

## 3. Användarytor och målbild

### Desktop — OVK:s egen arbetsplats

Skrivbordsvarianten är i första hand en desktop-anpassad produktvy på befintlig webbplattform; eventuell paketerad/native klient är ett separat beslut efter behovsvalidering. Användaren ska inte behöva förstå Workbench eller Backbone för att utföra OVK.

Startsidan:

- Permanent vänsternavigation: Översikt, Uppdrag, Fastigheter, Dokument/Import, Bevakning, Inställningar. Ombesiktningar och åtgärder nås även kontextuellt.
- Tydlig primärknapp **Ny OVK**; guidat flöde från befintlig/ny kund och fastighet till byggnad, system, uppdragstyp, kontrollant och planering.
- Översiktskort med verkliga data: planerade, pågående, att granska, öppna åtgärder. Tomlägen, laddning och felstatus.
- Aktuella uppdrag som sökbar och filtrerbar lista/tabell: fastighet, adress, uppdragstyp, system, kontrollant, datum, status, täckning och nästa åtgärd. Färg + text, inte enbart färg.
- Höger detaljpanel eller full detaljvy: uppdragsstatus, täckning per byggnad/system, synkstatus, dokument, öppna brister, tidigare OVK och snabbknapp till rätt nästa steg.
- Bevakning: nästa OVK, ombesiktning och åtgärdsfrister. Påminnelseöversikt först; automatisk utsändning separat.
- Fastighetsvy: fastighet → byggnad → plan/trapphus → rum/lägenhet/lokal → system/aggregat/don, med relevant historik. Visuell ritningsnavigering får inte blockera användning.
- Anpassad granskningsyta med dokumentförhandsvisning, navigerbara brister, bilder, mätbilagor och redigerbara granskningsfält. Ingen manuell inmatning av interna ID:n.

### Field — telefon och surfplatta

- Välj/öppna befintligt uppdrag via lista eller länk; visa fastighet, byggnad, besiktningsman och synkstatus.
- Bostäder: trapphus → lägenhet → rum → don; behåll Pass 101:s snabbknappar UA, anmärkning, BOM, nyckellogg och nästa ej behandlade enhet.
- Kommersiella lokaler: plan/zon → rum → don; rumsdrivet flöde, både till- och frånluft, flera don per rum, flera system i samma byggnad.
- Teknikutrymmen: aggregat, tak-/vindfläkt, märkskylt, systemanpassade checklistor och mät-/driftdata.
- Stora touchytor, numeriskt tangentbord, svensk decimalnotation, förifyllnad av projekterade värden och tidigare historik tydligt märkt som historisk. Ingen automatisk kopiering som ny observation.
- Fotografera från anmärkningen, bind automatiskt till rätt plats och brist; visa förhandsvisning och synkstatus. Flera bilder per brist.
- Offline: visa lokalt sparat, väntar på synk, verifierat synkat, konflikt eller fel. Arbeta vidare utan nät; bevara data vid utgången session och återuppta efter login.
- Tydlig avslutningskontroll, granskning, signering och export även på surfplatta; inga fält får kräva desktop utan saklig anledning.
- Mål för UX: UA-rondering utan mätning under 30 sekunder per normal lägenhet efter förberedelse; full mätning benchmarkas separat. Tid mäts i pilot, inte antas.

## 4. Kanoniskt arbetsflöde

Kund/fastighet → byggnad/system → planerat uppdrag → fältförberedelse → rondering och mätning → verifierad synk → protokollutkast → review och explicit systemtäckning → färdigställande/signering → PDF-paket → leverans → historik/bevakning → eventuell ombesiktning.

Föreslagna visningsstatusar: Planerad, Pågående, Att granska, Leveransklar, Levererad, Åtgärder öppna, Ombesiktning. Mappa mot befintliga workflow-tillstånd; inför inte ett konkurrerande statuslager. Besiktningsresultat (G/G med anmärkning/EG), täckning, leveransstatus och synkstatus är separata begrepp.

## 5. Teknisk baslinje och konkreta luckor

Befintliga delar ska återanvändas, inte byggas om: domänkärna och import (64–67), fältdomän (69–70), offline och fotografisk media (76–78), historik/restore (79), historisk PDF/XLSX-import (80/84), tid/pris (57/81/82), intyg (97), ombesiktning (98), bevakning (99), PDF-export (100), rondering och teknikytor (101–103), IAM (104), modulgräns (106), protokollbrygga och synkfixar (110/110b).

Kodgranskning av baslinjen:

- `field_bridge.py`: mätningar lämnas utanför record i väntan på flödesprotokollet. Grupperade findings saknar explicit härledning tillbaka till samtliga originalfinding-ID:n och fotoreferenser; komplettera utan att förlora individuell beskrivning, plats och system.
- `ovk_protokoll_surface.py`: förenklade fallback-värden för systemtyp, byggnad och objektnamn samt ett syntetiskt system skapas. Byt till faktisk, verifierad fastighets-/systemstruktur; saknade uppgifter ska framgå och blockera färdigställande där nödvändigt.
- Samma route hämtar snapshot med inspection-ID och separat projektparameter. Verifiera server-side projekt-/tenant-/besiktningsbindning, behörighet, säkra sökvägar och avvisa mismatch innan läsning eller sparande. Detta är ett konkret verifieringskrav, inte ett påstående om exploaterad sårbarhet.
- Bryggan kan skapa PASS-checkpoint när kontrollpunkter saknas och föreslå BESIKTIGAD för teknikutrymmen. Ingen automatisk UA/godkänd/täckning utan explicit kontrollantbekräftelse och faktisk täckning; utkast med väntande mätningar ska inte nekas synk men får inte bli slutprotokoll.
- Säkerställ semantik för klass 0/1/2, åtgärdskrav och slutsats genom hela kedjan; klass 1 ska inte oavsiktligt bli EG bara för att en rekommenderad åtgärd finns.
- Granska återskapande av utkast så att ny synk inte skriver över godkänd review, ändrade anteckningar eller färdigställda dokument. Använd revision, idempotens och konflikt/ny version.
- Pass 100 har PDF och HMAC-signerade nedladdningsvägar. Kontrollera att signeringsoperationen kräver rätt projektbehörighet. HMAC-länk är inte kontrollantens underskrift.
- Pass 77 har verifierad bildtransport; integrera den i granskning, slutpaket och återbesiktning. En verifierad filhash styrker bytesintegritet, inte att plats eller bedömning är sann.

## 6. Obligatorisk fotobilaga — CROW:s evidensbaserade leverans

Fotografering är ett förstaklasskrav i 1.0, inte ett senare tillval.

Varje foto knyts till ursprunglig observation/finding, besiktning och verifierad plats: fastighet, byggnad, trapphus, lägenhet/lokal, rum och system eller teknikutrymme/aggregat när tillämpligt. Spara originalets SHA-256, fångsttid, kontrollant, bild-ID, kort teknisk beskrivning och eventuell position/klass från den granskade anmärkningen. Märkskyltar och övrig dokumentation skiljs från felbilder.

- Automatisk fotobilaga, föreslagen beteckning **F – Fotodokumentation**, med huvuduppgifter, sidnumrering, stabila fotonummer (F-001 osv. inom låst dokumentrevision), bilder i läsbar storlek och kort beskrivning per bild.
- Gruppera per anmärkning/position, visa exakt plats och system. Samma brist i många lägenheter kan grupperas i huvudprotokollet men varje foto behåller sin ursprungliga plats och finding-ID.
- Huvudprotokollets anmärkning refererar till rätt foton; digitala länkar där exportformatet stödjer det. Ingen referens till saknat/utelämnat foto.
- Alla relevanta och valda bilder medföljer automatiskt. Kontrollanten kan inkludera/utesluta och maskera privata detaljer; ingen tyst bortfiltrering av utvalda foton. Original skyddas, exporterad kopia kan förminskas eller maskeras. Ovidkommande privata tillhörigheter undviks redan vid fotografering.
- Exportmanifest binder dokumentrevision och inkluderade evidens-ID:n/hashar. Rapportera saknad eller skadad media; blockera slutpaket om inkluderad evidens inte kan verifieras. Ingen tyst förlust.
- Testa flera bilder per finding, samma rum/lägenhetsnummer i olika byggnader/trapphus, samma feltyp i flera system, olika bildorienteringar, stora bilagor, exkludering, maskering, saknad media och reproducerbar numrering.
- Före/efter vid ombesiktning: originalobservation oförändrad; ny verifiering med nytt foto, datum och kontrollant. Ingen sammanblandning med fastighetsägarens uppgift om utförd åtgärd.

## 7. Komplett protokoll och leverans

Kanonisk fältinventering: [OVK-protokollmallar](ovk-protokollmallar.md). Bevara etablerade beteckningar D (åtgärder), E (aggregat), L (flöde/drift/effekt) och föreslå F för foto; lägg inte om bilagenumrering utan kontroll mot referensmall.

Slutpaket per byggnad/besiktning efter granskningsbeslut:

- Huvudprotokoll: fastighet, byggnad, ägare, kontakt, kontrollant/certifikat, system, uppdragstyp, datum, resultat, täckning, anmärkningar och bilagereferenser.
- D: åtgärdslista med platser, klass, rekommendation och fotoreferenser; kostnad endast när uppgiven/beräknad och tydligt märkt.
- E: aggregatprotokoll med relevanta tekniska data, mätning, drift, filter, motor/effekt och explicit täckning.
- L: luftflödesprotokoll och drift/effektuppgifter; projekterat/uppmätt, enhet, metod, avvikelse, totalsummor med definierad omfattning, ej mätbar med orsak.
- F: fotografisk evidensbilaga enligt §6.
- OVK-intyg/anslag med korrekta uppgifter och frist där tillämpligt; kontrollantgranskning av rättslig hantering.
- Kontrollantens underskrift/attest, datum, ort och låst slutrevision. Skilj ritad namnteckning/attest från kryptografisk signatur och eventuell kvalificerad e-signering.
- Export som separata PDF:er och komplett paket (samlad PDF eller ZIP enligt verifierat behov); tydliga filnamn och manifest. Förhandsgranskning före slutleverans.
- Leverans till ägare och byggnadsnämnd enligt gällande krav; i 1.0 räcker fungerande export, registrerad mottagare och manuell dokumenterad sändning. Automatisk e-post/kommunintegration är P1 och får inte försena pilot, men faktisk leverans måste fungera.

Normkontroll: jämför före pilot mot gällande Boverket-regler och verkliga referensprotokoll; verifiera särskilt energihushållning vid återkommande OVK, första/återkommande besiktning, intervall, systemtyp, intyg och täckningsredovisning. Ej tillämpligt, ej kontrollerat och uppgift saknas är olika tillstånd. Ingen generell schablon som skapar godkänt utan underlag.

## 8. Releaseplan — ordnade arbetsblock

Arbetsblocken är OVK-specifika (OVK-R1–R8), inte reserverade globala Pass-nummer. Pass 111 har redan andra förekomster i grenarna; stäm av aktuell passnumrering innan kod-PR. Varje block kan delas i små PR:ar med verifierbara acceptanskriterier.

| Block | Prioritet | Leverans | Exit gate |
|---|---|---|---|
| OVK-R1 | P0 | Produktöversikt, uppdragsval och fastighetskoppling | Skapa/öppna verkligt uppdrag utan ID-inmatning; korrekt systemstruktur; gå mellan Desktop och Field |
| OVK-R2 | P0 | Fältkomplettering och täckning | Bostad + kommersiell lokal + aggregat; alla nödvändiga data kan registreras; UA/BOM/ej mätbar hanteras uttryckligt |
| OVK-R3 | P0 | Offline, media, synk och revisionsgrind | Data och foto överlever offline/omstart/session expiry; idempotens, konflikt, projektbindning, återställning verifierade |
| OVK-R4 | P0 | Protokollbrygga 2.0 och review | Faktiska system, mätvärden, anmärkningar, fotoreferenser, energi och täckning kopplas; ofullständiga utkast får inte finaliseras |
| OVK-R5 | P0 | PDF-paket med D/E/L/F, intyg och attest | Korrekt, läsbar och komplett export mot referensmall; foto per brist; dokumentrevision låst; inga handskrivna kompletteringar |
| OVK-R6 | P0 | Pilot och säkerhets-/driftacceptans | Verklig bostads- och lokalbesiktning, kundredo dokument, backup/restore, korrigeringar och releasebevis |
| OVK-R7 | P1 | Kommersiellt arbetsflöde | Återkommande OVK, importprecision, före/efter-ombesiktning, bevakning, leveranslogg, företagsprofil och tidsuppföljning förbättrade |
| OVK-R8 | P1 före extern SaaS | Kundonboarding och flerföretagsdrift | Tenant-isolation, roller, MFA/identitet, loggning, licenser, support och avtal verifierade |

R3:s grundläggande integritet får inte skjutas upp om R1/R2 annars riskerar verklig data. R4/R5 utgör kärnan i den tidigare föreslagna end-to-end-slutförandet. Visa gärna UI tidigt, men inga mockdata i verkliga produktkort. P0-block kan överlappa endast om beroenden är explicita.

Milstolpar:
- **0.9 Fältklar:** R1–R3 verifierade på verklig enhet, inkl. fullständig datainsamling och offline.
- **1.0 Produktionsklar för egen verksamhet:** R1–R6 verifierade; hela leveransen kan genomföras, granskas och skickas. Grundläggande historik/ombesiktning/bevakning i befintlig kod integreras där nödvändigt för pilot.
- **1.1 Kommersiell flerföretagsrelease:** R7–R8 samt extern kundacceptans. Ingen publik flerorganisationsdrift före godkända säkerhetsgrindar.
- **2.0:** CAD Light, schakt-/kanaltopologi, system- och styrscheman samt driftkort. Se [OVK 2.0 vision](OVK_PRODUCT_VISION_2_0.md). Ingen av dessa funktioner blockerar 1.0.
- **Senare:** avancerad historik-/avvikelseanalys, Vent-kalkyl/åtgärdsoffert, energimotor, förvaltarportal, injustering.

## 9. Pilot, verifiering och definition of done

Välj två verkliga uppdrag (flerbostadshus och kommersiell fastighet, exempelvis hotell/kontor) med godkänd hantering av kunddata. Använd avpersonifierade fixtures i Git; inga riktiga bostadsbilder eller kunddokument i publikt repo.

Testmatris: flera byggnader/system, UA, klass 0/1/2, BOM, ej mätbar, ofullständig mätning, saknade projekterade värden, teknikrum, foto/flera foton, offline på iPad/iPhone, nätbortfall under bildsynk, omstart, utgången session, dubbel synk, konkurrerande ändring, fel projekt-ID, fel behörighet, exportlänk, restore, G/EG och ombesiktning.

- Mät tid från uppdrag till färdig leverans, antal manuella kompletteringar, synkfel, förlorade dataposter och behov av parallella verktyg. Baslinje från nuvarande metod; resultat dokumenteras efter pilot.
- Fältdata, mätvärden och originalbilder ska stämma mot slutpaket. Protokoll och intyg granskas av behörig kontrollant mot verkliga mallar.
- Alla P0-checkpunkter måste ha bevis: test, granskning eller faktiskt arbetsprov. CI: Ruff, mypy, pytest, architecture review, distribution build samt riktade API/browser- och verkliga enhetstester. Kodmerge är inte driftacceptans.
- Återställning på separat miljö, åtkomstkontroll och begränsad exponering, säker session och export, säker hantering av bostadsbilder, backup och revisionslogg är produktionsgrindar även för egen verksamhet.
- Inga blockerande P0-fel, inga tysta dataförluster, inga obligatoriska manuella dubbelregistreringar. Release-SHA, testmiljö, kända begränsningar och ansvarig acceptans dokumenteras.

## 10. Affär och fortsatt styrning

Första användaren är den egna ventilationsverksamheten. Verifiera verklig tidsbesparing före extern prissättning. Konkurrenternas priser är marknadsreferens; tidigare idéer om 249 kr/mån solo och 599 kr/mån företag är hypoteser, inte beslutad prislista. Ingen licensförsäljning före relevant produkt- och säkerhetsacceptans.

Vid varje utvecklingspass: välj nästa blockerare i roadmapen, identifiera återanvänd befintlig funktion, specificera mätbart acceptanskriterium, genomför test, granska PR och verifiera driftsatt resultat. Uppdatera denna roadmap med evidens och blockerare, inte med obestyrkt procentsats.

### Nästa konkreta arbete

Starta OVK-R1 med inventering av befintlig dashboard, uppdrags-/fastighetsmodell och field launch. Skapa en desktop-anpassad OVK-översikt som läser verkliga uppdrag och leder till rätt befintlig arbetsyta. Samtidigt specificeras kanonisk koppling fastighet–byggnad–system–inspection; inga nya dubbla datalager. Lägg därefter in de konkreta bryggluckorna i R4 och fotobilagan i R5 som obligatoriska, ej parkerade krav.

## Referenser i repot

- [Fältinventering och mallar](ovk-protokollmallar.md)
- [Pass 101 – rondering](10_Passes/PASS_101_FALTFLODE_RONDERING.md)
- [Pass 102 – teknikrum](10_Passes/PASS_102_ALLMANNA_DELAR.md)
- [Pass 77 – media](10_Passes/PASS_77_OVK_MEDIA_TRANSPORT.md)
- [Pass 79 – historik](10_Passes/PASS_79_OVK_INSPECTION_HISTORY_SERVER_RESTORE.md)
- [Pass 84 – import](10_Passes/PASS_84_LEGACY_OVK_REVIEW_UI.md)
- [Pass 97 – intyg](10_Passes/PASS_97_OVK_INTYG.md)
- [Pass 98 – ombesiktning](10_Passes/PASS_98_OVK_OMBESIKTNING.md)
- [Pass 99 – bevakning](10_Passes/PASS_99_OVK_BESIKTNINGSBEVAKNING.md)
- [Pass 100 – PDF](10_Passes/PASS_100_OVK_PDF_EXPORT.md)
- [Pass 104 – IAM](10_Passes/PASS_104_PLATFORM_IAM_SESSION_FOUNDATION.md)
- [Protokollbrygga](../modules/crow-ovk-module/src/crow_ovk_workflow/field_bridge.py)
- [Protokoll-API](../modules/crow-ovk-module/src/crow_ovk_module/ovk_protokoll_surface.py)
- [Pass 110b, PR #152](https://github.com/krto-chas/crow-plattform/pull/152)


### Prioriteringsbeslut efter PR #174

Beständiga mätpunkter är införda i byggnadsregistret. Nästa R1-del är lägenhetsmallar med suffixregler (XX01, XX02 osv.), förhandsgranskning och unika instans-ID:n. Därefter prioriteras uppföljning av tidigare anmärkningar, komplett fältflöde, synk-/integritetsgrindar, protokollbrygga, dokumentpaket och verkliga piloter enligt R1–R6. CAD Light och driftkort är uttryckligen uppskjutna till 2.0. Ändra inte befintliga releasegrindar för att tidigarelägga dessa funktioner.
