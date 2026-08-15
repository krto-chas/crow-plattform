# IFC explicit relation import

`crow_ifc_relations` läser uttryckliga relationer ur IFC STEP-text utan geometri- eller AI-inferens.

## Stöd i v0.1

| IFC-entitet | Kanonisk relation | Riktning |
|---|---|---|
| `IfcRelAggregates` | `contains` | RelatingObject → RelatedObjects |
| `IfcRelContainedInSpatialStructure` | `located_in` | RelatedElements → RelatingStructure |

Övriga `IfcRel*`-typer inventeras och rapporteras men översätts inte utan en beslutad semantisk mappning.

## Tvåstegsmodell

1. IFC-relationerna extraheras med ursprungliga IFC-ID:n.
2. De översätts till `ExplicitRelationAssertion` endast när både källa och mål redan har en explicit IFC→CCM-mappning.

Saknade objekt skapas inte automatiskt. Om en referens saknar CCM-mappning rapporteras den som `unmapped_ifc_ids`, och relationen hoppas över.

## Evidens

Varje översatt relation bär:

- källfilens ID och SHA-256,
- IFC-relationens entity-ID,
- IFC-relationstyp,
- ursprungliga source/target IFC-ID:n,
- `confidence = 1.0` för den uttryckliga IFC-semantiken.

Detta säger endast att relationen uttryckligen finns i IFC-filen. Det innebär inte att modellen tekniskt är korrekt eller komplett.
