# Pass 99 — OVK-besiktningsbevakning

## Mål
Den återkommande intäktsmotorn: en bevakningslista per projekt över när kundernas
byggnader ska besiktigas igen — kommande frister, påminnelser, förseningar och
byggnader där ombesiktning krävs.

## Nytt paket: `crow_ovk_besiktningsbevakning`
Bevakningen är en **härledd vy utan eget lagrat tillstånd**. Listan byggs on-demand
ur intygsrepositoryt (pass 97) och ombesiktningsärendena (pass 98), så det kan aldrig
uppstå synkdrift mellan bevakningen och källorna — en enda sanning.

### Modeller
- `WatchStatus`: `ok` → `paminnelse` (inom fönstret, standard 180 dagar) →
  `forsenad` (passerad frist), samt `ombesiktning_kravs` (senaste intyget EJ GODKÄND)
  och `ingen_frist` (t.ex. småhus utan återkommande krav).
- `WatchItem`: byggnad, källa (`intyg`/`ombesiktning`), referens-ID, besiktnings-ID,
  frist, intervall, dagar kvar och **obligatorisk skriven basis** — intygspostens basis
  är intygets egen härledda frist-basis, så proveniensen (BFS 2011:16-härledningen)
  följer med oavbruten från pass 97 in i bevakningsvyn.
- `WatchList`: genereringsdatum, påminnelsefönster, sorterade poster samt räknare för
  förseningar/ombesiktningskrav och påminnelser.

### Härledningsregler
- **Senaste intyget per byggnad vinner**, deterministiskt valt på utfärdandedatum med
  intygs-ID som tie-break. GODKÄNT intyg ger fristpost; EJ GODKÄNT ger
  `ombesiktning_kravs`; saknad frist ger `ingen_frist` med basis som förklarar varför.
- **Öppna ombesiktningsärenden med åtgärdsfrist** bevakas som egna poster
  (källa `ombesiktning`). Stängda ärenden bevakas inte — deras godkända ombesiktning
  får ett eget intyg via pass 97 och tar därmed över byggnadens fristpost. Det är så
  pass 97 → 98 → 99-kedjan sluter sig.
- Sorteringen är deterministisk: förseningar först, sedan ombesiktningskrav,
  påminnelser, ok och sist poster utan frist; inom status på frist och byggnads-ID.

## Yta
`ovk_bevakning_surface.py` i `crow_ovk_module`:

- `GET /ovk/bevakning` — workbench-sida med räknare och färgkodade poster
- `GET /api/ovk/projects/{p}/bevakning?window_days=180&today=YYYY-MM-DD` — bygger
  listan live ur repositoryn; `today` är valfri (default dagens datum) och gör
  endpointen deterministisk för test och planering; 422 vid ogiltigt datum

Pluginen registrerar routern och exporten `ovk_bevakning`.

## Ägarskap och gate
Layoutmanifest 1.12: `crow_ovk_besiktningsbevakning` i `owned_packages`/
`migrated_packages`, `test_ovk_bevakning.py` i `owned_tests`; ägarskapsvakt,
`known-first-party` och modulens package-data uppdaterade.

Gate: `ruff format` → `ruff check` → `mypy --strict` → `pytest`. Tester täcker alla
fem statusar, fönstergränser, senaste-intyg-valet, ärendefrister (öppna bevakas,
stängda inte), sorteringsordning, basiskrav, payload samt ytans 200/422 och tomt
projekt.
