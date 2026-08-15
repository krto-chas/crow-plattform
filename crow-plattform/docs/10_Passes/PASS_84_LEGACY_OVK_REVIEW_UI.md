# Pass 84 — Legacy OVK Review UI + Batch Migration

## Scope

Göra Pass 80/83 användbart utan handskrivna JSON-payloads. Workbench får en modulägd yta på `/ovk/legacy` där flera äldre `.pdf`/`.xlsx` kan förhandsgranskas, reviewas och commit:as som historiska serverbesiktningar.

## Säkerhetsprinciper

- Preview skriver aldrig till historiken.
- Explicit extraherade fakta är förvalda men kan avmarkeras.
- Tvetydiga reviewposter är alltid avmarkerade från början.
- En reviewpost måste aktivt godkännas och få både fälttyp och granskat värde innan commit.
- Varje källfil commit:as separat. Ett fel i en fil stoppar inte övriga filer i batchen.
- Pass 83:s servervalidering för käll-SHA, datum och proveniens är fortfarande den auktoritativa spärren.

## Flöde

1. Ange projekt och importansvarig.
2. Välj flera PDF/XLSX.
3. Crow skapar preview per fil.
4. Granska extraherade fakta och tvetydiga rader.
5. Ange/justera historiskt besiktnings-ID och datum.
6. Commit:a en fil eller alla färdiggranskade filer.
7. Resultat redovisas per fil och materialiseras i samma history/restore-lager som fältbesiktningar.

## Avgränsning

Detta pass bygger gransknings- och batcharbetsytan, inte nya parserprofiler. Verkliga arkivmallar används senare för att förbättra precisionen i Pass 80:s parseradaptrar. `.xls` är fortsatt explicit ostött tills en riktig adapter finns.

## Gate

- Ruff
- root mypy strict
- first-party module mypy strict
- pytest
- architecture review
- distribution build
