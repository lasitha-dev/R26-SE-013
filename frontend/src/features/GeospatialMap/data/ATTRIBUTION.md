# `sri-lanka-districts-adm2.geojson` — data provenance

**GEO30B Section 16**: real Sri Lanka district (ADM2) administrative
boundaries, used ONLY to draw the authenticated vet's own registered
district as a subtle outline/fill on the national map — never a
hand-drawn or hardcoded polygon.

- **Source**: [geoBoundaries](https://www.geoboundaries.org/) —
  `LKA-ADM2-46371173` (25 districts, 2017 boundary vintage), fetched from
  the project's own published simplified GeoJSON:
  `https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/LKA/ADM2/geoBoundaries-LKA-ADM2_simplified.geojson`
- **Underlying data**: OpenStreetMap contributors, via Wambacher
  (`wambachers-osm.website/boundaries/`).
- **License**: Open Data Commons Open Database License (ODbL) 1.0.
  Required attribution: "© OpenStreetMap contributors" — this app
  surfaces that text through MapLibre's own attribution control (the
  district source's `attribution` property), the same mechanism already
  used for the OSM raster basemap (`basemapConfig.js`).
- **Fetched**: 2026-08-30, read-only, no modification to geometry beyond
  what `services/districtGeometry.js` selects (one district's `Feature`
  by real name match) — the file itself is never rewritten by app code.
- **Field used**: `properties.shapeName` (e.g. `"Matara District"`),
  matched against the real authenticated vet's `district` field
  (`operational-context`'s `vet_district`) via the same normalized
  substring match convention as the backend's own
  `host_operational_adapter.py::district_matches`.

Not used for anything beyond visual district emphasis — never treated as
a scientific/model output, never used to filter clinical case
authorization (that boundary is enforced server-side, independent of
whether this geometry loads successfully).
