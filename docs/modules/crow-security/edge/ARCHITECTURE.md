# CROW Security – Edge, Asset Discovery & Topology

**Status:** föreslagen målarkitektur, ej implementerad  
**Version:** 0.1  
**Senast uppdaterad:** 2026-11-21  
**Berörd modul:** `crow.security` (föreslaget ID)  
**Beslutsfattare:** produktägaren  
**Syfte:** underlag för kommande masterprompt, ADR, implementation och acceptanstest

## 1. Mål och avgränsning
CROW Security ska stödja CROW:s roll som extern säkerhetspartner för små och medelstora organisationer. Första leveransen är en kontrollerad inventering av IT-tillgångar och deras relationer. Automatiska observationer ska kunna kompletteras med platsbesök och manuell verifiering. Resultatet ska bli ett beständigt tillgångsregister, en interaktiv nätverkskarta och spårbara förändringsförslag.

CROW identifierar, analyserar, prioriterar, rekommenderar och verifierar. Kunden äger sina riskbeslut och ansvarar genom sin egen IT-organisation/leverantör för förändringar, om inte separat avtal finns.

**Utanför första fasen:** autonom sårbarhetsexploatering, okontrollerad aktiv scanning, automatisk ändring av kundnät, full SOC/SIEM, nätverkssimulering och färdig kommersiell SaaS-drift.

## 2. Bindande arkitekturprinciper
1. **Domänneutral kärna.** CROW Platform ska starta och fungera utan CROW Security, Edge eller någon annan verksamhetsmodul.
2. **Fristående modul.** Säkerhetsdomänens modeller, regler, vyer och API:er placeras i en separat installerbar modul enligt publika SDK-kontrakt; inga OVK-beroenden.
3. **En identitet per tillgång.** Samma kanoniska asset-ID återanvänds i logisk, fysisk och framtida verksamhets-/beroendevy.
4. **Spårbar evidens.** Observationer, härledningar och manuella verifieringar skiljs åt och förses med källa, tid, metod och osäkerhet.
5. **Mänsklig kontroll.** Osäkra matchningar och betydande topologiförändringar ska granskas innan de fastställs som verifierade.
6. **Minsta privilegium.** Discovery sker bara inom dokumenterat, godkänt scope med hastighetsgränser och särskild hänsyn till OT/IoT/äldre utrustning.
7. **Strikt kundisolering.** Alla enheter, uppdrag, observationer och data är knutna till verifierad tenant och auktoriserad scope.
8. **Versionsstyrning och tester.** API, schema, agent och modulkontrakt versionssätts; nya funktioner kräver CI och verifierbara acceptanskriterier.

## 3. Föreslagen systemuppdelning
```text
Kundnät
  CROW Edge Agent / Collector
    - godkända discovery-jobb
    - lokal krypterad kö och återförsök
    - heartbeat, versions- och hälsostatus
           |
           | utgående TLS, mTLS, signerad/identifierad enhet
           v
CROW Edge Gateway (separat, begränsad tjänst)
    - registrering och återkallelse av enheter
    - bindning device -> tenant -> scope
    - autentisering, validering, replay-skydd
    - rate limiting, audit, idempotent ingestion
           |
           v
CROW Platform
    - gemensamma plattformskontrakt
    - modulregister, identity/authorization, audit
           |
           v
CROW Security (fristående verksamhetsmodul)
    - tillgångsregister och historik
    - logisk och fysisk topologi
    - discovery-observationer, review, riskkopplingar
    - API, grafiskt gränssnitt och rapporter
```

**Designrekommendation:** Kör Edge Gateway som separat tjänst, inte som oskyddad direktåtkomst till Workbench eller användarsessionernas API. En agent ska inte kunna välja eller byta tenant genom ett självrapporterat fält.

## 4. Inventering och discovery
- Inledande inventering av nät, subnät, VLAN, IP, MAC, enheter, system, tjänster, ägare och leverantörer.
- Discovery-källor kan vara scoped Nmap, ARP, DHCP/DNS, LLDP, SNMPv3, switchars MAC-tabeller och leverantörs-API:er, exempelvis UniFi.
- Passiv inventering eller API-inhämtning prioriteras där aktiv scanning kan innebära driftstörning.
- Scanuppdrag ska kräva uttryckligt kundgodkännande, tillåten IP-/nätomfattning, metoder, tidfönster och begränsningar.
- Varje fynd ska märkas `observed`, `inferred` eller `manually_verified`; inga inferenser får presenteras som säkra fakta.
- Matchning av flera observationer till samma tillgång ska vara deterministisk när evidensen räcker och annars leda till granskningskö.
- Nya enheter, ändrade IP-adresser, portar, VLAN, tjänster och relationer ska ge historik och förslag till förändringar, inte tyst skriva över verifierade uppgifter.

## 5. Gemensam datamodell – från första versionen
Minimala domänbegrepp:
- `Asset`: kanoniskt ID, typ, namn, status, ägare, tenant, livscykel.
- `NetworkInterface`: MAC, IP-observationer, VLAN-/subnätskoppling.
- `AssetRelation`: typad relation mellan tillgångar, evidens och giltighetstid.
- `Location`: site, byggnad, våning, rum, rack.
- `PhysicalConnection`: port, patchpanel, kabel/anslutning, verifieringsstatus.
- `Observation`: källa, metod, tidsstämpel, payload, kvalitet och confidence.
- `DiscoveryJob`: godkänt scope, initiator, tillåten metod, status, fel och logg.
- `ChangeProposal`: före/efter, evidens, granskare, beslut och revision.
- `EdgeDevice`: device-ID, tenant-bindning, certifikatstatus, policyversion, hälsa.

**Logisk vy:** router, brandvägg, switch, nät, subnät, VLAN, servrar, klienter, tjänster och relationer.  
**Fysisk vy:** site, byggnad, våning, rum, rack, fysisk enhet, portar, patchpanel och kablage.  
**Framtida beroendevy:** verksamhetsprocess -> applikation -> tjänst -> infrastruktur.

En tillgång som finns i flera vyer ska behålla samma ID. En vy får vara ofullständig utan att förstöra övriga vyer.

## 6. UX och interaktiv topologi
Gränssnittet ska vara rent, skandinaviskt och intuitivt. Nätverkskartan ska stödja zoom, panorering, filtrering, gruppering, sökning och detaljpanel. Klick på en nod ska visa dess evidens, historik, risker och möjliga relationer. Växling mellan logisk och fysisk vy ska behålla markerad tillgång där motsvarande fysisk placering finns. Layoutpositioner ska sparas per vy utan att påverka kanonisk data. Okända kopplingar ska visualiseras som okända, inte hittas på.

## 7. Säkerhetskrav för Edge
- Unik enhetsidentitet, säker onboarding och certifikatrotation/återkallelse.
- mTLS eller likvärdig stark ömsesidig autentisering; rekommendationen är mTLS.
- Backend härleder tenant och behörigt scope från serverlagrad enhetsregistrering, inte agentens uppgifter.
- Begränsade, signerade/versionerade uppdrag; allowlist, rate limiting och timeouts.
- Skydd mot replay, duplicerade batcher, överstora payloads och schemaförväxling.
- Krypterad kommunikation; skydd av lokala hemligheter och köad data.
- Felsäker drift: inga skanningar vid saknat godkännande, utgången policy eller oklar scope.
- Central spårbar loggning för registrering, policyändringar, uppdrag, resultat och spärrningar.
- En avaktiverad eller spärrad Edge-enhet ska inte kunna skicka nya accepterade fynd.
- Drift och livscykel: uppdateringspolicy, signering/verifiering av artefakter, rollback och återställning.

## 8. Faktisk repo-kontroll 2026-11-21
Granskat på `main` i `krto-chas/crow-plattform`:
- `src/crow_module_sdk/module_registry.py`: modulupptäckt via `crow.modules` entry points.
- `src/crow_workbench/shell.py`: modulers routrar monteras dynamiskt.
- `modules/crow-ovk-module/src/crow_ovk_module/plugin.py`: befintlig fristående plugin-implementation.
- `src/crow_entitlements/context.py`: kundkontext kan i miljöbaserat läge härledas från processmiljön; **får inte återanvändas som maskinidentitet för Edge**.
- `src/crow_entitlements/auth.py`: användarsessioner med signerad cookie; **inte ett Edge-autentiseringsprotokoll**.
- `src/crow_entitlements/api.py`: entitlement-kontroll med modul-/sökvägskatalog; Edge behöver explicit endpoint- och scope-authorization.
- `src/crow_entitlements/audit.py`: lokal JSONL-audit; Edge behöver bedömd hållbarhet, integritet och central logghantering.
- `.github/workflows/core-empty.yml`: testar att kärnan kan starta utan verksamhetsmoduler.
- `.github/workflows/ci.yml`: kvalitet, modultester, arkitekturgranskning och HTTPS-smoke.
- `README.md`: tenant-isolering, SSO och dataskydd anges som återstående verifiering inför extern drift.

**Bedömning:** återanvänd modularkitekturen men inför separat verifierad maskinidentitet och säker ingestion innan extern Edge-pilot. Detta är en statisk kod-/dokumentgranskning, inte ett penetrationstest eller produktionsgodkännande.

## 9. Föreslagen utvecklingsordning
1. **Kontrakt/ADR:** avgränsa Edge, kundbindning, API, dataägarskap, hotmodell, livscykel.
2. **Gateway-minimum:** onboarding, mTLS, spärrning, heartbeat, audit och idempotent ingestion.
3. **Security-modul:** plugin, tillgångsmodell, lagring, API, behörigheter och grundläggande lista.
4. **Collector minimum:** lokal agent, godkända jobb, kö, begränsad passiv/API-baserad discovery.
5. **Topologi:** logisk graf och manuellt verifierad fysisk placering; senare fysisk grafvy.
6. **Förändringar och risker:** diff, review, historik, risklänkar och rapportering.
7. **Pilot:** avgränsad intern testmiljö före kundinstallation; OT/IoT undantas tills särskild riskprövning gjorts.

## 10. Acceptanskriterier
- Kärnan startar med noll verksamhetsmoduler (befintlig core-empty CI fortsätter passera).
- CROW Security kan installeras, aktiveras och avaktiveras utan kodändring i kärnan.
- Edge utan giltig enhetsidentitet, giltigt certifikat eller aktiv registrering nekas.
- Edge kan inte läsa, skriva eller styra jobb för annan tenant.
- Scanning utanför godkänt scope nekas och loggas.
- Upprepade resultat skapar inte dubbla tillgångar eller dubbla historikhändelser.
- Samma asset-ID fungerar i logisk och fysisk modell; osäkra relationer markeras.
- Observation, inferens och manuell verifiering går att särskilja i UI och API.
- Större förändringar kräver review; historik kan återges.
- CI omfattar isolering, certifikatfel, replay, scope, schema, modulkonformitet och tomkörning.

## 11. För framtida masterprompt
En kommande masterprompt ska **först läsa faktiskt repo** och dessa dokument samt `AGENTS.md`, `docs/CONSTITUTION.md`, `docs/MODULE_CONTRACT.md`, relevanta ADR:er och `docs/engineering/`. Den ska:
1. skilja bindande krav, rekommendationer och senare faser,
2. återanvända befintliga publika kontrakt och undvika dubbelimplementation,
3. dela upp arbetet i små testbara PR:er,
4. kräva verifierad tenant-isolering, autentisering och CI innan kunddrift,
5. förbjuda automatisk merge/driftsättning utan produktägarbeslut,
6. redovisa varje ändrat filnamn, test, risk och återstående fråga.

## 12. Beslut och öppna frågor
**Fastlagd riktning:** fristående Security-modul; både logisk och fysisk modell från början; central asset-identitet; säker kundplacerad collector; evidens och mänsklig review; ingen domänlogik i kärnan.

**Rekommendationer att besluta senare:** separat Gateway-process, mTLS, databas, meddelandekö, hårdvaruval, exakta discovery-protokoll och UI-grafbibliotek.

**Ej verifierat:** faktisk driftssäkerhet, full tenant-isolering, produktionsredo audit, kompatibilitet med ännu ej skapad Edge-kod.
