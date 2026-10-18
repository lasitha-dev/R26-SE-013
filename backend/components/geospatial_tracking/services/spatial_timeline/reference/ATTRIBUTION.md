# `sri_lanka_districts_adm2.geojson` — provenance

Byte-identical copy of `frontend/src/features/GeospatialMap/data/sri-lanka-districts-adm2.geojson`,
so the backend spatial-timeline service can clip risk zones to Sri Lanka and summarise risk per
district without reading frontend files.

- Source: geoBoundaries `LKA-ADM2-46371173` (25 districts, 2017 boundary vintage), simplified release.
- Underlying data: © OpenStreetMap contributors. Licence: ODbL 1.0.
- Field used: `properties.shapeName` (e.g. `"Matara District"`). Never modified by application code.
