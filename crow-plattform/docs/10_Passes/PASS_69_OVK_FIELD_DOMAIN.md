# Pass 69 – OVK Field Domain

## Mål

Införa en mobil/offline-kompatibel fältdomän för OVK utan att låsa visuell design eller synkteknik.

## Levererat i passet

- `crow_ovk_field` med frozen dataclasses för lägenhet/lokal, rum, fältfinding och foto-evidens.
- Foto-evidens kräver fysisk enhet, läsbart enhetsnummer, feltyp, fångsttid, användare, lokal URI, MIME-typ och SHA-256.
- `PhotoSyncStatus` för kommande offline/synkflöde.
- Versionerat `defect_types.json` som installationsdata. Kategorierna är operativa klassificeringar och inte juridiska slutsatser.
- Regelreferenser valideras mot `crow_regulations`; okända regel-ID:n accepteras inte.
- Foto får kopplas till rum, finding, kontrollpunkt och ventilationssystem.
- `FieldFinding` kan projiceras till befintlig `crow_ovk.OvkFinding` utan en parallell OVK-besiktningsmodell.

## Viktiga regler

1. Bilder är evidensobjekt, inte lösa bilagor.
2. Bildens `unit_number` måste matcha den registrerade lägenheten/lokalen.
3. Bild måste ha en känd `defect_type`.
4. SHA-256 används som stabil innehållsidentitet inför media-sync och deduplicering.
5. Feltypslexikonet får inte användas som automatisk normbedömning.
6. Regelhänvisningar är explicita och måste finnas i Pass 68-biblioteket.

## Medvetet utanför scope

- Kamera-UI och slutlig mobil design.
- IndexedDB/service worker.
- Push/pull-synk och konfliktlösning.
- Binär bilduppladdning/serverlagring.
- Automatisk regelbedömning utifrån feltyp.
- Bildanalys/AI.

Dessa hör till följande field/offline-pass.
