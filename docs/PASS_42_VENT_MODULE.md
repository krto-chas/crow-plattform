# Pass 42 — Crow Vent som första riktiga modul

## Vad
`modules/crow-vent-module/` är ett eget distribuerbart wheel som implementerar
0.5-plugin-kontraktet (ModuleManifest, ModuleCapabilities, claim schemas,
validate_claim med lexikonvalidering, healthcheck) och upptäcks via entry
point-gruppen `crow.modules`. Verifierat: `crow module validate` → PASS,
`crow module list` → `crow.vent 1.0.0 [entrypoint:vent]`, eget wheel byggt.

## Beroenderiktningen rättad (ADR-003)
`crow_takeoff_consolidation` importerar inte längre `crow_vent`. Backbone
definierar `DesignationLexicon` (Protocol); domänmodulen tillhandahåller
implementationen och konsumenter injicerar den. Backbone → domän-importen
från Pass 41 är eliminerad (0 träffar).

## Svar på 0.5-frågan
Hela 0.5-backbonen (module SDK, conformance, trust, migrations, audit,
project aggregate) finns redan i repot sedan alpha22-konsolideringen —
inget behövde hämtas ur äldre paket. Detta pass ÅTERANVÄNDER kontraktet i
den nya kodbasen istället för att bygga ett parallellt.

## Kvarvarande flytt (medvetet uppskjuten)
`src/crow_vent` (lexikon, klassificering, kvantitet) ligger kvar i huvud-
distributionen eftersom ~20 paket importerar den. Full utflyttning till
modul-wheelet är nästa steg i plugin-SDK-återföreningen och bör ske
tillsammans med capability-deklarationer (ADR-011-förberedelse). Tills dess
är modulgränsen etablerad och kontraktet bevisat.

## Testnot
`test_cli_list_handles_no_installed_modules` var miljöberoende (föll så
snart en modul fanns installerad — vilket nu är repots normalläge).
Åtgärdad med monkeypatch av entry points + nytt discovery-test som kräver
att crow.vent hittas.
