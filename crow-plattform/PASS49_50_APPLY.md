# Pass 49–50 — gren-zip: Berghällen golden dataset + crow_pressure_test

## Innehåll (alla sökvägar repo-relativa, lägg ovanpå main)
- NYA: evidence/reference_datasets/berghallen/ (manifest.json + expected_findings.json)
- NYA: src/crow_pressure_test/ (__init__.py, models.py, knowledge.py, extraction.py,
       py.typed, tathetsprovning_lexikon.json)
- NYA: scripts/build_berghallen_manifest.py
- NYA: tests/test_berghallen_dataset.py, tests/test_pressure_test_knowledge.py,
       tests/test_pressure_test_extraction.py
- NYA: docs/10_Passes/PASS_49_*.md, PASS_50_*.md
- ÄNDRADE (hela filen ersätts): pyproject.toml (package-data + mypy-listan),
       CHANGELOG.md (ny post överst)

Inga filer med .updated-suffix denna gång — allt ligger på slutlig sökväg.

## Applicera
    git checkout -b granska/pass49-50
    # packa upp zipen i reporoten (skriv över pyproject.toml + CHANGELOG.md)
    pip install -e ".[dev]"
    ruff check . && mypy && pytest -q

Förväntat: Ruff 0, mypy strict 0 (209 filer), 447 passed + 1 skipped.
Det skippade testet är env-gated checksummeverifiering; kör det skarpt med:
    CROW_BERGHALLEN_ARCHIVE="/sökväg/till/Förfrågan vent Berghällen.zip" pytest tests/test_berghallen_dataset.py

## Verifierat i byggmiljön
- Checksummetestet grönt mot den riktiga förfrågningszipen (SHA-256-match).
- q_max klass C vid 400 Pa = 0,147387 l/(s·m²) — samma värde som protokollmallen.
- B/C-konflikten (QL vs kravtabell) detekteras med båda källdokumenten i konflikten.
