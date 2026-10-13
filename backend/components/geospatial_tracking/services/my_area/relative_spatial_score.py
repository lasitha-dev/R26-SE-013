"""GEO-AREA-01 Section 14/17: Relative Spatial Score at the authorized
area.

ARCHITECTURAL DECISION (documented, not a placeholder oversight):
this function always returns an UNAVAILABLE score. Section 14's
preferred rule is conditional -- "use actual point-in-polygon / model-
cell membership IF GEOMETRY SUPPORTS IT" -- and it genuinely does not,
within what this checkpoint is scoped to reuse:

  - The real `/cells` GeoJSON contract exposes only cell CENTROIDS
    (`CellFeature.geometry: GeoJSONPointGeometry`, `api/router.py::
    _cell_features`, verified read-only) -- there is no Polygon geometry
    type anywhere in `api/schemas.py`, so "does the farm point fall
    inside a returned cell" is not answerable from that response at all
    (a point cannot geometrically contain another point).
  - The real per-cell polygon footprint DOES exist
    (`ScientificGridCell.bounds_utm`/`.polygon()`,
    `services/geospatial/scientific_grid.py`) and a real, frozen
    containment function already exists for it
    (`assign_target_to_scientific_evaluation_domain`,
    `services/geospatial/scientific_domain.py`) -- but reaching it
    requires calling `build_scientific_evaluation_domain(...)` a SECOND
    time for the same origin, independently of the summary/cells fetch
    this checkpoint already performs. Section 12 explicitly says not to
    do that ("do not rebuild those calculations independently").
  - Approximating a cell's footprint from its centroid + the frozen
    `SCIENTIFIC_GRID_CELL_SIZE_KM` constant (degrees-per-km offset) was
    considered and rejected: the real footprint is a square in each
    scientific component's own local UTM projection, not a fixed
    degree-offset box in WGS84 -- a degree-based approximation would
    disagree with the real boundary near component edges, which is
    exactly the kind of invented geometry Section 14 forbids ("do NOT
    invent an interpolation").

So: `value=None`, `status=SCORE_STATUS_CELL_GEOMETRY_NOT_EXPOSED` on
every call -- honest, never a guessed number, never a nearest-cell
fallback (which Section 14 forbids unless "existing scientific protocol
explicitly defines nearest-cell assignment", which it does not for
score assignment). A later checkpoint could close this gap by either
exposing `bounds_utm` on the public `CellFeatureProperties` schema, or
adding a dedicated read-only wrapper around
`assign_target_to_scientific_evaluation_domain` -- deliberately out of
this checkpoint's scope.
"""

from __future__ import annotations

from ...domain.my_area_enums import RELATIVE_SPATIAL_SCORE_LABEL, RELATIVE_SPATIAL_SCORE_TEMPORAL_BASIS, SCORE_STATUS_CELL_GEOMETRY_NOT_EXPOSED
from ...domain.my_area_models import RelativeSpatialScoreContext


def build_relative_spatial_score_context() -> RelativeSpatialScoreContext:
    return RelativeSpatialScoreContext(
        value=None,
        label=RELATIVE_SPATIAL_SCORE_LABEL,
        temporal_basis=RELATIVE_SPATIAL_SCORE_TEMPORAL_BASIS,
        status=SCORE_STATUS_CELL_GEOMETRY_NOT_EXPOSED,
        scientific_cell_id=None,
    )
