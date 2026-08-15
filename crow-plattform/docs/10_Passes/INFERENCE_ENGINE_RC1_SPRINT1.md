# Crow Inference Engine RC1 — Sprint 1

Sprinten introducerar ett separat, deterministiskt inferenslager ovanpå Building Graph.
Källgrafen ändras aldrig av inferensmotorn.

## Levererat

- transitiv inferens för `served_by`, `located_in` och `depends_on`
- deterministiska ID:n för härledda relationer
- förklaringskedjor till explicita relationer
- confidence-propagation
- deduplicering mot explicita och tidigare härledda slutsatser
- konfliktkontroll för motstridiga egenskapsvärden
- atomisk persistens i `building-graph/inferences.json`
- API för körning, läsning och förklaring

## API

- `GET /api/projects/{project_id}/inference/relations`
- `POST /api/projects/{project_id}/inference/run`
- `GET /api/projects/{project_id}/inference/relations/{relation_id}/explanation`

## Säkerhetsprincip

Inferensresultat är härledda påståenden, inte accepterade grundfakta. De hålls därför
separerade från `graph.json` och måste uttryckligen granskas eller materialiseras av ett
senare arbetsflöde.
