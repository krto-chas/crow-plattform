# Sprint B2 — Document Model

Version: `0.6.0-alpha.3`

B2 introducerar stabila dokumentpositioner och gör varje PDF-sida adresserbar.

## Modell

```text
CrowDocument
└── DocumentPage
    └── DocumentRegion
        └── BoundingBox (normaliserad 0..1)
```

## Implementerat

- `DocumentPage` med sidnummer, geometri, rotation och textfingerprint,
- `DocumentRegion` med stabil locator och normaliserad bounding box,
- inbyggd PDF-textutvinning via pypdf,
- automatisk markering `OCR_REQUIRED` när en sida saknar extraherbar text,
- fullside-region för varje sida,
- beständig lagring av sidor och regioner,
- bakåtkompatibel laddning av äldre index,
- projektsummering av sidantal, regioner, OCR-behov och textmängd.

## Provenance

En position representeras stabilt som exempelvis:

```text
doc:...#page=4&xywh=0.100000,0.200000,0.300000,0.050000
```

Koordinater lagras normaliserat för att vara oberoende av DPI och rendering.

## Avgränsning

B2 använder endast PDF:ens inbyggda textlager. Ingen OCR, LLM, symboligenkänning
eller semantisk klassificering av regioner utförs ännu.
