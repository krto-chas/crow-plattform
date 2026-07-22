# CCM identity candidates

Crow does not merge objects merely because two drawing texts look alike.

`VentCanonicalAssembler` may create a `same_as_candidate` relation when all of the
following deterministic fields match:

- canonical object type,
- component code,
- explicit component number,
- explicit ventilation system context.

The relation is marked `review_required`. It means that two observations are a
candidate for representing the same physical component; it is not a confirmed
identity and it does not remove either source object or its evidence.

No candidate is produced for duct strings, missing component numbers, or objects
assigned to different systems. Geometry and spatial proximity are not used yet.
