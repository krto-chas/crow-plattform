# Pass 46 — Repo-städning och namnbyte

## Utfört
- Roten bantad 107 → 17 poster: verifikationsbevis → `docs/verification/`,
  demoskript → `scripts/demos/`, ersatta changelogs/releasedokument →
  `docs/history/`, regenererbara körartefakter (crow-*.json m.fl.) raderade
  (tjänsterna skriver dem per projektfil; inget i src/tests/scripts läser
  dem från roten — verifierat med referenssvep före flytt).
- `docs/`: `40_Architecture` invikt i `00_Architecture`; alla sprint-/pass-
  dokument samlade i `docs/10_Passes/`; nytt `docs/README.md` som index.
- Distributionen omdöpt `crow-sprint-a` → `crow-plattform` (pyproject +
  modulberoendet i crow-vent-module). Namnet var historiskt missvisande.
- `.gitattributes` med `* text=auto eol=lf` (CRLF hade smugit in i
  pyproject) och CRLF-undantag för `.bat`.

## Genomförande i git
`scripts/pass46_cleanup.sh` utför flyttarna med `git mv`/`git rm` så att
historiken bevaras. Ordning: granska-gren → kör skriptet → packa upp
överlägget (uppdaterade filer) → `git add -A` → granska diff → PR.

## Verifiering efter städning
Ruff 0, Mypy strict 0 (204 filer), 420 tester, `crow review` 4/4 PASS,
`crow module list` hittar crow.vent 1.0.0, RC-009 e2e-baseline PASS.
Inga sökvägsberoenden bröts.
