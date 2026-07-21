# PROVENANCE — 0.6.0-RC-samlingen

Härkomst och disposition för samtliga delpaket i samlingen `0_6_0-RC.zip`
(28 zippar + V3.0-mappen). Detta repo (`0.7.0-alpha.1`) är den enda levande
källan; allt nedan är superseded och kan arkiveras eller raderas.

## Utvecklingslinje (äldst → nyast, varje steg innehåller det föregående)

| # | Paket | Disposition |
|---|---|---|
| 1 | crow-0.6.0-alpha22-consolidated | Bas: backbone + pipeline + docs + CAF-governance. Superseded. |
| 2 | crow-workbench-beta-foundation | Workbench-grunden (FastAPI + frontend). Superseded. |
| 3–12 | crow-workbench-beta-geometry-framework 0.1–0.9 + 1.0-rc1 | Geometry Framework växer fram (DXF-parser, index, topologi, system). Superseded. |
| 13 | crow-workbench-beta-import-framework | Import-plugins (PDF/IFC/DXF/DWG/bild/JSON/CSV/DOCX/XLSX). Superseded. |
| 14–16 | crow-workbench-crow-vent 0.1–0.3 | Vent-kunskapsmodul in-tree. Superseded. |
| 17–21 | crow-platform-2.0-building-graph sprint1–4 + 1.0-rc1 | Building Graph (objekt/relationer/evidens/historik). Superseded. |
| 22–25 | crow-platform-2.3-reasoning-engine sprint1–4 | Traversering, regler, findings-livscykel. Superseded. |
| 26–28 | crow-platform-2.4-inference-engine sprint1–4 | Deterministisk inferens med förklaringar, review, promotion. **sprint4 = källan till detta repo.** |

## Utanför linjen

**V3.0/crow-platform-3.0-complete.zip — ingår INTE, medvetet.**
88 filer varav 32 py; README utlovar en "körbar modulär monolit" med elva
moduler, men backend är router-stubbar (inkl. `README.stub`), frontenden är
55 rader TSX totalt, och paketet innehåller inte 2.4-kodbasen (~250 py-filer).
Det är förpackning utan innehåll — samma mönster som ursprungliga CAF RC1.
Det som har återbrukbart värde (docker-compose, nginx-konfig, CI-yml,
React/Vite-skelett) kan hämtas härifrån när ett riktigt frontend-arbete
påbörjas, men "3.0" som versionsanspråk är annullerat.

## Versionshistorik, korrigerad

Numreringen "2.0 / 2.3 / 2.4 / 3.0" uppstod utan att någon 0.6-, 1.x- eller
2.x-version någonsin släpptes, taggades eller verifierades. Den ersätts av:

- `0.5.0` — Foundation Release (externt validerad, kontrakt frysta)
- `0.6.0-alpha.1 … alpha.22` — Sprint B, Document Intelligence-kedjan
- `0.7.0-alpha.1` — detta repo: alpha22 + Workbench + Import + Geometry +
  Building Graph + Reasoning + Inference + Vent-kunskapspaket, sanerat
- Nästa stabila mål: `0.7.0` när RC-kriterierna i CAF-CMP-001 är uppfyllda

Regel framåt (upprepning av CAF-REL-001): ingen versionssiffra utan
verifikationsmanifest, och major-versioner kräver ett skäl, inte en känsla.
