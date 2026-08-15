# Ventilation Graph Audit 0.1

`VentGraphAudit` granskar evidenskomplettering och dataintegritet i en Building Graph-snapshot.

## Grundregel

Frånvaro av en relation är inte bevis på ett projekteringsfel. Därför klassas avsaknad av
`feeds` eller `belongs_to` som `evidence_gap` med `review_required`, aldrig som ett verifierat
fel i anläggningen.

## Regler

| Regel | Innebörd | Klassning |
|---|---|---|
| VENT-EVID-001 | Luftdon saknar explicit inkommande `feeds` | Evidence gap |
| VENT-EVID-002 | Ventilationsobjekt saknar explicit `belongs_to` mot system | Evidence gap |
| VENT-DQ-001 | Relation refererar till saknat objekt | Verifierat datakvalitetsfel |
| VENT-DQ-002 | Explicit ventilationsrelation saknar evidens-ID | Verifierad datakvalitetsbrist |

Motorn gör ingen geometrisk, lexikal eller AI-baserad inferens. Resultatet märks med
`inference_performed: false` och `missing_information_treated_as_defect: false`.
