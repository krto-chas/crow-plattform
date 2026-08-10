# Pass 100 — OVK PDF-export med signerade nedladdningsvägar

## Mål
Kommunerna vill ha PDF. Passet gör protokollet (pass 91-kedjan) och intyget (pass 97)
exporterbara som PDF — och stänger samtidigt en av de tre identifierade
attackytorna inför publik lansering: **oskyddade exportvägar**. Ingen PDF lämnar
plattformen utan giltig HMAC-signatur.

## Nytt paket: `crow_ovk_export`

### `signing.py`
- `sign_export_path(secret, path, expires_epoch)`: HMAC-SHA256 över den kanoniska
  sökvägen och utgångstiden (`{path}|{expires}`), samma algoritmfamilj som
  backbones `crow_module_conformance.trust`.
- `verify_export_signature(...)`: nekar utgångna länkar och verifierar med
  `hmac.compare_digest` (konstanttid). Manipulerad sökväg, manipulerad signatur,
  fel nyckel och passerad utgångstid ger alla `ExportSignatureError`.

### `pdf.py`
- `protocol_pdf(record)` och `intyg_pdf(intyg)` renderar A4-PDF:er med `fpdf2`
  (ren Python, nytt modulberoende `fpdf2>=2.8`). Svenska etiketter, systemtabeller,
  kontrollpunkter med status, anmärkningar med allvarsgrad och åtgärdskrav,
  resultatbanner samt — för intyget — den härledda fristen med sin skrivna basis
  markerad som härledd uppgift. Innehållet speglar HTML-renderarna: samma
  analyskedja, två presentationsformat.
- Testerna läser tillbaka PDF-texten med `pypdf` (redan ett beroende) och
  verifierar innehållet — inte bara att bytes producerades.

## Yta
`ovk_export_surface.py` i `crow_ovk_module`:

- `POST /api/ovk/projects/{p}/export/{kind}/{id}/sign` (kind `protokoll`|`intyg`,
  valfri `ttl_seconds` 1–86400, default 3600): validerar att dokumentet finns och
  är exporterbart, returnerar signerad URL med utgångstid.
- `GET /api/ovk/export/{p}/{kind}/{id}.pdf?expires=&sig=`: verifierar signaturen
  **innan** något dokument laddas; 403 `OVK_EXPORT_SIGNATURE_REJECTED` vid
  manipulerad eller utgången länk.
- Signeringsnyckeln läses ur `CROW_EXPORT_SIGNING_KEY`. Saknas den svarar båda
  endpoints 503 `OVK_EXPORT_SIGNING_KEY_MISSING` — **ingen osignerad fallback**.
- Protokollexport kräver protokollklart record (409 `OVK_PROTOCOL_NOT_READY`),
  samma spärr som HTML-protokollet och intyget.

Pluginen registrerar routern och exporten `ovk_pdf_export`.

## Drift
Sätt `CROW_EXPORT_SIGNING_KEY` per miljö (stark slumpad hemlighet, roteras vid
behov — rotation ogiltigförklarar utestående länkar, vilket är avsett beteende).

## Ägarskap och gate
Layoutmanifest 1.13: `crow_ovk_export` i `owned_packages`/`migrated_packages`,
`test_ovk_export.py` i `owned_tests`; ägarskapsvakt, `known-first-party`,
modulens beroenden och package-data uppdaterade.

Gate: `ruff format` → `ruff check` → `mypy --strict` → `pytest`. Tester täcker
signaturroundtrip, avvisning av manipulerad sökväg/signatur/nyckel och utgången
länk, PDF-innehåll för båda dokumenttyperna via pypdf-extraktion, ytans hela
kedja sign→download för båda typerna, 403/503/409/404/422 samt TTL-gränser.
