# Vent Intelligence Core — RC readiness pass 5

## Scope

This pass integrates the supplied Swedish ventilation designation lexicon as packaged,
configuration-driven runtime data in `crow_vent`.

Implemented:

- typed lexicon loading from packaged JSON;
- deterministic parsing of complete duct strings such as `T13-250x400-V1`;
- component lookup with running-number extraction;
- explicit ambiguity handling for `AF` using layer/system context;
- configurable project layer overrides;
- SB11 recognition for `V-57*` / `V57*` layers;
- freehand fallback mappings for common layers such as `KANAL_ISO`;
- evidence and confidence fields on every successful interpretation;
- regression tests for positive, ambiguous and rejected inputs.

Not implemented or claimed:

- complete CoClass layer decoding;
- BIP TypeID lookup;
- automatic extraction of text entities from DWG;
- quantity takeoff from geometry;
- customer-specific profiles beyond caller-provided project overrides.
