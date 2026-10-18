"""Day-indexed (D0..D14) spatial timeline built ONLY from the frozen,
evaluated geospatial models -- no new risk formula.

Reused verbatim (same calls as the 10A runtime, `frozen_geospatial_analysis_10a.py`):
  - scientific domain + 5 km grid: `build_scientific_evaluation_domain` with `RUNTIME_GRID_CONFIG_10A`
  - relative spatial score C0(x) = sum_j exp(-d(x, source_j) / 25 km): `score_origin_candidates_7c(..., wind=None)`
  - geometric direction: `compute_cell_direction_tendency_8b3`
  - nominal reach: `nominal_reach_km` / `derived_nominal_reach_interval` (S0 = 3.946 km/day)

What changes from day to day, and why:
  - The eligible source set is fixed at the as-of date (the frozen C0 is a
    STATIC-T0 model; no future case is ever invented), so the C0 cells and the
    relative-risk zones are identical on every day.
  - The nominal reach envelope (S0 x day around each source) grows, and the
    reach-limited zones are the parts of the SAME C0 zones inside it. This is a
    visualization of the documented 9C reach quantity, not a forecast of where
    cases will occur.
  - Days 8-14 extend the reach formula beyond its D1-D7 development horizon
    and are labelled EXPLORATORY.

Risk tiers use the same snapshot-relative quartile rule the map's Risk Zones
layer already uses (frontend `mapLibreAdapter.computeRiskTierStats`): >= Q3
highest, >= median high, >= Q1 moderate, otherwise lower. Relative ranks
within one snapshot, never probabilities, never comparable across snapshots.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

import pyproj
import shapely
from shapely.geometry import LineString, Point, mapping, shape
from shapely.ops import transform as shapely_transform
from shapely.ops import unary_union
from shapely.prepared import prep

from ..application.frozen_geospatial_analysis_10a import (
    ACTIVE_SOURCE_WINDOW_DAYS_10A,
    DISEASE_MODEL_READINESS_10A,
    DISEASE_MODEL_STATUS_READY_10A,
    RUNTIME_GRID_CONFIG_10A,
    RUNTIME_LIMITATIONS_10A,
    runtime_provenance_10a,
)
from ..direction.c0_cell_local_tendency_8b3 import compute_cell_direction_tendency_8b3
from ..geospatial.scientific_domain import build_scientific_evaluation_domain
from ..geospatial.source_geometry import EligibleSourcePoint
from ..integration.nominal_reach_9c import (
    FROZEN_S0_RATE_KM_DAY_9C,
    NOMINAL_REACH_SEMANTICS_9C,
    PRIMARY_HORIZON_DAYS_9C,
    derived_nominal_reach_interval,
    nominal_reach_km,
)
from ..model_development.candidate_registry_7c import C0_FAMILY, FROZEN_KERNEL_SCALE_KM, build_candidate_registry_7c
from ..model_development.local_evaluation_scope import PRIMARY_LOCAL_EVALUATION_DISTANCE_KM
from ..model_development.wind_scoring_7c import score_origin_candidates_7c
from .districts import District, geodesic_area_km2, load_districts, sri_lanka_land
from .risk_raster import GRID_SPEC as RISK_RASTER_GRID
from .risk_raster import GATE_SDS as RISK_GATE_SDS
from .risk_raster import MIN_SCORE as RISK_VISIBLE_MIN_SCORE
from .risk_raster import ScoredLand, build_day_raster, district_cells, iso_gate, source_district_influence
from .spread_direction import CASE_KAPPA, HEURISTIC_ID, INERTIA_KAPPA, LOOKAHEAD_KM, MIN_CONFIDENCE, SECTORS, WIND_KAPPA, daily_heading
from .sources import TimelineSource

CONTRACT_VERSION = "SPATIAL_TIMELINE_1.0"
ENGINE_VERSION = "SPATIAL_TIMELINE_ENGINE_3.2"  # 3.2: district view only -- an existing outbreak's front becomes a modelled NEW OUTBREAK on the first day it has moved and stands in the district (Day 1 inside, the arrival day from outside); the new outbreak spreads on with its own path and kernel (weighted by its seed score) and the existing path and kernel spine stop there; 3.1: one heading per case per day from land, cattle, NET daily wind and the 8B.3 push of nearby cases (spread_direction.py), turned gradually within the day, held at the coast instead of deflected; every case with any preferred direction gets a path; 3.0: trajectory from evaluated quantities only (8B.3 streamline at the 9C rate, land, 25 km domain; no wind/cattle, no coast deflection), honest stop reasons, per-day distance check, direction-averaged risk for cases without directional evidence; 2.2: per-day practical risk field + map raster (C0 kernel gated by the reach along each case's path); 2.1: 3-hour wind blocks; tapered plume from the real wind-direction spread; 2.0: practical per-case heading (cattle density, land, wind, existing cases, course) + per-case spread plume; 1.9: one path per case; same-group cases share wind and do not repel; 1.8: 1 km coastal tolerance for paths; Risk Zones reach follows the group paths; 1.7: one path per outbreak group (12.37 km), heading = wind (downwind, by steadiness) + 8B.3 (by clarity); 1.6: day-by-day source paths (8B.3 direction field stepped at the 9C rate, on land); 1.5: fixed display bands on the bounded score 1-exp(-C0); direction-shaped daily reach (reach_display); 1.1: national source pool, Asia/Colombo dates, 25 km source-direction neighbourhood; 1.2: land-only tier statistics, per-cell geometry; 1.3: stable feature ids, corridors capped at the 25 km direction domain, district polygon in scope; 1.4: land-clipped display geometry (cells + reach envelope) so a district view is not cut at the administrative border
MAX_HORIZON_DAYS = 14
EVALUATED_HORIZON_DAYS = max(PRIMARY_HORIZON_DAYS_9C)  # 7

STATUS_OK = "OK"
STATUS_NO_ELIGIBLE_SOURCES = "NO_ELIGIBLE_SOURCES"
STATUS_MODEL_NOT_READY = "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"
STATUS_NO_GRID = "ANALYSIS_UNAVAILABLE_GRID"

HORIZON_AS_OF = "AS_OF_OBSERVED_CONTEXT"
HORIZON_EVALUATED = "WITHIN_D1_D7_REACH_HORIZON"
HORIZON_EXPLORATORY = "EXPLORATORY_BEYOND_D7_REACH_HORIZON"

TIER_ORDER = ("lower", "moderate", "high", "highest")
TIER_LABELS = {
    "highest": "Highest relative risk", "high": "Elevated relative risk",
    "moderate": "Moderate relative risk", "lower": "Lower relative risk",
}
TIER_RULE = ("SNAPSHOT_QUARTILES_OF_RAW_C0_OVER_SCORED_LAND_CELLS: >=Q3 highest, >=median high, >=Q1 moderate, else lower "
             "(linear-interpolation quantiles; cells whose centroid is off Sri Lanka land are not tiered)")
TIER_STATUS_OFF_LAND = "OFF_LAND_NOT_TIERED"

# Display bands (fixed, identical on every day and in every snapshot) on the
# BOUNDED score B = 1 - exp(-C0). B is a strictly increasing transform of the
# frozen C0, so it ranks every cell exactly as the evaluated model does; it only
# bounds overlapping contributions to [0, 1) (two co-located sources -> 0.86,
# one -> 0.63). Thresholds are the project's display bands, NOT calibrated
# probabilities. The quartile `tier` fields are unchanged.
DISPLAY_BANDS = (("high", 0.70), ("elevated", 0.40), ("moderate", 0.15), ("low", 0.0))
DISPLAY_SCORE_RULE = ("BOUNDED_SCORE = 1 - exp(-raw C0); FIXED_BANDS high >= 0.70, elevated >= 0.40, moderate >= 0.15, "
                      "else low; display bands, not infection probabilities")
# Day-d display reach. A case with a path: a ribbon of half-width tau_d (the
# risk field's position uncertainty, below) around the path travelled so far.
# A case without a path: the isotropic 9C disc of radius S0 x d. The C0 score
# is never changed by direction (7C: no directional model was selected).
REACH_DISPLAY_SEMANTICS = "DIRECTION_SHAPED_NOMINAL_REACH_FOR_DISPLAY_NOT_A_TRANSMISSION_ROUTE"

# Day-by-day path (Trajectory), ONE PER CASE:
#   heading    once a day at the front, `spread_direction.daily_heading` scores
#              every direction by land ahead, cattle ahead (FAO GLW4), the day's
#              NET wind (vector mean of 24 h, so sea/land breezes cancel) and the
#              frozen 8B.3 push of the nearby eligible cases (away from where
#              cases are dense), plus the previous day's course. Wind and cattle
#              are labelled extensions (7C/7D candidates were not selected).
#   movement   within the day the heading turns gradually from yesterday's to
#              today's over the day's steps -- a smooth curve, never a zigzag.
#              The front advances the evaluated 9C rate S0 per day.
#   coast      a step that would leave land ends that day's movement: the front
#              waits at the coast (`held_at_coast`) and the next day's heading,
#              which already sees no land that way, moves it on. Never a point at
#              sea, never a slide along the shoreline. District borders never stop it.
#   limits     REACHED_25KM_LOCAL_DOMAIN (the distance the C0 model and its
#              direction were evaluated within -- a research limit, not a display
#              constant); NO_DIRECTIONAL_EVIDENCE when no direction is preferred
#              at all (no land ahead, or every factor flat): no path is invented.
# An estimated spread tendency for display, not a transmission route and not
# a predicted outbreak site.
PATH_STEP_KM = 0.5
PATH_SEMANTICS = "DAILY_SPREAD_TENDENCY_LAND_CATTLE_NET_WIND_8B3_AT_9C_RATE_NOT_A_TRANSMISSION_ROUTE"
PATH_METHOD = ("one heading per day from land, FAO GLW4 cattle, net daily wind and the 8B.3 push of nearby cases "
               "(spread_direction.daily_heading), turned gradually within the day, stepped at the 9C rate")
PATH_GROUP_EPS_KM = 12.37

# Practical day-d risk field (Risk Zones surface), one kernel per eligible case:
#
#   c_j(x)  = exp(-r_j / 25 km) * min(g_reach_j, p_j * g_path_j + (1 - p_j) * g_iso_j)
#   g_path  = max_k exp(-1/2 * (|x - p_k| / tau_d)^2)       a tube along the case's day-d path
#   g_iso   = the same tube around a straight path of length L_d = min(S0 x d, 25 km)
#             in an UNKNOWN direction, averaged over all directions
#   g_reach = exp(-1/2 * (max(0, r_j - S0 x d) / tau_d)^2)  the 9C nominal reach
#   F_d(x)  = sum_j c_j(x)   (overlapping cases add up, exactly as in C0);  display score 1 - exp(-F_d)
#
#   exp(-r/25 km)  the frozen C0 kernel (distance from the case farm).
#   p_j            the case's directional share at its farm = |8B.3 resultant| /
#                  total C0 mass there (0 when there is no path): how strongly the
#                  evaluated field points one way rather than all ways.
#   tau_d          2.5 km (half a 5 km grid cell, the model resolution) (+) half the
#                  frozen 9B bootstrap reach interval at day d.
#
# Day 0 is the case farm at the model's resolution. Each gate is <= 1, so
# F_d <= C0 everywhere: the field never shows more than the frozen model -- it
# only withholds the part of C0 a case cannot have reached yet. The source set
# stays the one eligible at the as-of date on every day, as in the evaluated
# STATIC-T0 model. No environmental factor and no invented direction: a case
# without directional evidence spreads its risk evenly over all directions.
RISK_FIELD_RESOLUTION_KM = 2.5
RISK_FIELD_SEMANTICS = "DAY_D_C0_KERNEL_GATED_BY_NOMINAL_REACH_ALONG_THE_8B3_PATH_NOT_AN_INFECTION_PROBABILITY"
# The ADM2 land polygon is generalised at the shoreline; a front within ~1 km
# of it is still on land (same idea as the 0.05 deg coastal tolerance used for
# source eligibility). It never turns a path along the coast.
PATH_COAST_TOLERANCE_DEG = 0.01
PATH_STOP_DOMAIN_CAP = "REACHED_25KM_LOCAL_DOMAIN"
PATH_STOP_NO_DIRECTION = "NO_DIRECTIONAL_EVIDENCE"
PATH_STOP_OFF_LAND = "NEXT_STEP_OFF_LAND"
PATH_STOP_HORIZON = "HORIZON_END"

DIRECTION_INDETERMINATE = "INDETERMINATE_NO_DIRECTIONAL_MASS"
DIRECTION_AVAILABLE = "GEOMETRIC_TENDENCY_AVAILABLE"

ZONE_SEMANTICS = "RELATIVE_SPATIAL_SCORE_TIER_ZONE_NOT_INFECTION_PROBABILITY_NOT_QUARANTINE_BOUNDARY"
REACH_ZONE_SEMANTICS = "RELATIVE_RISK_ZONE_WITHIN_NOMINAL_REACH_VISUALIZATION_ONLY"
CORRIDOR_SEMANTICS = "C0_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY_AT_SOURCE_NOT_A_TRANSMISSION_ROUTE"

ENGINE_LIMITATIONS = (
    *RUNTIME_LIMITATIONS_10A,
    "SOURCE_SET_FIXED_AT_AS_OF_DATE_NO_FUTURE_CASES_ARE_GENERATED",
    "C0_SURFACE_AND_TIER_ZONES_IDENTICAL_ON_EVERY_DAY_STATIC_T0_MODEL",
    "DAY_TO_DAY_CHANGE_IS_THE_NOMINAL_REACH_ENVELOPE_ONLY",
    "DAYS_8_14_EXTRAPOLATE_THE_D1_D7_REACH_FORMULA_EXPLORATORY",
    "RISK_TIERS_ARE_SNAPSHOT_RELATIVE_QUARTILES_NOT_COMPARABLE_ACROSS_SNAPSHOTS",
    "SCORED_AREA_LIMITED_TO_25KM_SOURCE_BUFFER_DOMAIN_REACH_BEYOND_IT_SHOWS_NO_ZONES",
    "OPERATIONAL_SOURCE_POSITION_IS_THE_FARM_GPS_NOT_THE_ANIMAL_LOCATION",
    "ENVIRONMENTAL_VARIABLES_NOT_USED_IN_ANY_SCORE",
    "SOURCE_DIRECTION_ONLY_FROM_OTHER_ELIGIBLE_SOURCES_WITHIN_25KM_ELSE_INDETERMINATE",
    "OPERATIONAL_SOURCES_ARE_VET_VERIFIED_DIAGNOSES_NOT_OFFICIAL_OUTBREAK_CONFIRMATIONS",
    "TIER_QUARTILES_COMPUTED_OVER_SCORED_LAND_CELLS_ONLY_OCEAN_CELLS_NOT_TIERED",
    "UNSCORED_LAND_OUTSIDE_THE_25KM_SOURCE_DOMAIN_IS_NOT_LOW_RISK_IT_IS_NOT_SCORED",
)

ENVIRONMENT_BLOCK = {
    "status": "NOT_INTEGRATED",
    "used_in_score": False,
    "reason": (
        "No evaluated environmental influence model exists (wind/host candidates were not selected in 7C/7D). "
        "The ERA5 adapter is historical reanalysis (Open-Meteo archive, ~5-day publication lag) and no weather "
        "forecast source is integrated, so no environmental values are reported for these dates."
    ),
    "candidate_variables": [
        {"name": "temperature_2m", "unit": "degC", "source": "ERA5 reanalysis (Open-Meteo archive)", "kind": "REANALYSIS"},
        {"name": "dew_point_2m", "unit": "degC", "source": "ERA5 reanalysis (Open-Meteo archive)", "kind": "REANALYSIS"},
        {"name": "precipitation", "unit": "mm", "source": "ERA5 reanalysis (Open-Meteo archive)", "kind": "REANALYSIS"},
        {"name": "wind_speed_10m", "unit": "km/h", "source": "ERA5 reanalysis (Open-Meteo archive)", "kind": "REANALYSIS"},
        {"name": "wind_direction_10m", "unit": "deg", "source": "ERA5 reanalysis (Open-Meteo archive)", "kind": "REANALYSIS"},
    ],
}

_GEOD = pyproj.Geod(ellps="WGS84")
_CORRIDOR_POINTS = 16
_COORD_PRECISION = 1e-5  # ~1 m; far below the 5 km cell size
_SIMPLIFY_TOLERANCE_DEG = 0.0001  # ~11 m; far below the 5 km cell size


@dataclass(frozen=True)
class TimelineScope:
    kind: str  # "national" | "district"
    district: District | None = None

    @property
    def key(self) -> str:
        return "national" if self.kind == "national" else f"district:{self.district.name}"

    def mask(self):
        return sri_lanka_land() if self.kind == "national" else self.district.geometry

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "district": self.district.name if self.district else None,
            "country": "Sri Lanka",
            "boundary_source": "geoBoundaries LKA ADM2 (ODbL, (c) OpenStreetMap contributors)",
            # The administrative polygon the map must use for this scope (district only;
            # national scope = the island union the frontend already loads).
            "district_geometry": mapping(self.district.geometry) if self.district else None,
        }


def disease_model_ready(disease_display: str) -> bool:
    return DISEASE_MODEL_READINESS_10A.get(disease_display) == DISEASE_MODEL_STATUS_READY_10A


def frame_dates(as_of: date, horizon_days: int) -> list[tuple[int, date]]:
    return [(d, as_of + timedelta(days=d)) for d in range(horizon_days + 1)]


def horizon_status(day: int) -> str:
    if day == 0:
        return HORIZON_AS_OF
    return HORIZON_EVALUATED if day <= EVALUATED_HORIZON_DAYS else HORIZON_EXPLORATORY


def reach_for_day(day: int) -> dict:
    if day == 0:
        return {"nominal_reach_km": None, "interval_km": None, "rate_km_day": FROZEN_S0_RATE_KM_DAY_9C,
                "semantics": NOMINAL_REACH_SEMANTICS_9C, "note": "Day 0 is the as-of context; reach starts at day 1."}
    lower, upper = derived_nominal_reach_interval(day)
    return {
        "nominal_reach_km": nominal_reach_km(day), "interval_km": [lower, upper], "rate_km_day": FROZEN_S0_RATE_KM_DAY_9C,
        "semantics": NOMINAL_REACH_SEMANTICS_9C,
        "note": None if day <= EVALUATED_HORIZON_DAYS else "Beyond the D1-D7 development horizon of the rate estimate.",
    }


def snapshot_identity(*, disease_display: str, scope: TimelineScope, as_of: date, horizon_days: int,
                      sources: list[TimelineSource]) -> str:
    provenance = runtime_provenance_10a()
    payload = {
        "contract": CONTRACT_VERSION, "engine": ENGINE_VERSION,
        "c0": provenance["frozen_c0_candidate_id"], "spec": provenance["frozen_7c_spec_hash"],
        "direction": provenance["direction_method_protocol_hash_8b3"],
        "disease": disease_display, "scope": scope.key, "as_of": as_of.isoformat(), "horizon_days": horizon_days,
        "sources": [s.as_dict() for s in sorted(sources, key=lambda s: s.source_id)],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "stl_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _quantile(sorted_values: list[float], q: float) -> float:
    idx = q * (len(sorted_values) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (idx - lo)


def tier_thresholds(scores: list[float]) -> dict | None:
    if not scores:
        return None
    ordered = sorted(scores)
    return {"q1": _quantile(ordered, 0.25), "median": _quantile(ordered, 0.5), "q3": _quantile(ordered, 0.75)}


def tier_for(score: float | None, thresholds: dict | None) -> str | None:
    if score is None or thresholds is None:
        return None
    if score >= thresholds["q3"]:
        return "highest"
    if score >= thresholds["median"]:
        return "high"
    if score >= thresholds["q1"]:
        return "moderate"
    return "lower"


@lru_cache(maxsize=32)
def _to_wgs84(analysis_crs: str) -> pyproj.Transformer:
    return pyproj.Transformer.from_crs(analysis_crs, "EPSG:4326", always_xy=True)


def _polygonal(geometry):
    """Valid polygonal part only (drops stray lines/points a clip can create)."""
    if geometry is None or geometry.is_empty:
        return None
    if not geometry.is_valid:
        geometry = shapely.make_valid(geometry)
    if geometry.geom_type in ("Polygon", "MultiPolygon"):
        return geometry
    parts = [g for g in getattr(geometry, "geoms", []) if g.geom_type in ("Polygon", "MultiPolygon") and not g.is_empty]
    return unary_union(parts) if parts else None


def _finish(geometry):
    """Valid, precision-snapped polygonal output. Callers simplify BEFORE
    clipping, so the clip boundary is never crossed by simplification."""
    geometry = _polygonal(geometry)
    if geometry is None:
        return None
    geometry = _polygonal(shapely.set_precision(geometry, _COORD_PRECISION))
    return geometry if geometry is not None and not geometry.is_empty else None


@lru_cache(maxsize=512)
def _aeqd_to_wgs84(lat: float, lon: float) -> pyproj.Transformer:
    aeqd = pyproj.CRS.from_proj4(f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs")
    return pyproj.Transformer.from_crs(aeqd, "EPSG:4326", always_xy=True)


def _geodesic_disc(lat: float, lon: float, radius_km: float):
    """True geodesic-radius disc: a circle in the source-centred azimuthal
    equidistant projection, transformed to WGS84."""
    return shapely_transform(_aeqd_to_wgs84(lat, lon).transform, Point(0.0, 0.0).buffer(radius_km * 1000.0, quad_segs=32))


def bounded_score(raw: float | None) -> float | None:
    return None if raw is None else 1.0 - math.exp(-raw)


def display_band(score: float | None) -> str | None:
    if score is None:
        return None
    return next(band for band, minimum in DISPLAY_BANDS if score >= minimum)


@lru_cache(maxsize=512)
def _wgs84_to_aeqd(lat: float, lon: float) -> pyproj.Transformer:
    aeqd = pyproj.CRS.from_proj4(f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs")
    return pyproj.Transformer.from_crs("EPSG:4326", aeqd, always_xy=True)


def _reach_display_shape(lat: float, lon: float, day: int):
    """Display reach of a case WITHOUT a path on day `day`: the isotropic 9C
    disc of radius S0 x day, built in a source-centred metric projection."""
    disc = Point(0.0, 0.0).buffer(FROZEN_S0_RATE_KM_DAY_9C * day * 1000.0, quad_segs=32)
    return shapely_transform(_aeqd_to_wgs84(lat, lon).transform, disc)


def group_sources(sources: list, eps_km: float = PATH_GROUP_EPS_KM) -> list[list]:
    """Single-linkage groups of sources within `eps_km` (geodesic)."""
    parent = list(range(len(sources)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, a in enumerate(sources):
        for j in range(i + 1, len(sources)):
            b = sources[j]
            if _GEOD.inv(a.longitude, a.latitude, b.longitude, b.latitude)[2] / 1000.0 <= eps_km:
                parent[find(i)] = find(j)
    groups: dict[int, list] = {}
    for i, source in enumerate(sources):
        groups.setdefault(find(i), []).append(source)
    return sorted(groups.values(), key=lambda g: min(s.source_id for s in g))


def front_tendency(lat: float, lon: float, points: list) -> dict:
    """8B.3 at one point from the eligible cases within the 25 km local
    evaluation distance of it (a case's own zero-distance term carries no
    direction, by the method)."""
    near = [p for p in points if _GEOD.inv(lon, lat, p.longitude, p.latitude)[2] / 1000.0 <= PRIMARY_LOCAL_EVALUATION_DISTANCE_KM]
    t = compute_cell_direction_tendency_8b3({"scientific_cell_id": "PATH_FRONT", "centroid_lat": lat, "centroid_lon": lon}, near)
    share = t.resultant_magnitude / t.total_scalar_c0_mass if t.total_scalar_c0_mass else 0.0
    return {"method": "8B.3", "bearing_deg": t.bearing_deg, "directional_clarity": t.directional_clarity,
            "directional_share": round(min(1.0, share), 4), "cases_within_25km": len(near)}


def trace_source_path(origin_lat: float, origin_lon: float, points: list, horizon_days: int, land_contains, *,
                      as_of: date | None = None, wind_by_date: dict | None = None, initial_bearing: float | None = None) -> dict:
    """Day-by-day front of one case (see PATH_* above). Returns the stepped
    coordinates, the coordinate index of each day's front (Day 0 = the farm),
    each day's heading basis and why the path stopped. `initial_bearing`:
    the course the front arrived on, when this path continues another
    front (a new outbreak), so its first day turns gradually from it."""
    coords = [(origin_lon, origin_lat)]
    day_index = [0]
    basis_by_day: list[dict | None] = [None]
    travelled = 0.0
    stop = PATH_STOP_HORIZON
    previous = initial_bearing
    for day in range(1, horizon_days + 1):
        if stop != PATH_STOP_HORIZON:
            day_index.append(len(coords) - 1)
            basis_by_day.append(None)
            continue
        lon, lat = coords[-1]
        # Travel during day d uses the net wind of the calendar day it starts on.
        wind = (wind_by_date or {}).get((as_of + timedelta(days=day - 1)).isoformat()) if as_of else None
        cases = front_tendency(lat, lon, points)
        basis = {**daily_heading(lat, lon, land_contains=land_contains, case_tendency=cases, wind=wind, previous_bearing=previous),
                 "cases_within_25km": cases["cases_within_25km"], "held_at_coast": False, "moved_km": 0.0}
        if basis["bearing_deg"] is None:
            stop = PATH_STOP_NO_DIRECTION
            day_index.append(len(coords) - 1)
            basis_by_day.append(basis)
            continue
        start = previous if previous is not None else basis["bearing_deg"]
        turn = ((basis["bearing_deg"] - start) + 180.0) % 360.0 - 180.0
        budget = min(FROZEN_S0_RATE_KM_DAY_9C, PRIMARY_LOCAL_EVALUATION_DISTANCE_KM - travelled)
        steps = max(1, math.ceil(budget / PATH_STEP_KM - 1e-9))
        moved, last_moved = 0.0, None
        for i in range(steps):
            step = min(PATH_STEP_KM, budget - moved)
            if step <= 1e-9:
                break
            heading = (start + turn * (i + 1) / steps) % 360.0
            nlon, nlat, _ = _GEOD.fwd(coords[-1][0], coords[-1][1], heading, step * 1000.0)
            if not land_contains(Point(nlon, nlat)):
                # The front waits at the coast while the heading keeps turning
                # toward today's bearing; that step's distance is not made up.
                basis["held_at_coast"] = True
                continue
            coords.append((nlon, nlat))
            moved += step
            travelled += step
            last_moved = heading
        basis["moved_km"] = round(moved, 3)
        # The course is the direction actually moved last; a day spent waiting keeps it.
        previous = last_moved if last_moved is not None else previous
        if travelled + 1e-9 >= PRIMARY_LOCAL_EVALUATION_DISTANCE_KM:
            stop = PATH_STOP_DOMAIN_CAP
        day_index.append(len(coords) - 1)
        basis_by_day.append(basis)
    return {"coords": coords, "day_index": day_index, "basis_by_day": basis_by_day, "length_km": round(travelled, 3), "stop_reason": stop}


def _distance_check(path: dict, day: int, reach: dict) -> dict | None:
    """Day-d distance of the path against the evaluated reach: drawn length,
    straight-line displacement from the farm, and the 9C reach with its 9B
    interval. The path is never longer than the nominal reach."""
    if day < 1:
        return None
    upto = path["day_index"][day]
    coords = path["coords"][: upto + 1]
    drawn = sum(_GEOD.inv(*coords[i - 1], *coords[i])[2] for i in range(1, len(coords))) / 1000.0
    lon0, lat0 = path["origin"]
    lower, upper = reach["interval_km"]
    return {"drawn_km": round(drawn, 3), "displacement_km": round(_GEOD.inv(lon0, lat0, *coords[-1])[2] / 1000.0, 3),
            "nominal_reach_km": reach["nominal_reach_km"], "reach_interval_km": [lower, upper],
            "within_nominal_reach": drawn <= reach["nominal_reach_km"] + 1e-6}


def _ribbon(path: dict, day: int) -> dict | None:
    """The case's path so far widened by tau_d (its position uncertainty), on land."""
    upto = path["day_index"][day] if day >= 1 else 0
    if upto < 1:
        return None
    lon0, lat0 = path["origin"]
    to_xy = _wgs84_to_aeqd(lat0, lon0)
    line = LineString([to_xy.transform(lon, lat) for lon, lat in path["coords"][: upto + 1]])
    ribbon = shapely_transform(_aeqd_to_wgs84(lat0, lon0).transform, line.buffer(risk_fringe_km(day) * 1000.0, quad_segs=12))
    ribbon = _finish(ribbon.intersection(sri_lanka_land()))
    return mapping(shapely.set_precision(ribbon, _COORD_PRECISION)) if ribbon is not None else None


def risk_fringe_km(day: int) -> float:
    """tau_d: the 5 km model resolution combined with half the frozen 9B
    bootstrap reach interval at day d (0 on Day 0)."""
    if day < 1:
        return RISK_FIELD_RESOLUTION_KM
    lower, upper = derived_nominal_reach_interval(day)
    return math.hypot(RISK_FIELD_RESOLUTION_KM, (upper - lower) / 2.0)


def max_influence_distance_km(horizon_days: int) -> float:
    """Largest distance at which a case's day-d risk kernel can still give a
    visible score within the horizon: the path (S0 x day, capped at the 25 km
    local domain) plus GATE_SDS x the day's position uncertainty tau_d -- the
    same radius the raster evaluates (risk_raster.kernel_radius_km)."""
    day = max(0, int(horizon_days))
    return min(FROZEN_S0_RATE_KM_DAY_9C * day, PRIMARY_LOCAL_EVALUATION_DISTANCE_KM) + RISK_GATE_SDS * risk_fringe_km(day)


def source_age_days(source, on: date) -> int | None:
    try:
        return (on - date.fromisoformat(str(source.observation_date)[:10])).days
    except ValueError:
        return None


def _risk_kernel(source, path: dict | None, day: int) -> dict:
    """Day-d kernel parameters of one case (see RISK_FIELD_* above)."""
    tau = risk_fringe_km(day)
    reach = FROZEN_S0_RATE_KM_DAY_9C * day
    origin = (source.longitude, source.latitude)
    on_path = path is not None and day >= 1 and path["day_index"][day] >= 1
    spine = [[*origin, 0.0, tau]]
    if on_path:
        # Every path step (PATH_STEP_KM), so day d's spine is a prefix of day d+1's.
        spine = [[lon, lat, 0.0, tau] for lon, lat in path["coords"][: path["day_index"][day] + 1]]
    return {"source_id": source.source_id, "origin": list(origin), "reach_km": round(reach, 4), "fringe_km": round(tau, 4),
            "directional_share": path["origin_basis"]["confidence"] if on_path else 0.0,
            "iso_length_km": round(min(reach, PRIMARY_LOCAL_EVALUATION_DISTANCE_KM), 4),
            "spine": [[round(lon, 6), round(lat, 6), round(core, 4), round(sd, 4)] for lon, lat, core, sd in spine]}


def risk_field_value(lon: float, lat: float, kernels: list[dict]) -> float:
    """F_d at one point (the same formula as the map raster, risk_raster.py)."""
    total = 0.0
    for kernel in kernels:
        r = _GEOD.inv(kernel["origin"][0], kernel["origin"][1], lon, lat)[2] / 1000.0
        g_reach = math.exp(-0.5 * (max(0.0, r - kernel["reach_km"]) / kernel["fringe_km"]) ** 2)
        g_path = max(math.exp(-0.5 * (max(0.0, _GEOD.inv(plon, plat, lon, lat)[2] / 1000.0 - core) / sd) ** 2)
                     for plon, plat, core, sd in kernel["spine"])
        g_iso = float(iso_gate(r, kernel["iso_length_km"], kernel["fringe_km"]))
        share = kernel["directional_share"]
        total += kernel.get("weight", 1.0) * math.exp(-r / FROZEN_KERNEL_SCALE_KM) * min(g_reach, share * g_path + (1.0 - share) * g_iso)
    return total


def _front_bearing(coords: list, upto: int) -> float | None:
    if upto < 1:
        return None
    (lon0, lat0), (lon1, lat1) = coords[max(0, upto - 2)], coords[upto]
    if (lon0, lat0) == (lon1, lat1):
        return None
    return _GEOD.inv(lon0, lat0, lon1, lat1)[0] % 360


def _corridor(lat: float, lon: float, bearing_deg: float, length_km: float) -> LineString:
    coords = [(lon, lat)]
    for i in range(1, _CORRIDOR_POINTS + 1):
        dest_lon, dest_lat, _ = _GEOD.fwd(lon, lat, bearing_deg, length_km * 1000.0 * i / _CORRIDOR_POINTS)
        coords.append((dest_lon, dest_lat))
    return LineString(coords)


def _feature(geometry, properties: dict, feature_id: str | None = None) -> dict:
    feature = {"type": "Feature", "geometry": mapping(geometry), "properties": properties}
    if feature_id is not None:
        feature["id"] = feature_id  # deterministic: same snapshot + tier/day -> same id
        feature["properties"] = {**properties, "feature_id": feature_id}
    return feature


def _collection(features: list) -> dict:
    return {"type": "FeatureCollection", "features": features}


_NO_MODEL_REACH = {"nominal_reach_km": None, "interval_km": None, "rate_km_day": None, "semantics": None,
                   "note": "No validated spatial model for this disease: the LSD rate and reach are never reused."}


def _empty_frames(as_of: date, horizon_days: int, *, model_ready: bool = True) -> list[dict]:
    return [{
        "day": d, "date": dt.isoformat(), "horizon_status": horizon_status(d), "active_source_ids": [],
        "reach": reach_for_day(d) if model_ready else dict(_NO_MODEL_REACH), "reach_envelope": None, "reach_envelope_display": None, "reach_display": None, "reach_limited_risk_zones": _collection([]),
        "source_corridors": [], "source_paths": [], "district_summaries": [],
        "risk_field": {"kernels": [], "raster": None},
    } for d, dt in frame_dates(as_of, horizon_days)]


def build_spatial_timeline(
    *, sources: list[TimelineSource], disease_display: str, disease_code: str, as_of: date, horizon_days: int,
    scope: TimelineScope, source_exclusions: dict | None = None, source_statuses: dict | None = None,
    source_selection: dict | None = None, wind_lookup=None,
) -> dict:
    sources = sorted(sources, key=lambda s: s.source_id)
    snapshot_id = snapshot_identity(disease_display=disease_display, scope=scope, as_of=as_of, horizon_days=horizon_days, sources=sources)
    provenance = {**runtime_provenance_10a(), "engine_version": ENGINE_VERSION, "tier_rule": TIER_RULE,
                  "display_score_rule": DISPLAY_SCORE_RULE,
                  "spread_path_rule": {"method": PATH_METHOD, "heuristic": HEURISTIC_ID, "rate_km_day": FROZEN_S0_RATE_KM_DAY_9C,
                                       "rate_interval_km_day": list(derived_nominal_reach_interval(1)),
                                       "evaluated_days": EVALUATED_HORIZON_DAYS, "step_km": PATH_STEP_KM, "sectors": SECTORS,
                                       "lookahead_km": list(LOOKAHEAD_KM), "wind_kappa": WIND_KAPPA, "case_kappa": CASE_KAPPA,
                                       "inertia_kappa": INERTIA_KAPPA, "min_confidence": MIN_CONFIDENCE,
                                       "length_cap_km": PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
                                       "length_cap_basis": "PRIMARY_LOCAL_EVALUATION_DISTANCE: the C0 model and its 8B.3 direction were evaluated within it",
                                       "inputs": {"cases": "eligible case coordinates: frozen 8B.3 push away from dense cases (evaluated model)",
                                                  "reach": "9C nominal reach rate (evaluated model)", "land": "Sri Lanka land (geography)",
                                                  "wind": "net daily wind, ERA5 reanalysis / Open-Meteo forecast (EXTENSION: 7C wind candidates not selected)",
                                                  "cattle": "FAO GLW4 cattle density 2015 (EXTENSION: 7D host candidates not selected)"},
                                       "not_inputs": {"rain": "no evaluated model", "humidity": "no evaluated model"},
                                       "stop_reasons": [PATH_STOP_NO_DIRECTION, PATH_STOP_DOMAIN_CAP, PATH_STOP_HORIZON],
                                       "status": "DISPLAY_SPREAD_TENDENCY_NOT_A_VALIDATED_SPREAD_PREDICTION"},
                  "display_bands": [{"band": band, "min": minimum} for band, minimum in DISPLAY_BANDS],
                  "reach_display_rule": {"semantics": REACH_DISPLAY_SEMANTICS, "rate_km_day": FROZEN_S0_RATE_KM_DAY_9C,
                                         "length_cap_km": PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
                                         "path_ribbon_half_width": "fringe_km of the day (risk_field_rule)"},
                  "risk_field_rule": {
                      "semantics": RISK_FIELD_SEMANTICS,
                      "formula": "F_d(x) = sum_j exp(-r_j/25 km) * min(g_reach_j, p_j * g_path_j + (1 - p_j) * g_iso_j); display score = 1 - exp(-F_d)",
                      "g_path": "max_k exp(-0.5 * (max(0, |x - p_k| - core_k) / sd_k)^2) over the case's spine points (the day-d 8B.3 path)",
                      "g_iso": "the same tube around a straight path of length iso_length_km in an unknown direction, averaged over all directions",
                      "g_reach": "exp(-0.5 * (max(0, r_j - reach_km) / fringe_km)^2)",
                      "directional_share": "p_j = |8B.3 resultant| / total C0 mass at the farm; 0 without a path",
                      "kernel_scale_km": FROZEN_KERNEL_SCALE_KM, "resolution_km": RISK_FIELD_RESOLUTION_KM,
                      "reach_km": "S0 x day", "fringe_km": "hypot(resolution_km, half the 9B bootstrap reach interval at day d)",
                      "source_set": "the sources eligible at the as-of date, unchanged on every day (STATIC-T0, as evaluated)",
                      "never_exceeds": "the frozen C0 at any point (every gate <= 1)",
                      "raster": RISK_RASTER_GRID,
                      "environment": "net daily wind shapes the path (labelled extension); no environmental factor scales the score",
                  },
                  "active_source_window_days": ACTIVE_SOURCE_WINDOW_DAYS_10A,
                  "grid_cell_size_km": RUNTIME_GRID_CONFIG_10A.cell_size_km,
                  "domain_distance_km": PRIMARY_LOCAL_EVALUATION_DISTANCE_KM}
    window_start = as_of - timedelta(days=ACTIVE_SOURCE_WINDOW_DAYS_10A)
    base = {
        "contract_version": CONTRACT_VERSION, "snapshot_id": snapshot_id, "disease": disease_display, "disease_code": disease_code,
        "scope": scope.as_dict(), "as_of": as_of.isoformat(), "horizon_days": horizon_days,
        "evaluated_horizon_days": EVALUATED_HORIZON_DAYS,
        "time_window": {"source_window_start": window_start.isoformat(), "source_window_end": as_of.isoformat(),
                        "frame_start": as_of.isoformat(), "frame_end": (as_of + timedelta(days=horizon_days)).isoformat()},
        "model": {"risk": "C0 = sum_j exp(-d_j / 25 km), frozen candidate " + provenance["frozen_c0_candidate_id"],
                  "direction": "8B.3 C0 cell-local negative-gradient tendency", "reach": "9C nominal reach = S0 x day"},
        "provenance": provenance,
        "sources": [s.as_dict() for s in sources],
        "source_exclusions": source_exclusions or {},
        "source_statuses": source_statuses or {},
        "source_selection": source_selection or {},
        "environment": ENVIRONMENT_BLOCK,
        "limitations": list(ENGINE_LIMITATIONS),
    }
    empty = {"cells": [], "tier_thresholds": None, "risk_zones": _collection([]), "source_directions": [], "source_paths": [],
             "district_summaries": [], "frames": _empty_frames(as_of, horizon_days), "district_influence": None, "possible_new_cases": []}

    if not disease_model_ready(disease_display):
        return {**base, **empty, "frames": _empty_frames(as_of, horizon_days, model_ready=False),
                "model": {"risk": None, "direction": None, "reach": None}, "status": STATUS_MODEL_NOT_READY}
    if not sources:
        return {**base, **empty, "status": STATUS_NO_ELIGIBLE_SOURCES}

    points = [EligibleSourcePoint(source_id=s.source_id, latitude=s.latitude, longitude=s.longitude) for s in sources]
    domain = build_scientific_evaluation_domain(
        forecast_origin_id=f"SPATIAL_TIMELINE:{scope.key}:{as_of.isoformat()}", t0=as_of.isoformat(), sources=points,
        grid_config=RUNTIME_GRID_CONFIG_10A, primary_local_evaluation_distance_km=PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
    )
    cells_with_component = [(component, cell) for component in domain.components for cell in component.cells]
    if not cells_with_component:
        return {**base, **empty, "status": STATUS_NO_GRID}

    cell_dicts = sorted((cell.as_dict() for _, cell in cells_with_component),
                        key=lambda c: c["scientific_cell_id"] or c["grid_cell_id"])
    c0_spec = next(c for c in build_candidate_registry_7c() if c.family == C0_FAMILY)
    scores = {c.grid_cell_id: c for c in score_origin_candidates_7c(
        grid_cells=cell_dicts, sources=points, candidates=(c0_spec,), wind=None)[c0_spec.candidate_id]}
    # Tier statistics use scored LAND cells only: an offshore cell is not a
    # land monitoring area and must not shift the land quartiles. The frozen
    # C0 score of every cell is unchanged and still returned.
    land = prep(sri_lanka_land())
    on_land = {cell.grid_cell_id: land.contains(Point(cell.centroid_lon, cell.centroid_lat)) for _, cell in cells_with_component}
    thresholds = tier_thresholds([c.score for gid, c in scores.items() if c.score is not None and on_land.get(gid)])

    mask = scope.mask()
    # Per-cell clipping only ever needs the mask near the scored domain.
    lons = [cell.centroid_lon for _, cell in cells_with_component]
    lats = [cell.centroid_lat for _, cell in cells_with_component]
    local_box = shapely.box(min(lons) - 0.1, min(lats) - 0.1, max(lons) + 0.1, max(lats) + 0.1)
    local_mask = mask.intersection(local_box)
    prepared_mask = prep(local_mask)
    # Display geometry is clipped to LAND only: a district is an administrative
    # boundary, not a barrier, so a district view must not cut the scored
    # surface at its border. Scope-clipped `geometry`, zones and summaries are
    # unchanged (they remain the district product).
    district_scope = scope.kind == "district"
    local_land = sri_lanka_land().intersection(local_box) if district_scope else local_mask
    prepared_land = prep(local_land) if district_scope else prepared_mask
    tier_parts: dict[str, list] = {tier: [] for tier in TIER_ORDER}
    drawable_parts = []  # the land the map may colour (display footprints)
    cell_records = []
    for component, cell in cells_with_component:
        cell_score = scores.get(cell.grid_cell_id)
        raw = cell_score.score if cell_score else None
        cell_on_land = on_land.get(cell.grid_cell_id, False)
        tier = tier_for(raw, thresholds) if cell_on_land else None
        footprint = cell.polygon()
        if component.domain is not None and component.domain.union_geometry is not None:
            footprint = footprint.intersection(component.domain.union_geometry)
        footprint_wgs84 = shapely_transform(_to_wgs84(cell.analysis_crs).transform, footprint)
        if tier is not None and not footprint_wgs84.is_empty:
            tier_parts[tier].append(footprint_wgs84)
        # The cell's own domain-clipped footprint, clipped to the scope (land or
        # district) -- the geometry a map should draw instead of a guessed square.
        scoped = None
        if tier is not None and not footprint_wgs84.is_empty and prepared_mask.intersects(footprint_wgs84):
            scoped = footprint_wgs84 if prepared_mask.contains(footprint_wgs84) else _finish(footprint_wgs84.intersection(local_mask))
        display = scoped
        if district_scope:
            display = None
            if tier is not None and not footprint_wgs84.is_empty and prepared_land.intersects(footprint_wgs84):
                display = footprint_wgs84 if prepared_land.contains(footprint_wgs84) else _finish(footprint_wgs84.intersection(local_land))
        if display is not None and not display.is_empty:
            drawable_parts.append(display)
        tendency = compute_cell_direction_tendency_8b3(cell.as_dict(), points)
        cell_records.append({
            "cell_id": cell.scientific_cell_id or cell.grid_cell_id,
            "centroid": {"longitude": cell.centroid_lon, "latitude": cell.centroid_lat},
            "raw_c0_score": raw, "score_status": cell_score.status if cell_score else "MODEL_INPUT_INCOMPLETE",
            "bounded_score": bounded_score(raw) if cell_on_land else None,
            "band": display_band(bounded_score(raw)) if cell_on_land else None,
            "tier": tier, "tier_status": "TIERED" if tier is not None else (TIER_STATUS_OFF_LAND if not cell_on_land else "NOT_TIERED"),
            "on_land": cell_on_land, "domain_overlap_area_km2": cell.domain_overlap_area_km2,
            "geometry": mapping(shapely.set_precision(scoped, _COORD_PRECISION)) if scoped is not None and not scoped.is_empty else None,
            "display_geometry": mapping(shapely.set_precision(display, _COORD_PRECISION)) if display is not None and not display.is_empty else None,
            "direction": {"bearing_deg": tendency.bearing_deg, "directional_clarity": tendency.directional_clarity,
                          "direction_status": tendency.direction_status},
            "in_scope": mask.contains(Point(cell.centroid_lon, cell.centroid_lat)),
        })
    cell_records.sort(key=lambda c: c["cell_id"])

    zones = {}
    for tier in TIER_ORDER:
        geometry = _finish(
            unary_union(tier_parts[tier]).simplify(_SIMPLIFY_TOLERANCE_DEG, preserve_topology=True).intersection(mask)
        ) if tier_parts[tier] else None
        if geometry is not None:
            zones[tier] = geometry
    zone_features = [
        _feature(zones[tier], feature_id=f"zone:{tier}", properties={"tier": tier, "label": TIER_LABELS[tier], "semantics": ZONE_SEMANTICS,
                               "area_km2": round(geodesic_area_km2(zones[tier]), 3)})
        for tier in TIER_ORDER if tier in zones
    ]

    source_directions = []
    for source in sources:
        # The frozen 8B.3 resultant has no absolute-mass cutoff, so evaluated
        # at a source with no nearby neighbour it would turn one far-away
        # source into a clarity-1.0 bearing. The source-anchored tendency
        # therefore only uses eligible sources inside the frozen 25 km local
        # evaluation distance of that source (the validated C0 domain).
        local_points = [p for p in points
                        if _GEOD.inv(source.longitude, source.latitude, p.longitude, p.latitude)[2] / 1000.0 <= PRIMARY_LOCAL_EVALUATION_DISTANCE_KM]
        neighbours = sum(1 for p in local_points
                         if (p.latitude, p.longitude) != (source.latitude, source.longitude))
        tendency = compute_cell_direction_tendency_8b3(
            {"scientific_cell_id": source.source_id, "centroid_lat": source.latitude, "centroid_lon": source.longitude}, local_points)
        available = tendency.bearing_deg is not None
        source_directions.append({
            "source_id": source.source_id, "record_domain": source.record_domain,
            "coordinates": [source.longitude, source.latitude],
            "bearing_deg": tendency.bearing_deg, "directional_clarity": tendency.directional_clarity,
            "direction_status": DIRECTION_AVAILABLE if available else DIRECTION_INDETERMINATE,
            "method_direction_status": tendency.direction_status,
            "direction_input_source_count": neighbours,
            "direction_neighbourhood_km": PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
            "method": ("8B.3 evaluated at the source location from the other eligible sources within the 25 km local "
                       "evaluation distance (the source's own zero-distance term is excluded by the method)"),
            "semantics": CORRIDOR_SEMANTICS,
        })

    # Day-by-day paths (Trajectory), ONE PER CASE, see PATH_* above.
    land_prepared = prep(sri_lanka_land().buffer(PATH_COAST_TOLERANCE_DEG))
    source_paths = []
    no_path = {}  # source_id -> why it has no path
    for group in group_sources(sources):
        group_ids = sorted(m.source_id for m in group)
        for member in sorted(group, key=lambda m: m.source_id):
            lat0, lon0 = member.latitude, member.longitude
            wind_by_date = None
            if wind_lookup is not None:
                try:
                    wind_by_date = wind_lookup(lat0, lon0)
                except Exception:  # weather is optional context: never fails the timeline
                    wind_by_date = None
            trace = trace_source_path(lat0, lon0, points, horizon_days, land_prepared.contains, as_of=as_of,
                                      wind_by_date=wind_by_date) if horizon_days > 0 else None
            day1 = (trace["basis_by_day"][1] if trace else None) or {}
            origin_basis = {**day1, "confidence": day1.get("confidence", 0.0), "directional_share": day1.get("confidence", 0.0),
                            "cases_within_25km": day1.get("cases_within_25km", front_tendency(lat0, lon0, points)["cases_within_25km"])}
            wind_status = "OK" if wind_by_date else "UNAVAILABLE"
            if trace is None or len(trace["coords"]) < 2:
                no_path[member.source_id] = {"reason": trace["stop_reason"] if trace else PATH_STOP_HORIZON,
                                             "origin_basis": origin_basis, "group_source_ids": group_ids, "wind_status": wind_status}
                continue
            source_paths.append({"source_id": member.source_id, "member_source_ids": [member.source_id], "group_source_ids": group_ids,
                                 "origin": [lon0, lat0], "origin_basis": origin_basis, "wind_status": wind_status, **trace})

    districts = [scope.district] if scope.kind == "district" else [
        d for d in load_districts() if any(d.geometry.intersects(z) for z in zones.values())]
    district_summaries = _district_summaries(districts, zones, cell_records, sources)

    frames = []
    path_by_source = {path["source_id"]: path for path in source_paths}
    # New outbreaks where an existing outbreak's front first stands in the
    # vet's district (district view only, see POSSIBLE_* above).
    possible, handovers = (_district_arrivals(sources, source_paths, scope.district.geometry, horizon_days, as_of, points,
                                              land_prepared.contains, wind_lookup)
                           if scope.kind == "district" and horizon_days > 0 else ([], {}))
    handed_to = {p["triggered_by"][0]: p["id"] for p in possible}
    # Raster contributor index: the eligible sources, then the new outbreaks.
    source_index = {s.source_id: i for i, s in enumerate(sources)}
    source_index.update({p["id"]: len(sources) + k for k, p in enumerate(possible)})
    drawable_land = ScoredLand(unary_union(drawable_parts) if drawable_parts else None)
    for day, frame_date in frame_dates(as_of, horizon_days):
        reach = reach_for_day(day)
        frame = {"day": day, "date": frame_date.isoformat(), "horizon_status": horizon_status(day),
                 "active_source_ids": [s.source_id for s in sources], "reach": reach,
                 "reach_envelope": None, "reach_envelope_display": None, "reach_display": None, "reach_limited_risk_zones": _collection([]), "source_corridors": [], "source_paths": [],
                 "district_summaries": [],
                 "risk_field": {
                     # Days since the case's verification on this frame date (information only).
                     "kernels": [{**_source_kernel(s, path_by_source.get(s.source_id), day, handovers.get(s.source_id)), "age_days": source_age_days(s, frame_date)} for s in sources]
                                + [_possible_kernel(p, day) for p in possible if day >= p["seed_day"]],
                 },
                 "possible_new_case_ids": [p["id"] for p in possible if day >= p["seed_day"]]}
        frame["risk_field"]["raster"] = build_day_raster(frame["risk_field"]["kernels"], source_index, drawable_land)
        for path in source_paths:
            handover = handovers.get(path["source_id"])
            if handover is not None and day >= handover:
                # The front became a new outbreak: the path stops there.
                frame["source_paths"].append({**_frame_path_entry(path, handover, day), "handover_day": handover,
                                              "handed_over_to": handed_to[path["source_id"]]})
            else:
                frame["source_paths"].append(_frame_path_entry(path, day, day))
        for p in possible:
            if p["path"] is not None and day >= p["seed_day"]:
                frame["source_paths"].append({**_frame_path_entry(p["path"], day - p["seed_day"], day), "possible_new_case": True})
        if reach["nominal_reach_km"] is not None:
            radius = reach["nominal_reach_km"]
            discs = unary_union([_geodesic_disc(s.latitude, s.longitude, radius) for s in sources])
            envelope = _finish(discs.intersection(mask))
            frame["reach_envelope"] = mapping(envelope) if envelope is not None else None
            # Land-only outline for display (see `display_geometry` above).
            display_envelope = _finish(discs.intersection(sri_lanka_land())) if district_scope else envelope
            frame["reach_envelope_display"] = mapping(display_envelope) if display_envelope is not None else None
            # Direction-shaped display reach, land-clipped (never over the sea).
            on_path = {sid for path in source_paths for sid in path["member_source_ids"]}
            ribbons = [shape(r) for r in (_ribbon(path, day) for path in source_paths) if r]
            discs_without_path = [_reach_display_shape(s.latitude, s.longitude, day) for s in sources if s.source_id not in on_path]
            shaped = unary_union(ribbons + discs_without_path)
            reach_display = _finish(shaped.intersection(sri_lanka_land())) if not shaped.is_empty else None
            frame["reach_display"] = mapping(reach_display) if reach_display is not None else None
            reach_features = []
            reach_parts = []
            for tier in TIER_ORDER:
                if tier in zones and envelope is not None:
                    part = _finish(zones[tier].intersection(envelope))
                    if part is not None:
                        reach_parts.append((tier, part))
                        reach_features.append(_feature(part, feature_id=f"reach:d{day}:{tier}", properties={"tier": tier, "label": TIER_LABELS[tier], "day": day,
                                                              "semantics": REACH_ZONE_SEMANTICS,
                                                              "area_km2": round(geodesic_area_km2(part), 3)}))
            frame["reach_limited_risk_zones"] = _collection(reach_features)
            for direction in source_directions:
                if direction["bearing_deg"] is None:
                    continue
                # A geometric tendency is only defined from sources within the 25 km
                # local domain, so it is never drawn beyond it (no long-range arrows
                # implying spread); the day's reach itself is reported separately.
                corridor_km = min(radius, PRIMARY_LOCAL_EVALUATION_DISTANCE_KM)
                line = _corridor(direction["coordinates"][1], direction["coordinates"][0], direction["bearing_deg"], corridor_km)
                on_land = line.intersection(sri_lanka_land())  # never drawn out over the sea
                if on_land.is_empty:
                    continue
                frame["source_corridors"].append({
                    "corridor_id": f"corridor:d{day}:{direction['source_id']}",
                    "source_id": direction["source_id"], "bearing_deg": direction["bearing_deg"], "length_km": corridor_km,
                    "nominal_reach_km": radius, "length_capped_at_km": PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
                    "clipped_to": "SRI_LANKA_LAND",
                    "geometry": mapping(shapely.set_precision(on_land, _COORD_PRECISION)), "semantics": CORRIDOR_SEMANTICS,
                })
            frame["district_summaries"] = [
                {"district": d.name,
                 "area_within_reach_km2": round(geodesic_area_km2(envelope.intersection(d.geometry)), 3) if envelope is not None else 0.0,
                 # Only land the C0 model actually scored (reach-limited tier zones), never unscored land.
                 "scored_area_within_reach_km2": round(sum(geodesic_area_km2(part.intersection(d.geometry)) for _, part in reach_parts), 3),
                 "highest_tier_within_reach": next((t for t, part in reversed(reach_parts) if part.intersects(d.geometry)), None)}
                for d in districts
            ]
        frames.append(frame)

    return {
        **base, "status": STATUS_OK,
        "district_influence": _district_influence(scope, sources, frames, unary_union(drawable_parts) if drawable_parts else None) if district_scope else None,
        "tier_thresholds": thresholds, "cells": cell_records, "risk_zones": _collection(zone_features),
        "source_directions": source_directions, "district_summaries": district_summaries, "frames": frames,
        "source_paths": [{"source_id": p["source_id"], "member_source_ids": p["member_source_ids"], "group_source_ids": p["group_source_ids"], "origin": p["origin"],
                          "origin_basis": p["origin_basis"], "wind_status": p["wind_status"], "geometry": mapping(LineString(p["coords"])) if len(p["coords"]) > 1 else None,
                          "day_front_index": p["day_index"], "length_km": p["length_km"], "stop_reason": p["stop_reason"],
                          "step_km": PATH_STEP_KM, "semantics": PATH_SEMANTICS} for p in source_paths],
        # Cases with no individual path and why (the map shows their outbreak
        # group / cluster instead of inventing a direction).
        "sources_without_path": [{"source_id": sid, **info} for sid, info in sorted(no_path.items())],
        # Modelled possible new outbreaks in the vet's district (district
        # view), in raster contributor order after `sources`; never confirmed.
        "possible_new_cases": [{"id": p["id"], "farm_id": p["farm_id"], "latitude": p["focus"].latitude, "longitude": p["focus"].longitude,
                                "seed_day": p["seed_day"], "seed_date": (as_of + timedelta(days=p["seed_day"])).isoformat(),
                                "seed_score": p["seed_score"], "generation": p["generation"], "arrival": p["arrival"],
                                "triggered_by": p["triggered_by"], "has_path": p["path"] is not None, "semantics": POSSIBLE_SEMANTICS} for p in possible],
        "scientific_domain_id": domain.scientific_evaluation_domain_id,
    }


def _frame_path_entry(path: dict, local_day: int, frame_day: int) -> dict:
    """One path on one frame. `local_day` counts from the path's own start
    (a real case: the as-of date; a possible new case: its seed day)."""
    upto = path["day_index"][local_day]
    coords = path["coords"]
    reach = reach_for_day(local_day)
    return {
        "path_id": f"path:d{frame_day}:{path['source_id']}", "source_id": path["source_id"], "day": frame_day,
        "geometry": mapping(LineString(coords[: upto + 1])) if upto >= 1 else None,
        "front": list(coords[upto]), "front_bearing_deg": _front_bearing(coords, upto),
        "length_km": round(min(FROZEN_S0_RATE_KM_DAY_9C * local_day, path["length_km"]), 3) if upto >= 1 else 0.0,
        "member_source_ids": path["member_source_ids"], "group_source_ids": path["group_source_ids"], "heading_basis": path["basis_by_day"][local_day],
        "origin_basis": path["origin_basis"], "reach_interval_km": reach["interval_km"], "plume": _ribbon(path, local_day),
        "distance_check": _distance_check(path, local_day, reach),
        "stop_reason": path["stop_reason"] if upto == len(coords) - 1 and local_day > 0 else None,
        "semantics": PATH_SEMANTICS,
    }


# New outbreaks in the vet's district (My Area Future Impact, district view
# only). The front of an existing outbreak's path establishes a POSSIBLE new
# outbreak on the first day it has moved and stands inside the district:
# for an outbreak already in the district, where it first moves to (Day 1);
# for one outside, where it arrives. From that day the new outbreak spreads
# with the same path and kernel model as a real case -- its kernel weighted
# by the combined score at that spot that day (an uncertain outbreak counts
# less than a verified one) -- and the existing outbreak's path and kernel
# spine stop there: its front is handed over, so one spread is never drawn or
# counted twice. A modelled scenario for planning, never a confirmed case, a
# prediction of infection or a new eligible source.
POSSIBLE_ID_PREFIX = "POSSIBLE:"
POSSIBLE_SEMANTICS = "MODELED_POSSIBLE_NEW_OUTBREAK_WHERE_AN_EXISTING_OUTBREAK_FRONT_FIRST_STANDS_IN_THE_DISTRICT_NOT_A_CONFIRMED_CASE"
ARRIVAL_LOCAL = "FIRST_MOVE_INSIDE_DISTRICT"
ARRIVAL_EXTERNAL = "ARRIVAL_FROM_OUTSIDE_THE_DISTRICT"


class _Focus:
    """A real case or a possible new outbreak as a kernel/path source."""

    def __init__(self, source_id, latitude, longitude):
        self.source_id, self.latitude, self.longitude = source_id, latitude, longitude


def handover_day(path: dict, district_contains, horizon_days: int) -> int | None:
    """First day the path's front has moved and stands inside the district."""
    for day in range(1, min(horizon_days, len(path["day_index"]) - 1) + 1):
        upto = path["day_index"][day]
        if upto >= 1 and district_contains(Point(*path["coords"][upto])):
            return day
    return None


def _source_kernel(source, path: dict | None, day: int, handover: int | None = None) -> dict:
    """Day-d kernel of an eligible case; after its front is handed over to a
    new outbreak the spine stops at the hand-over point (reach and the
    isotropic part keep their day-d values)."""
    kernel = _risk_kernel(source, path, day)
    if handover is not None and path is not None and day > handover:
        tau = kernel["fringe_km"]
        kernel["spine"] = [[round(lon, 6), round(lat, 6), 0.0, round(tau, 4)] for lon, lat in path["coords"][: path["day_index"][handover] + 1]]
        kernel["handed_over_at_day"] = handover
    return kernel


def _possible_kernel(possible: dict, day: int) -> dict:
    kernel = _risk_kernel(possible["focus"], possible["path"], day - possible["seed_day"])
    return {**kernel, "weight": possible["seed_score"], "age_days": None, "possible_new_case": True}


def _district_arrivals(sources: list, source_paths: list, district_geometry, horizon_days: int, as_of: date, points: list,
                       land_contains, wind_lookup) -> tuple[list[dict], dict]:
    """New outbreaks (see POSSIBLE_* above) and, per eligible source id, the
    day its front was handed over."""
    district = prep(district_geometry)
    by_id = {s.source_id: s for s in sources}
    path_by_source = {path["source_id"]: path for path in source_paths}
    candidates = sorted(((d, path) for path in source_paths if (d := handover_day(path, district.contains, horizon_days)) is not None),
                        key=lambda item: (item[0], item[1]["source_id"]))
    arrivals: list[dict] = []
    handovers: dict[str, int] = {}
    focus_points = list(points)
    for day, path in candidates:
        parent = by_id[path["source_id"]]
        upto = path["day_index"][day]
        lon, lat = path["coords"][upto]
        kernels = [_source_kernel(s, path_by_source.get(s.source_id), day, handovers.get(s.source_id)) for s in sources]
        kernels += [{**_risk_kernel(a["focus"], a["path"], day - a["seed_day"]), "weight": a["seed_score"]} for a in arrivals if a["seed_day"] <= day]
        score = max(RISK_VISIBLE_MIN_SCORE, 1.0 - math.exp(-risk_field_value(lon, lat, kernels)))
        focus = _Focus(f"{POSSIBLE_ID_PREFIX}{parent.source_id}", lat, lon)
        wind = None
        if wind_lookup is not None:
            try:
                wind = wind_lookup(lat, lon)
            except Exception:  # weather is optional context
                wind = None
        trace = trace_source_path(lat, lon, focus_points, horizon_days - day, land_contains, as_of=as_of + timedelta(days=day),
                                  wind_by_date=wind, initial_bearing=_front_bearing(path["coords"], upto))
        day1 = (trace["basis_by_day"][1] if len(trace["basis_by_day"]) > 1 else None) or {}
        new_path = None
        if len(trace["coords"]) >= 2:
            new_path = {"source_id": focus.source_id, "member_source_ids": [focus.source_id], "group_source_ids": [focus.source_id],
                        "origin": [lon, lat], "origin_basis": {**day1, "confidence": day1.get("confidence", 0.0),
                        "directional_share": day1.get("confidence", 0.0), "cases_within_25km": day1.get("cases_within_25km")}, **trace}
        inside = district.contains(Point(parent.longitude, parent.latitude))
        arrivals.append({"id": focus.source_id, "focus": focus, "path": new_path, "seed_day": day, "seed_score": round(score, 4),
                         "generation": 1, "farm_id": None, "triggered_by": [parent.source_id],
                         "arrival": ARRIVAL_LOCAL if inside else ARRIVAL_EXTERNAL})
        handovers[parent.source_id] = day
        focus_points.append(EligibleSourcePoint(source_id=focus.source_id, latitude=lat, longitude=lon))
    return arrivals, handovers


DISTRICT_INFLUENCE_SEMANTICS = "SOURCE_SPECIFIC_MODELED_INFLUENCE_INSIDE_DISTRICT_NOT_A_CONFIRMED_CASE_OR_NEW_SOURCE"


def _district_influence(scope: TimelineScope, sources: list[TimelineSource], frames: list[dict], drawable=None) -> dict:
    """Per source, when its OWN modeled risk reaches the vet's district.

    first_influence_day: the first day the source's own day-d risk kernel
      (frames[d].risk_field.kernels) gives a visible score (>= the map's
      threshold) on at least one district land cell -- the same geometry the
      Risk Zones map draws for that source. Before it, the source has no
      modeled influence inside the district and is not shown as influencing.
    first_nominal_reach_day: the first day the 9C nominal reach disc
      (S0 x day) touches the district polygon -- distance only, which can be
      earlier or later than the influence (direction and uncertainty shape it).
    No case, source or infection is created: the source set is the as-of set.
    """
    district = scope.district.geometry
    # Only district land the Risk Zones map can colour (scored land), so the
    # reported influence is exactly what the map shows inside the district.
    cells = district_cells(district, drawable if drawable is not None else sri_lanka_land())
    entries = []
    for source in sources:
        local = shapely_transform(_wgs84_to_aeqd(source.latitude, source.longitude).transform, district)
        distance_km = local.distance(Point(0.0, 0.0)) / 1000.0
        inside = distance_km == 0.0
        by_day = []
        for frame in frames:
            kernel = next((k for k in frame["risk_field"]["kernels"] if k["source_id"] == source.source_id), None)
            influence = source_district_influence(kernel, cells) if kernel else {"area_km2": 0.0, "max_score": None}
            by_day.append({"day": frame["day"], "date": frame["date"], **influence})
        first_reach = 0 if inside else next((f["day"] for f in frames if f["day"] >= 1 and FROZEN_S0_RATE_KM_DAY_9C * f["day"] >= distance_km), None)
        entries.append({
            "source_id": source.source_id, "inside_district": inside, "distance_to_district_km": round(distance_km, 3),
            "first_influence_day": next((d["day"] for d in by_day if d["area_km2"] > 0), None),
            "first_nominal_reach_day": first_reach, "by_day": by_day,
        })
    return {"district": scope.district.name, "visible_score_threshold": RISK_VISIBLE_MIN_SCORE,
            "district_land_cells": int(len(cells[0])), "semantics": DISTRICT_INFLUENCE_SEMANTICS, "sources": entries}


def _district_summaries(districts: list[District], zones: dict, cell_records: list[dict], sources: list[TimelineSource]) -> list[dict]:
    summaries = []
    for district in districts:
        in_district = [c for c in cell_records
                       if c["raw_c0_score"] is not None and district.geometry.contains(Point(c["centroid"]["longitude"], c["centroid"]["latitude"]))]
        top = max(in_district, key=lambda c: c["raw_c0_score"], default=None)
        tier_area = {tier: round(geodesic_area_km2(zones[tier].intersection(district.geometry)), 3) if tier in zones else 0.0
                     for tier in TIER_ORDER}
        summaries.append({
            "district": district.name,
            "district_area_km2": round(geodesic_area_km2(district.geometry), 3),
            "tier_area_km2": tier_area,
            "scored_area_km2": round(sum(tier_area.values()), 3),
            "max_relative_score": top["raw_c0_score"] if top else None,
            "max_tier": top["tier"] if top else None,
            "n_cells_with_centroid_in_district": len(in_district),
            "n_sources_in_district": sum(1 for s in sources if district.geometry.contains(Point(s.longitude, s.latitude))),
            "semantics": "DISTRICT_SUMMARY_OF_RELATIVE_SPATIAL_SCORE_NOT_INCIDENCE",
        })
    return summaries
