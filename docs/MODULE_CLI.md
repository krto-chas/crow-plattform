# Crow Module CLI

## Validera en modul

```bash
crow module validate \
  crow_example_module.plugin:ExamplePlugin \
  --source-root examples/crow_example_module/src \
  --backbone-version 1.0.0 \
  --domain-model-version 1.0.0
```

Exitkoder:

- `0`: modulen är kompatibel,
- `1`: konformitetsfel,
- `2`: modulen kunde inte laddas eller kommandot var ogiltigt.

Kontrollerna omfattar manifest, semantisk versionering, kompatibilitetsintervall,
Human Review, healthcheck, determinism och förbjudna privata Core-importer.
