# Pass 48 — Självläkande dokumentsökvägar och pipeline-körning i UI

## Fältfynd (Mandelblomman, andra körningen)
1. "Dokumentfilen finns inte" vid PDF-visning: dokumentindexet lagrar
   absoluta sökvägar vid import, så mappbytet crow-plattform (Pass 46-rådet)
   gjorde alla tidigare importerade dokument onåbara.
2. Pipeline fastnade på "1 av 6": analysstegen (claims → authority →
   technical delta → commercial) har endpoints men UI:t anropade dem aldrig.

## Åtgärd 1: sökvägsläkning i `load_index`
`_heal_document_path` körs vid varje indexläsning: relativa sökvägar löses
mot dataroten; inaktuella absoluta sökvägar remappas till projektets
uploads-katalog när en fil med samma namn finns där; annars lämnas strängen
orörd. Absoluthet detekteras för både Windows- och POSIX-format så index
skrivna på en plattform läker på en annan. Lagrad data muteras aldrig —
läkningen sker i minnet vid läsning. Ditt Mandelblomman-projekt börjar
fungera igen utan omimport.

## Åtgärd 2: "Kör analys"-knapp i dashboardens pipelinepanel
Kör stegen sekventiellt (claims, authority, technical delta,
commercial-profil, impact, review) med stegvis statustext; vid fel visas
vilket steg som stannade och varför, därefter laddas projektet om så
pipeline och nästa åtgärder uppdateras.

## Verifiering
4 nya läkningstester (inkl. Windows-sökväg läst på annan plattform) + UI-
serveringstest. Totalt 427 gröna, mypy strict 205 filer, ruff 0.

## Framtida
Riktig portabilitet (relativ lagring i crowpkg-formatet) kvarstår som
arkitekturpunkt; läkningen täcker rename/flytt tills dess.
