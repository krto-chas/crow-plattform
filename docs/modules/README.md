# Modulernas dokumentation och idébank

Detta är den gemensamma ingången för planerade och befintliga verksamhetsmoduler i CROW Platform.

## Grundregel
- Varje modul har en egen katalog under `docs/modules/<module-id>/`, **även om kod ännu inte finns**.
- Idéer och beslut dokumenteras i Git med datum, status, syfte, avgränsning, beroenden och acceptanskriterier där det är relevant.
- Dokumentation och förslag är **inte** liktydiga med godkänd implementation, produktionsstatus eller beslut om prioritering.
- Domänspecifika krav ska ligga i modulens katalog; plattformsövergripande krav hanteras i plattformens arkitektur/ADR och länkas från modulen.
- Varje ny modul ska ha en `README.md` som index och minst ett dokument för krav, idéer eller arkitektur.
- Förändringar föreslås via PR och granskas enligt `AGENTS.md`, `docs/engineering/` och `docs/CONSTITUTION.md`. Ingen merge utan produktägarens beslut.
- Vid ny diskussion: kontrollera först befintlig modulmapp, komplettera där, undvik parallella motstridiga dokument. Märk ut öppna frågor och skilj fastställda krav från rekommendationer.
- Dokumentera först; implementera inte automatiskt bara för att en idé har registrerats.

## Moduler
- [CROW Security](crow-security/README.md) – planerad säkerhetsmodul, inklusive Edge och nätverksinventering.

## Föreslagen statusvokabulär
`idé` · `under utredning` · `föreslagen` · `beslutad` · `implementeras` · `verifierad` · `avförd`.

Varje dokument bör ange **Status**, **Senast uppdaterad**, **Ägare/beslutsfattare**, **Berörd modul** och **Relaterade dokument**.
