# Hotfix pass 43 — DwgPlugin-integrationen på rätt sökväg

Pass 43-zippen la den uppdaterade plugins.py under fel filnamn
(src/crow_import_framework_plugins.py.updated), så DwgPlugin i repot
uppdaterades aldrig — därför saknar din DWG-import conversion-objektet.

1. git checkout -b granska/pass43-hotfix
2. Packa upp denna zip över repot (skriver över src/crow_import_framework/plugins.py)
3. Ta bort ströfilen om den finns:
   git rm -f src/crow_import_framework_plugins.py.updated   (ok om den saknas)
4. git add -A && git diff --cached --stat  → ska visa 1 ändrad fil (+ ev. 1 borttagen)
5. Commit, push, PR → grönt CI → merge
6. Starta om workbenchen och LADDA UPP DWG-FILEN PÅ NYTT — konvertering sker
   vid importtillfället, den gamla tillgången konverteras inte retroaktivt.

Förväntat efteråt i Model Inspector:
- Med CROW_ODA_CONVERTER satt: conversion.status = "converted" + SHA-256 för
  original och härledd .derived.dxf
- Utan ODA: conversion.status = "converter_unavailable" med installationsråd
