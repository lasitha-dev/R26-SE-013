"""GEO-AREA-01 domain objects for the Page-2 "My Area" backend contract.

Reuses `domain/operational_models.py::OperationalFarm` verbatim for
`MyAreaContext.area` (Section 19 -- same minimal, GPS-validated,
PII-free farm shape GEO-INT-01 already defined; no second farm DTO is
declared) and `VerifiedClinicalContext` verbatim for
`verified_clinical_contexts` (Section 18 -- the same semantic-firewalled
shape, never a My-Area-specific reinterpretation).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields

from .my_area_enums import RELEVANT_ORIGIN_DISTANCE_BASIS
from .operational_models import OperationalFarm, VerifiedClinicalContext


@dataclass(frozen=True)
class RelevantOrigin:
    """Section 10: one real historical/model origin, ranked by real
    distance from the authorized area. `scientific_mode` is the origin's
    own `temporal_mode` (e.g. `RETROSPECTIVE_PROXY`) -- never a fabricated
    "current"/"live" label. `distance_basis` (Section 8, GEO-AREA-01H)
    makes explicit that this distance is measured to the origin's real
    T0 TRIGGER source(s) -- the sources that define the origin's
    identity -- never implying `ForecastOrigin` itself has a coordinate."""

    origin_id: str
    disease: str
    t0: str
    distance_from_area_km: float
    distance_basis: str = RELEVANT_ORIGIN_DISTANCE_BASIS
    scientific_mode: str | None = None


@dataclass(frozen=True)
class NearestHistoricalSource:
    """Section 9/13 (GEO-AREA-01H reaffirmed): the nearest REAL ELIGIBLE
    historical source to the area, for one selected origin's own
    analysis -- `analysis.eligible_sources`, the SAME set/concept the
    existing `/sources` route and its `NEAREST_SOURCE_SEMANTICS_9C`
    disclaimer already use ("a geometric reference only, never a
    confirmed transmission origin"). Deliberately a DIFFERENT source set
    from `RelevantOrigin.distance_basis`'s T0 trigger sources (Section 7:
    "eligible source != trigger source") -- this value must never be
    read as, or renamed to imply, "distance to origin" (GEO-AREA-01H
    Section 2's corrected issue); it is its own concept, kept under its
    own name. No date field -- the real `/sources`-equivalent output
    (`SourceFeatureProperties`, verified read-only) carries no date, so
    none is fabricated here."""

    source_id: str
    distance_from_area_km: float
    availability_quality: str | None = None
    gps_quality: str | None = None


@dataclass(frozen=True)
class RelativeSpatialScoreContext:
    """Section 14: `value` is `None` whenever true cell containment
    cannot be determined (see `my_area_enums.SCORE_STATUS_CELL_GEOMETRY_
    NOT_EXPOSED`) -- never interpolated, never a nearest-cell fallback,
    never converted to a percentage."""

    value: float | None
    label: str
    temporal_basis: str
    status: str
    scientific_cell_id: str | None = None


@dataclass(frozen=True)
class NominalReachContext:
    """Section 15/16/17 (GEO-AREA-01H hardened): `nominal_reach_km` is
    `None` for D0 (never fabricated as `0`) and for any day with no real
    entry in the origin's `nominal_reach_by_day`. `disclaimer` always
    carries Section 16's exact required sentence.

    GEO-AREA-01H Section 2/4/6 correction: this dataclass NO LONGER
    carries a "distance to origin" field. `nominal_reach_km(day_h) =
    frozen_S0_rate_km_day * day_h` (`services/integration/
    nominal_reach_9c.py`, verified read-only) is a pure function of
    `day_h` alone with zero spatial input -- no single geographic point
    is scientifically defined anywhere to measure the area's distance
    against. `relation` is therefore always `NOT_APPLICABLE` this
    checkpoint, and `anchor_basis` states why explicitly rather than
    leaving that to be inferred. The real scalar `nominal_reach_km` is
    still returned -- a magnitude can be real even when no containment
    relation can be defended (Section 6's own framing)."""

    day: int
    forecast_date: str | None
    basis: str  # ForecastDayBasis value
    nominal_reach_km: float | None
    relation: str  # NominalReachRelation value -- NOT_APPLICABLE this checkpoint, see anchor_basis
    anchor_basis: str  # NominalReachAnchorBasis value
    disclaimer: str

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass(frozen=True)
class SelectedOriginContext:
    """Section 12: built only after the real scientific summary/sources
    for `origin_id` were successfully fetched via the existing read
    path -- never independently recomputed.

    GEO-AREA-01H Section 12 correction: `t0` (the origin's real, actual
    availability date) is now carried explicitly -- it was previously
    only reachable indirectly via `nominal_reach_context.forecast_date`,
    which is `None` for every D+N day. Exposing `t0` directly lets a
    future frontend reuse its own already-tested `forecastDate.js`
    utility (`addDaysToIsoDate(t0, day)`) without this backend
    reimplementing calendar-date arithmetic."""

    origin_id: str
    disease: str
    forecast_day: int
    forecast_date: str | None
    t0: str
    nearest_historical_source: NearestHistoricalSource | None
    relative_spatial_score: RelativeSpatialScoreContext
    nominal_reach_context: NominalReachContext


@dataclass(frozen=True)
class MyAreaContext:
    """Section 19 top-level response DTO."""

    status: str  # MyAreaStatus value
    disease: str | None = None
    area: OperationalFarm | None = None
    relevant_origins: list[RelevantOrigin] = field(default_factory=list)
    selected_origin_context: SelectedOriginContext | None = None
    verified_clinical_contexts: list[VerifiedClinicalContext] = field(default_factory=list)
    generated_at: str | None = None

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}
