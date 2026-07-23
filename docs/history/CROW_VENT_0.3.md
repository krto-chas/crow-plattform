# Crow Vent 0.3 — Quantity Takeoff

Crow Vent 0.3 adds a provenance-preserving quantity layer on top of classified ventilation systems.

## Included

- component counts grouped by type, category and dimension
- circular and rectangular dimension parsing (`Ø160`, `300x200`)
- length aggregation when geometry evidence exposes `length` or `length_m`
- measured/unmeasured coverage metrics
- quantity rows linked to Vent systems and source classification IDs
- semicolon-separated UTF-8 CSV export suitable for Swedish Excel
- Workbench quantity summary and export link

The quantity engine never invents dimensions or lengths. Missing properties remain explicitly unmeasured.
