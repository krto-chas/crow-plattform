# Crow Platform 2.3 – Reasoning Engine RC1, Sprint 1

Sprinten inför en domänneutral traverseringsmotor ovanpå Crow Building Graph 1.0 RC1.

## Levererat

- riktad och dubbelriktad BFS-traversering
- upstream och downstream
- kortaste väg
- impact analysis med sammanställning per objekttyp och disciplin
- isolerade objekt
- dead-end-detektering
- cykeldetektering
- återanvändbart adjacency-index
- cache i tjänstelagret som invalideras när grafen ändras
- Workbench-API

## API

- `GET /api/projects/{project_id}/reasoning/traverse/{object_id}`
- `GET /api/projects/{project_id}/reasoning/path`
- `GET /api/projects/{project_id}/reasoning/impact/{object_id}`
- `GET /api/projects/{project_id}/reasoning/diagnostics`

## Avgränsning

Sprinten innehåller inte ännu regelmotor, findings, event bus, subscriptions eller CrowQL. Dessa byggs ovanpå traverseringsmotorn i följande sprintar.
