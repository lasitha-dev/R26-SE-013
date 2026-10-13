"""GEO-AREA-01 enums for the Page-2 "My Area" backend contract.

Deliberately separate from `domain/enums.py` (Checkpoint 3 live-scientific
domain) and `domain/operational_enums.py` (GEO-INT-01 operational
boundary), though it composes both: "My Area" answers "what real
historical/model context is relevant to one of my authorized farms",
which needs BOTH an authorized farm (operational boundary) AND real
historical/model origins (scientific read path) -- neither existing enum
module owns that composition.
"""

from __future__ import annotations

from enum import Enum


class MyAreaStatus(str, Enum):
    """Top-level result state of one `MyAreaContext` request. Mirrors
    GEO-INT-01's `OperationalStatus` discipline: every branch that cannot
    proceed maps to an explicit value here, never a fabricated `OK` with
    partial/guessed data. Several values are reused VERBATIM from the
    existing scientific 10A contract (`services/application/
    frozen_geospatial_analysis_10a.py`) rather than declared as new,
    differently-spelled synonyms -- `UNSUPPORTED_DISEASE`,
    `ORIGIN_NOT_FOUND`, and `ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY`
    are byte-identical to `UNSUPPORTED_DISEASE_10A` /
    `ORIGIN_NOT_FOUND_10A` (value `"ORIGIN_NOT_FOUND"`, verified read-only
    in `services/integration/geospatial_api_protocol_10a.py`) /
    `ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY_10A`."""

    OK = "OK"
    UNAUTHORIZED = "UNAUTHORIZED"
    NON_VET_FORBIDDEN = "NON_VET_FORBIDDEN"
    NO_ASSIGNED_FARMS = "NO_ASSIGNED_FARMS"
    ASSIGNED_AREA_NOT_FOUND = "ASSIGNED_AREA_NOT_FOUND"
    LOCATION_REQUIRED = "LOCATION_REQUIRED"
    UNSUPPORTED_DISEASE = "UNSUPPORTED_DISEASE"
    NO_RELEVANT_ORIGINS = "NO_RELEVANT_ORIGINS"
    ORIGIN_NOT_FOUND = "ORIGIN_NOT_FOUND"
    FORECAST_FRAME_UNAVAILABLE = "FORECAST_FRAME_UNAVAILABLE"
    ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY = "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"
    OPERATIONAL_DATA_UNAVAILABLE = "OPERATIONAL_DATA_UNAVAILABLE"
    ANALYSIS_INTERNAL_ERROR = "ANALYSIS_INTERNAL_ERROR"
    """Reused verbatim from `ANALYSIS_INTERNAL_ERROR_10A` -- the router's
    own catch-all for a genuinely unexpected scientific-read failure,
    never raised deliberately by any gate in this module."""


class ForecastDayBasis(str, Enum):
    """What a `NominalReachContext.day` actually represents -- mirrors
    the frontend adapter's `status: dayIndex === 0 ? 'observed' :
    'forecast'` distinction (`lsdOutbreakAdapter.js`, verified read-only),
    now made explicit server-side too."""

    OBSERVED_ORIGIN_CONTEXT = "OBSERVED_ORIGIN_CONTEXT"  # D0
    FORECAST = "FORECAST"  # D+1..D+7


class NominalReachRelation(str, Enum):
    """Section 16: a deterministic, strictly non-clinical relation
    between the area's distance to a scientifically defined reach ANCHOR
    and the real nominal-reach value for the selected day. Never
    `INFECTED`/`SAFE`/`INSIDE_OUTBREAK`/`PREDICTED_INFECTION_ZONE` -- this
    is contextual geometry only.

    GEO-AREA-01H Section 4 finding: as of this checkpoint, the frozen
    scientific contract defines NO such anchor at all --
    `services/integration/nominal_reach_9c.py::nominal_reach_km(day_h) =
    frozen_S0_rate_km_day * day_h` is a pure function of `day_h` alone,
    with zero spatial input (verified read-only: no coordinate, source,
    or origin appears anywhere in that module). The frontend's own
    `nominalReachRing.js` independently reached the same conclusion --
    its docstring states it deliberately draws a ring around EVERY real
    source rather than "arbitrarily picking one ... as 'the' ring
    center", specifically to avoid implying a single point of origin the
    data doesn't establish.

    Consequently `WITHIN_NOMINAL_VISUALIZATION_REACH`/
    `OUTSIDE_NOMINAL_VISUALIZATION_REACH` are never produced by this
    checkpoint's code -- they remain declared only so a LATER checkpoint
    that genuinely establishes a defensible anchor (e.g. a future
    scientific-protocol amendment defining reach as source-centered) has
    a place to put that result without a second enum. See
    `NominalReachAnchorBasis` for why the current value is always
    `NOT_APPLICABLE`.
    """

    WITHIN_NOMINAL_VISUALIZATION_REACH = "WITHIN_NOMINAL_VISUALIZATION_REACH"
    OUTSIDE_NOMINAL_VISUALIZATION_REACH = "OUTSIDE_NOMINAL_VISUALIZATION_REACH"
    NOT_APPLICABLE = "NOT_APPLICABLE"  # D0, or no scientifically defined anchor to compare against


class NominalReachAnchorBasis(str, Enum):
    """Section 13: self-describing reason `NominalReachContext.relation`
    is (always, this checkpoint) `NOT_APPLICABLE` -- so a frontend never
    has to infer "why" from a bare enum value."""

    NO_SCIENTIFICALLY_DEFINED_REACH_ANCHOR = "NO_SCIENTIFICALLY_DEFINED_REACH_ANCHOR"
    """`nominal_reach_km` is real and origin-level, but no single
    geographic point is defined anywhere in the frozen scientific
    contract to measure the area's distance against for a WITHIN/OUTSIDE
    determination -- see `NominalReachRelation`'s docstring for the full
    evidence trail."""


RELEVANT_ORIGIN_DISTANCE_BASIS = "NEAREST_T0_TRIGGER_SOURCE"
"""Section 8: `RelevantOrigin.distance_from_area_km` self-describing
basis -- computed against `origin.trigger_source_ids_at_t0` (the sources
that actually DEFINE the origin's identity/existence,
`services/forecast_origin.py`), never `analysis.eligible_sources` (a
different, broader, active-window-dependent set only meaningful for one
already-SELECTED origin's own analysis -- see
`NearestHistoricalSource`/`NEAREST_SOURCE_SEMANTICS_9C`). Declared once
here so the field's meaning never has to be inferred from a comment
alone."""

NOMINAL_REACH_DISCLAIMER = "Nominal reach — visualization only, not a disease boundary."
"""Section 16's exact required wording -- every response carrying a
`NominalReachContext` must preserve this disclaimer unmodified."""

RELATIVE_SPATIAL_SCORE_LABEL = "Relative Spatial Score"

RELATIVE_SPATIAL_SCORE_TEMPORAL_BASIS = "STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT"
"""Reused verbatim from the frozen 10A limitation string
`RUNTIME_LIMITATIONS_10A`'s `"STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT_
NOT_A_DAY_VARYING_PREDICTION"` -- Section 17: the score must never be
presented as day-varying, so its temporal basis is stated explicitly on
every response, not left implicit."""

GEOSPATIAL_STUDY_COUNTRY = "Sri Lanka"
"""GEO-AREA-01S: the ADRS Geospatial application's own real operational
study scope -- verified read-only against
`frontend/src/features/GeospatialMap/pages/OutbreakMapPage.jsx`'s own
hardcoded `const COUNTRY = 'Sri Lanka'` (Page 1) and
`useNationalOutbreaks.js`'s docstring ("the real Sri Lanka LSD corpus").

Declared here, in the already-established shared My-Area enums module
(`domain/analysis_trends_enums.py` already imports several other
constants from this exact module rather than redeclaring them -- see
that module's own docstring), rather than in a brand-new module, so
every Page that must restrict its scientific reads to the same real
country has exactly ONE source of truth to import from. Every such Page
(My Area, Analysis & Trends) is expected to consume THIS constant
directly or via a same-value re-export -- never a second hardcoded
`"Sri Lanka"` literal, and never a per-page duplicate that could drift.
Never accepted from a client query/header/body -- this is a
server/application-controlled constant, not a request parameter."""

SCORE_STATUS_CELL_GEOMETRY_NOT_EXPOSED = "SCORE_UNAVAILABLE_CELL_GEOMETRY_NOT_EXPOSED_FOR_CONTAINMENT"
"""See `services/my_area/relative_spatial_score.py`'s module docstring
for the full evidence-backed explanation of why this status is the
correct, honest answer this checkpoint gives for every request -- the
public `/cells` GeoJSON contract exposes only cell CENTROIDS (verified
read-only, `api/router.py::_cell_features`), never the real per-cell
polygon footprint (`ScientificGridCell.bounds_utm`), so true point-in-
cell containment cannot be determined from the data this checkpoint is
scoped to reuse without re-invoking the internal scientific-domain
construction a second time -- which Section 12 explicitly says not to do
("do not rebuild those calculations independently")."""