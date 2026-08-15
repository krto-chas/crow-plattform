# RC-010 real-project DXF acceptance record

## Source

- File: `Mandelblomman - Aggregat1_0002.dxf`
- Size: `1886380` bytes
- SHA-256: `41d46177ac4e93ade674cff10a6258b2621cc995e2deb4dfb24b1b35811e56b7`
- Format: `dxf`

## Import result

- Importer: `crow.import.dxf`
- Layers: `1`
- Total inventoried entities: `7120`
- Normalized entities: `1722`
- Preview entities: `1722`
- Preview truncated: `False`
- Unsupported entity types: `{'3DFACE': 5384}`
- Malformed or unparsed supported types: `None`
- Omitted from normalized preview: `5384`

## Entity inventory

| Entity type | Count |
|---|---:|
| `3DFACE` | 5384 |
| `BLOCK` | 7 |
| `ENDBLK` | 7 |
| `INSERT` | 7 |
| `LINE` | 1715 |

## Warnings

- DXF contains entity types without preview support; they were inventoried but not converted to normalized preview geometry: 3DFACE=5384.

## Acceptance

- Parser completed: **TRUE**
- Known losses reported: **TRUE**
- Silent loss detected: **FALSE**

This record verifies parser completion and explicit loss reporting. It does not claim
that unsupported 3D entities have been normalized or rendered.
