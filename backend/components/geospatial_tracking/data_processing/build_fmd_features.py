"""FMD-04: environmental/host-context feature-enrichment layer for the
frozen FMD-03D canonical event corpus.

**Architectural note (why this does NOT call `services/features/assembler.py`):**
That module's `assemble_feature_snapshot` is built around LSD's hazard-model
workflow — a `ForecastOrigin` + a spatial GRID of `GridCell`s over an AOI,
with per-cell host-density/landcover/hydrology and one AOI-center weather
call. FMD-04 is explicitly forbidden from building forecast origins, grids,
or anything tied to a future forecasting/clustering checkpoint (see
FMD-04's "IMPORTANT: DO NOT START THESE YET" list — no ST-DBSCAN, no risk
zones, no forecast-origin semantics). What FMD-04 needs instead is a POINT-
level feature attached directly to each canonical event's own
`(latitude, longitude, onset_date)` — so this module calls the underlying,
already-disease-agnostic extraction adapters
(`services/geospatial/weather/era5.py`, `.../elevation/terrain_tiles.py`,
`.../host_density/fao_glw.py`, `.../landcover/esa_worldcover.py`,
`.../hydrology/hydrosheds.py`) DIRECTLY, one event at a time, never
through the grid/forecast-origin machinery. Every adapter call below is
the SAME shared, unmodified code LSD's feature layer uses — only the
orchestration (which events, which windows, how results are assembled and
classified) is FMD-specific, mirroring the `build_fmd_canonical.py`
precedent from FMD-03C/D.

**Never mutates the frozen FMD-03D canonical corpus.** Reads
`fmd_canonical_outbreaks_conservative.csv` read-only; every output here
lives in a separate `local_data/processed/fmd/features/` directory, joined
back only by `fmd_canonical_event_id`.

**Scale note.** The real corpus has 9,526 canonical events (9,311
modelling-eligible). A full-corpus run makes ~4 live Open-Meteo HTTP
requests per event for weather alone (~38,000+ requests) plus one ESA
WorldCover windowed S3 read per event — infeasible to run unattended
within a single interactive session without risking external rate-limits
or a multi-hour partial run. `run()` therefore accepts an explicit `events`
list (the caller decides scope) rather than always defaulting to the full
corpus; see `FMD_FEATURE_AUDIT.md` for the real, executed validation scope
this checkpoint used and the exact reproducible command for a full-corpus
run.
"""

from __future__ import annotations

import csv
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..services.geospatial.elevation.terrain_tiles import extract_elevation
from ..services.geospatial.feature_result import FeatureResult, FeatureStatus, assert_not_demo_for_scientific_use
from ..services.geospatial.host_density.fao_glw import GLW_SPECIES, extract_density
from ..services.geospatial.hydrology.hydrosheds import distance_to_nearest_river_km
from ..services.geospatial.landcover.esa_worldcover import WORLDCOVER_CLASSES, extract_landcover_fractions
from ..services.geospatial.weather.base import T0Precision
from ..services.geospatial.weather.era5 import build_pre_t0_weather_summary
from ..services.features.cache import FileWeatherCache
from .fmd_feature_status import (
    EXTRACTION_COMPLETE,
    EXTRACTION_NOT_RUN,
    classify_feature_availability,
    not_attempted,
    outside_coverage,
)

# ---------------------------------------------------------------------------
# Fixed, documented, UNFROZEN_DEVELOPMENT_PARAMETER extraction config —
# never tuned against any outcome (no outcome/model exists at this
# checkpoint to tune against). Mirrors config.py's own
# UNFROZEN_DEVELOPMENT_PARAMETER convention.
# ---------------------------------------------------------------------------

WEATHER_WINDOWS_HOURS: dict[str, float] = {
    "event_day": 24.0,
    "window_3day": 72.0,
    "window_7day": 168.0,
    "window_14day": 336.0,
}
"""Candidate retrospective windows only (FMD-04 Step 4) — none is chosen
as "the" feature here; window selection against outcome performance is
explicitly out of scope for this checkpoint."""

WEATHER_VARIABLES: tuple[str, ...] = (
    "mean_temperature_2m",
    "mean_relative_humidity_2m",
    "precipitation_accumulation",
    "mean_u10",
    "mean_v10",
    "mean_wind_speed",
    "vector_resultant_speed",
    "directional_persistence",
)

HOST_DENSITY_SPECIES_AVAILABLE: tuple[str, ...] = tuple(sorted(GLW_SPECIES))  # ("buffalo", "cattle") today
HOST_DENSITY_SPECIES_UNAVAILABLE: tuple[str, ...] = ("swine", "sheep", "goat")
"""FMD is multi-host; GLW4 only has cattle/buffalo wired in
(`fao_glw.GLW_SPECIES`). These three get `FEATURE_NOT_AVAILABLE` — never a
fabricated density, never silently folded into a fake "total"."""

HOST_DENSITY_HALF_EXTENT_KM = 10.0
"""Matched to GLW4's own ~10km native pixel resolution (see
fao_glw.py's documented sensitivity to arbitrary half_extent_km choice) —
a fixed, single value applied identically to every event, never varied
per-event or tuned."""

LANDCOVER_HALF_EXTENT_KM = 10.0
LANDCOVER_DEFAULT_YEAR = "2021"

HYDROLOGY_SEARCH_RADIUS_KM = 25.0

ELEVATION_ZOOM = 12

FMD_HYDROLOGY_ASIA_BBOX = (25.0, -15.0, 180.0, 60.0)  # (west, south, east, north)
"""A documented, deliberately generous WGS84 bounding-box APPROXIMATION of
HydroRIVERS' 'as' (Asia) continental coverage — not an exact country/
continent polygon test. Used only to avoid a guaranteed-empty shapefile
read for an event already known to be far outside coverage (e.g. South
Africa, Algeria — the FMD corpus's two largest non-Asian contributors);
a genuinely borderline coordinate still gets a real adapter call whenever
it falls inside this box, and `distance_to_nearest_river_km`'s own
MISSING/BLOCKED result remains authoritative for anything this box lets
through. Never used to justify a fabricated distance."""

_EVENT_DATE_FIELD_PRIORITY = ("outbreak_start_date", "onset_date", "event_start_date", "confirmation_date")
"""Mirrors `data_processing/dedup.best_match_date`'s own fallback
hierarchy exactly (re-declared, not imported, since that name is a
module-private helper in dedup.py) — the same epidemiological event-date
semantics FMD-03D already froze, never re-derived differently here."""


@dataclass(frozen=True)
class FmdFeatureExtractionConfig:
    weather_windows_hours: dict[str, float] = field(default_factory=lambda: dict(WEATHER_WINDOWS_HOURS))
    host_density_half_extent_km: float = HOST_DENSITY_HALF_EXTENT_KM
    landcover_half_extent_km: float = LANDCOVER_HALF_EXTENT_KM
    landcover_default_year: str = LANDCOVER_DEFAULT_YEAR
    hydrology_search_radius_km: float = HYDROLOGY_SEARCH_RADIUS_KM
    elevation_zoom: int = ELEVATION_ZOOM


@dataclass(frozen=True)
class FmdCanonicalEventRef:
    fmd_canonical_event_id: str
    source_record_id: str
    country: str | None
    event_date: str | None
    latitude: float | None
    longitude: float | None
    modelling_eligible: bool


def _to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _event_date(row: dict) -> str | None:
    for field_name in _EVENT_DATE_FIELD_PRIORITY:
        value = row.get(field_name)
        if value:
            return value
    return None


def load_fmd_canonical_events(canonical_csv_path: str | Path) -> list[FmdCanonicalEventRef]:
    """Read-only load of the frozen FMD-03D canonical corpus — never
    writes back, never mutates the source file. Every row (all diagnosis
    statuses) is loadable; `modelling_eligible` is carried through so
    callers/coverage reports can slice by the confirmed-eligible subset
    without a second file read."""
    path = Path(canonical_csv_path)
    refs: list[FmdCanonicalEventRef] = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            refs.append(
                FmdCanonicalEventRef(
                    fmd_canonical_event_id=row["fmd_canonical_event_id"],
                    source_record_id=row["source_record_id"],
                    country=row.get("country") or None,
                    event_date=_event_date(row),
                    latitude=_to_float(row.get("latitude")),
                    longitude=_to_float(row.get("longitude")),
                    modelling_eligible=row.get("modelling_eligible") == "True",
                )
            )
    return refs


def _event_year(event_date: str | None) -> str | None:
    if not event_date or len(event_date) < 4:
        return None
    return event_date[:4]


def _in_hydrology_asia_bbox(lat: float, lon: float) -> bool:
    west, south, east, north = FMD_HYDROLOGY_ASIA_BBOX
    return west <= lon <= east and south <= lat <= north


# ---------------------------------------------------------------------------
# Per-feature-family extraction — each returns a list of (row-fragment,
# provenance-fragment) pairs. `row-fragment`/`provenance-fragment` are
# plain dicts merged into the wide feature-table row / long provenance
# table respectively, keyed by a stable `feature_name`.
# ---------------------------------------------------------------------------


def _provenance_row(event_id: str, feature_name: str, availability: str, result: FeatureResult | None, *, extra_notes: str = "") -> dict:
    if result is None:
        return {
            "fmd_canonical_event_id": event_id,
            "feature_name": feature_name,
            "value": "",
            "units": "",
            "availability_status": availability,
            "dataset_name": "",
            "dataset_version": "",
            "reference_time": "",
            "retrieved_at": "",
            "source_resolution": "",
            "source_crs": "",
            "analysis_method": "",
            "quality_notes": extra_notes,
        }
    return {
        "fmd_canonical_event_id": event_id,
        "feature_name": feature_name,
        "value": result.value if result.value is not None else "",
        "units": result.units or "",
        "availability_status": availability,
        "dataset_name": result.dataset_name or "",
        "dataset_version": result.dataset_version or "",
        "reference_time": result.reference_time or "",
        "retrieved_at": result.retrieved_at or "",
        "source_resolution": result.source_resolution or "",
        "source_crs": result.source_crs or "",
        "analysis_method": result.analysis_method or "",
        "quality_notes": (result.quality_notes or "") + (f"; {extra_notes}" if extra_notes else ""),
    }


def extract_weather_for_event(
    event: FmdCanonicalEventRef, config: FmdFeatureExtractionConfig, cache: FileWeatherCache,
    *, precomputed_weather_windows: dict[str, tuple] | None = None,
) -> tuple[dict, list[dict]]:
    """`precomputed_weather_windows`: OPTIONAL, additive-only seam
    (Checkpoint FMD-07A-R2B2-R1 Section 4) -- `None` (every existing
    caller) reproduces the exact original behavior byte-for-byte, one
    live/cached `build_pre_t0_weather_summary` call per window. When a
    caller (`fmd_model_development_r2b2.py`'s consolidated-request path)
    has already derived a window's `(PreT0WeatherWindow, list[FeatureResult])`
    from ONE real superset payload via era5's own
    `summarize_hourly_payload_for_window` -- the SAME pure equations this
    function's own per-window call ultimately uses -- that precomputed
    result is used directly instead of a redundant live/cached fetch. Any
    window NOT present in `precomputed_weather_windows` (e.g. the
    consolidated fetch failed for this source) transparently falls back
    to the unmodified live/cached call, so a partial precomputed dict is
    always safe."""
    row: dict = {}
    prov: list[dict] = []
    if event.latitude is None or event.longitude is None or not event.event_date:
        for window_name in config.weather_windows_hours:
            for var in WEATHER_VARIABLES:
                feature_name = f"weather_{window_name}_{var}"
                row[f"{feature_name}_value"] = ""
                row[f"{feature_name}_status"] = not_attempted("missing coordinate/date")
                prov.append(_provenance_row(event.fmd_canonical_event_id, feature_name, not_attempted(""), None, extra_notes="event missing latitude/longitude/event_date"))
        return row, prov

    for window_name, lookback_hours in config.weather_windows_hours.items():
        if precomputed_weather_windows is not None and window_name in precomputed_weather_windows:
            _window, results = precomputed_weather_windows[window_name]
        else:
            _window, results = build_pre_t0_weather_summary(
                latitude=event.latitude,
                longitude=event.longitude,
                t0=event.event_date,
                t0_precision=T0Precision.DATE_ONLY.value,
                lookback_hours=lookback_hours,
                cache=cache,
            )
        assert_not_demo_for_scientific_use(results)
        by_name = {r.feature_name: r for r in results}
        for var in WEATHER_VARIABLES:
            feature_name = f"weather_{window_name}_{var}"
            result = by_name.get(var)
            if result is None:
                row[f"{feature_name}_value"] = ""
                row[f"{feature_name}_status"] = not_attempted("variable not returned by adapter")
                prov.append(_provenance_row(event.fmd_canonical_event_id, feature_name, not_attempted(""), None, extra_notes="variable absent from adapter result set"))
                continue
            availability = classify_feature_availability(result)
            row[f"{feature_name}_value"] = result.value if result.value is not None else ""
            row[f"{feature_name}_status"] = availability
            prov.append(_provenance_row(event.fmd_canonical_event_id, feature_name, availability, result))
    return row, prov


def extract_elevation_for_event(event: FmdCanonicalEventRef, config: FmdFeatureExtractionConfig) -> tuple[dict, list[dict]]:
    if event.latitude is None or event.longitude is None:
        return (
            {"elevation_m_value": "", "elevation_m_status": not_attempted("missing coordinate")},
            [_provenance_row(event.fmd_canonical_event_id, "elevation_m", not_attempted(""), None, extra_notes="missing coordinate")],
        )
    result = extract_elevation(latitude=event.latitude, longitude=event.longitude, zoom=config.elevation_zoom)
    assert_not_demo_for_scientific_use([result])
    availability = classify_feature_availability(result)
    row = {"elevation_m_value": result.value if result.value is not None else "", "elevation_m_status": availability}
    return row, [_provenance_row(event.fmd_canonical_event_id, "elevation_m", availability, result)]


def extract_host_density_for_event(event: FmdCanonicalEventRef, config: FmdFeatureExtractionConfig) -> tuple[dict, list[dict]]:
    row: dict = {}
    prov: list[dict] = []

    for species in HOST_DENSITY_SPECIES_AVAILABLE:
        feature_name = f"host_density_{species}"
        if event.latitude is None or event.longitude is None:
            row[f"{feature_name}_value"] = ""
            row[f"{feature_name}_status"] = not_attempted("missing coordinate")
            prov.append(_provenance_row(event.fmd_canonical_event_id, feature_name, not_attempted(""), None, extra_notes="missing coordinate"))
            continue
        result = extract_density(
            center_lat=event.latitude,
            center_lon=event.longitude,
            half_extent_km=config.host_density_half_extent_km,
            species=species,
        )
        assert_not_demo_for_scientific_use([result])
        availability = classify_feature_availability(result)
        row[f"{feature_name}_value"] = result.value if result.value is not None else ""
        row[f"{feature_name}_status"] = availability
        prov.append(_provenance_row(event.fmd_canonical_event_id, feature_name, availability, result))

    for species in HOST_DENSITY_SPECIES_UNAVAILABLE:
        feature_name = f"host_density_{species}"
        row[f"{feature_name}_value"] = ""
        row[f"{feature_name}_status"] = not_attempted("no validated GLW4 adapter for this species")
        prov.append(
            _provenance_row(
                event.fmd_canonical_event_id, feature_name, not_attempted(""), None,
                extra_notes="no validated density adapter exists for this species (see fmd_feature_registry.py)",
            )
        )

    # Deliberately NO "total_livestock_density" column: composing one from
    # only 2 of 6 FMD-susceptible species (cattle, buffalo) would silently
    # understate host exposure wherever swine/sheep/goat dominate — per
    # FMD-04 Step 2's explicit instruction not to collapse species without
    # preserving per-species information, no such aggregate is fabricated.
    return row, prov


def extract_landcover_for_event(event: FmdCanonicalEventRef, config: FmdFeatureExtractionConfig) -> tuple[dict, list[dict]]:
    row: dict = {}
    prov: list[dict] = []
    class_names = sorted(WORLDCOVER_CLASSES.values())

    if event.latitude is None or event.longitude is None:
        for name in class_names:
            feature_name = f"landcover_{name}_fraction"
            row[f"{feature_name}_value"] = ""
            row[f"{feature_name}_status"] = not_attempted("missing coordinate")
            prov.append(_provenance_row(event.fmd_canonical_event_id, feature_name, not_attempted(""), None, extra_notes="missing coordinate"))
        return row, prov

    target_year = _event_year(event.event_date)
    results = extract_landcover_fractions(
        center_lat=event.latitude,
        center_lon=event.longitude,
        half_extent_km=config.landcover_half_extent_km,
        worldcover_year=config.landcover_default_year,
        target_year=target_year,
    )
    assert_not_demo_for_scientific_use(results)

    if len(results) == 1 and results[0].status != FeatureStatus.REAL.value:
        # whole-AOI failure/nodata (BLOCKED or the single "landcover_all_classes" MISSING result)
        sole = results[0]
        availability = classify_feature_availability(sole)
        for name in class_names:
            feature_name = f"landcover_{name}_fraction"
            row[f"{feature_name}_value"] = ""
            row[f"{feature_name}_status"] = availability
            prov.append(_provenance_row(event.fmd_canonical_event_id, feature_name, availability, sole))
        return row, prov

    present = {r.feature_name: r for r in results}  # keys: "landcover_<class>_fraction"
    for name in class_names:
        feature_name = f"landcover_{name}_fraction"
        result = present.get(feature_name)
        if result is not None:
            availability = classify_feature_availability(result)
            row[f"{feature_name}_value"] = result.value
            row[f"{feature_name}_status"] = availability
            prov.append(_provenance_row(event.fmd_canonical_event_id, feature_name, availability, result))
        else:
            # The adapter's own compute_class_fractions enumerates every
            # official class and includes it only when count>0 — absence
            # here means 0 valid pixels of this class in an AOI window
            # whose extraction otherwise succeeded. Making that implicit
            # zero explicit (never for a class the adapter didn't get a
            # chance to evaluate at all, e.g. a BLOCKED/MISSING whole-AOI
            # case, handled above before this branch).
            row[f"{feature_name}_value"] = 0.0
            row[f"{feature_name}_status"] = "SOURCE_VALUE_AVAILABLE"
            prov.append(
                _provenance_row(
                    event.fmd_canonical_event_id, feature_name, "SOURCE_VALUE_AVAILABLE", None,
                    extra_notes="DERIVED_ZERO_FRACTION: class absent from adapter's per-class REAL results = 0 valid pixels of this class in the AOI window (not an independently-returned adapter value)",
                )
            )
    return row, prov


def extract_hydrology_for_event(event: FmdCanonicalEventRef, config: FmdFeatureExtractionConfig) -> tuple[dict, list[dict]]:
    feature_name = "distance_to_nearest_river_km"
    if event.latitude is None or event.longitude is None:
        return (
            {f"{feature_name}_value": "", f"{feature_name}_status": not_attempted("missing coordinate")},
            [_provenance_row(event.fmd_canonical_event_id, feature_name, not_attempted(""), None, extra_notes="missing coordinate")],
        )
    if not _in_hydrology_asia_bbox(event.latitude, event.longitude):
        availability = outside_coverage("outside FMD_HYDROLOGY_ASIA_BBOX")
        return (
            {f"{feature_name}_value": "", f"{feature_name}_status": availability},
            [
                _provenance_row(
                    event.fmd_canonical_event_id, feature_name, availability, None,
                    extra_notes="event coordinates fall outside the documented HydroRIVERS 'as'-region bounding-box approximation; adapter not called",
                )
            ],
        )
    result = distance_to_nearest_river_km(
        center_lat=event.latitude,
        center_lon=event.longitude,
        search_radius_km=config.hydrology_search_radius_km,
        region="as",
    )
    assert_not_demo_for_scientific_use([result])
    availability = classify_feature_availability(result)
    row = {f"{feature_name}_value": result.value if result.value is not None else "", f"{feature_name}_status": availability}
    return row, [_provenance_row(event.fmd_canonical_event_id, feature_name, availability, result)]


CORE_EVENT_COLUMNS = ["fmd_canonical_event_id", "source_record_id", "country", "event_date", "latitude", "longitude", "modelling_eligible"]

PROVENANCE_COLUMNS = [
    "fmd_canonical_event_id",
    "feature_name",
    "value",
    "units",
    "availability_status",
    "dataset_name",
    "dataset_version",
    "reference_time",
    "retrieved_at",
    "source_resolution",
    "source_crs",
    "analysis_method",
    "quality_notes",
]


def build_event_feature_row(
    event: FmdCanonicalEventRef, config: FmdFeatureExtractionConfig, weather_cache: FileWeatherCache,
    *, precomputed_weather_windows: dict[str, tuple] | None = None,
) -> tuple[dict, list[dict]]:
    """`precomputed_weather_windows`: see `extract_weather_for_event` --
    optional, additive-only, `None` for every pre-existing caller."""
    row: dict = {
        "fmd_canonical_event_id": event.fmd_canonical_event_id,
        "source_record_id": event.source_record_id,
        "country": event.country or "",
        "event_date": event.event_date or "",
        "latitude": event.latitude if event.latitude is not None else "",
        "longitude": event.longitude if event.longitude is not None else "",
        "modelling_eligible": event.modelling_eligible,
    }
    prov: list[dict] = []

    for extractor in (
        lambda: extract_weather_for_event(event, config, weather_cache, precomputed_weather_windows=precomputed_weather_windows),
        lambda: extract_elevation_for_event(event, config),
        lambda: extract_host_density_for_event(event, config),
        lambda: extract_landcover_for_event(event, config),
        lambda: extract_hydrology_for_event(event, config),
    ):
        sub_row, sub_prov = extractor()
        row.update(sub_row)
        prov.extend(sub_prov)

    return row, prov


def feature_value_columns(row: dict) -> list[str]:
    return [c for c in row if c.endswith("_value") and c not in ("fmd_canonical_event_id",)]


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run(
    events: list[FmdCanonicalEventRef],
    *,
    out_dir: str | Path,
    weather_cache_dir: str | Path,
    config: FmdFeatureExtractionConfig | None = None,
) -> dict:
    """Builds the feature table + provenance table for exactly the
    `events` passed in — caller controls scope (see module docstring
    "Scale note"). Never reads/writes the canonical corpus CSV itself."""
    config = config or FmdFeatureExtractionConfig()
    out_path = Path(out_dir)
    cache = FileWeatherCache(Path(weather_cache_dir))

    feature_rows: list[dict] = []
    provenance_rows: list[dict] = []
    for event in events:
        row, prov = build_event_feature_row(event, config, cache)
        feature_rows.append(row)
        provenance_rows.extend(prov)

    fieldnames = list(CORE_EVENT_COLUMNS)
    if feature_rows:
        for key in feature_rows[0]:
            if key not in fieldnames:
                fieldnames.append(key)

    _write_csv(out_path / "fmd_feature_table.csv", feature_rows, fieldnames)
    _write_csv(out_path / "fmd_feature_provenance.csv", provenance_rows, PROVENANCE_COLUMNS)

    return {
        "events_requested": len(events),
        "events_enriched": len(feature_rows),
        "feature_table_path": str(out_path / "fmd_feature_table.csv"),
        "provenance_path": str(out_path / "fmd_feature_provenance.csv"),
        "feature_rows": feature_rows,
        "provenance_rows": provenance_rows,
    }


# ---------------------------------------------------------------------------
# FMD-04 Step 8: per-feature coverage/quality audit
# ---------------------------------------------------------------------------


def _plausibility_flag(feature_name: str, value: float) -> str | None:
    """Physical/source-defined bound checks (Step 8 examples) — flags
    only, never deletes/corrects a value."""
    if "relative_humidity" in feature_name and not (0.0 <= value <= 100.0):
        return f"relative humidity {value} outside physical bounds [0,100]%"
    if "precipitation_accumulation" in feature_name and value < 0.0:
        return f"precipitation_accumulation {value} is negative (source-invalid)"
    if feature_name.startswith("host_density_") and value < 0.0:
        return f"host density {value} is negative (source-invalid)"
    if feature_name.endswith("_fraction") and not (-1e-9 <= value <= 1.0 + 1e-9):
        return f"landcover fraction {value} outside [0,1]"
    if feature_name == "elevation_m" and not (-500.0 <= value <= 9000.0):
        return f"elevation {value}m outside plausible terrestrial bounds [-500,9000]m (Dead Sea..Everest)"
    if "wind_speed" in feature_name and value < 0.0:
        return f"wind speed {value} m/s is negative (source-invalid)"
    if feature_name == "distance_to_nearest_river_km" and value < 0.0:
        return f"distance_to_nearest_river_km {value} is negative (source-invalid)"
    return None


def compute_feature_coverage_report(provenance_rows: list[dict], events_requested: int) -> list[dict]:
    by_feature: dict[str, list[dict]] = {}
    for row in provenance_rows:
        by_feature.setdefault(row["feature_name"], []).append(row)

    report: list[dict] = []
    for feature_name, rows in sorted(by_feature.items()):
        numeric_values: list[float] = []
        invalid_notes: list[str] = []
        status_counts: dict[str, int] = {}
        for row in rows:
            status = row["availability_status"]
            status_counts[status] = status_counts.get(status, 0) + 1
            if status == "SOURCE_VALUE_AVAILABLE" and row["value"] != "":
                try:
                    v = float(row["value"])
                except (TypeError, ValueError):
                    continue
                numeric_values.append(v)
                flag = _plausibility_flag(feature_name, v)
                if flag:
                    invalid_notes.append(flag)

        n_available = status_counts.get("SOURCE_VALUE_AVAILABLE", 0)
        n_requested = len(rows)
        report.append(
            {
                "feature_name": feature_name,
                "events_requested": n_requested,
                "events_available": n_available,
                "missing_count": n_requested - n_available,
                "missing_percentage": round(100.0 * (n_requested - n_available) / n_requested, 2) if n_requested else 0.0,
                "status_breakdown": "; ".join(f"{k}={v}" for k, v in sorted(status_counts.items())),
                "min": round(min(numeric_values), 6) if numeric_values else "",
                "max": round(max(numeric_values), 6) if numeric_values else "",
                "mean": round(statistics.fmean(numeric_values), 6) if numeric_values else "",
                "median": round(statistics.median(numeric_values), 6) if numeric_values else "",
                "stdev": round(statistics.stdev(numeric_values), 6) if len(numeric_values) > 1 else "",
                "invalid_nonphysical_count": len(invalid_notes),
                "invalid_examples": "; ".join(invalid_notes[:3]),
            }
        )
    return report


COVERAGE_REPORT_COLUMNS = [
    "feature_name",
    "events_requested",
    "events_available",
    "missing_count",
    "missing_percentage",
    "status_breakdown",
    "min",
    "max",
    "mean",
    "median",
    "stdev",
    "invalid_nonphysical_count",
    "invalid_examples",
]


def write_coverage_report(provenance_rows: list[dict], events_requested: int, out_path: str | Path) -> list[dict]:
    report = compute_feature_coverage_report(provenance_rows, events_requested)
    _write_csv(Path(out_path), report, COVERAGE_REPORT_COLUMNS)
    return report


# ---------------------------------------------------------------------------
# FMD-04 closure: full-corpus addressability index + validation-scope
# manifest. Neither performs any extraction/network/file I/O against a
# remote source — both are pure joins over data already on disk (the frozen
# FMD-03D canonical corpus + whatever `fmd_feature_table.csv` extraction has
# already produced), so both are safe and fast to run against the full
# 9,526-event corpus in an interactive session.
# ---------------------------------------------------------------------------

FMD04_VALIDATION_SAMPLE = "FMD04_VALIDATION_SAMPLE"
"""Label for the real, executed 29-event (22 Sri Lanka + 7 global-diversity)
adapter-validation extraction — proves the extraction pipeline itself works
end-to-end against real sources, NOT the final modelling feature matrix.
Full-corpus feature extraction is intentionally deferred until FMD-05
freezes the study cohort (see module docstring "Scale note")."""

EVENT_INDEX_COLUMNS = [
    "fmd_canonical_event_id",
    "source_record_id",
    "event_date",
    "latitude",
    "longitude",
    "country",
    "modelling_eligible",
    "feature_extraction_status",
    "validation_scope",
]


def load_extracted_event_ids(feature_table_csv: str | Path) -> set[str]:
    """Reads only the `fmd_canonical_event_id` column of an already-produced
    `fmd_feature_table.csv` — never re-runs extraction. Returns an empty set
    (not an error) if the file does not exist yet, since "no extraction has
    been run at all" is itself a legitimate addressability-index state."""
    path = Path(feature_table_csv)
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as f:
        return {row["fmd_canonical_event_id"] for row in csv.DictReader(f)}


def build_feature_event_index(
    events: list[FmdCanonicalEventRef],
    extracted_event_ids: set[str],
    *,
    validation_scope_ids: set[str] = frozenset(),
) -> list[dict]:
    """One row per canonical event passed in (never fewer, never more) —
    the full-corpus addressability contract this index exists to prove.
    `feature_extraction_status` is EXTRACTION_COMPLETE only for an event
    whose id already appears in a produced `fmd_feature_table.csv`;
    EXTRACTION_NOT_RUN otherwise — an explicit, non-error "intentionally
    deferred" status, never FEATURE_NOT_AVAILABLE/SOURCE_VALUE_MISSING/
    EXTRACTION_FAILED (those describe an attempted-but-absent per-feature
    VALUE, a different question this index does not answer)."""
    rows: list[dict] = []
    for event in events:
        extracted = event.fmd_canonical_event_id in extracted_event_ids
        rows.append(
            {
                "fmd_canonical_event_id": event.fmd_canonical_event_id,
                "source_record_id": event.source_record_id,
                "event_date": event.event_date or "",
                "latitude": event.latitude if event.latitude is not None else "",
                "longitude": event.longitude if event.longitude is not None else "",
                "country": event.country or "",
                "modelling_eligible": event.modelling_eligible,
                "feature_extraction_status": EXTRACTION_COMPLETE if extracted else EXTRACTION_NOT_RUN,
                "validation_scope": FMD04_VALIDATION_SAMPLE if event.fmd_canonical_event_id in validation_scope_ids else "",
            }
        )
    return rows


def write_feature_event_index(
    events: list[FmdCanonicalEventRef], extracted_event_ids: set[str], out_path: str | Path
) -> list[dict]:
    rows = build_feature_event_index(events, extracted_event_ids, validation_scope_ids=extracted_event_ids)
    _write_csv(Path(out_path), rows, EVENT_INDEX_COLUMNS)
    return rows


def build_validation_scope_manifest(
    events: list[FmdCanonicalEventRef], extracted_event_ids: set[str]
) -> dict:
    """Machine-readable record of exactly what the 29-event validation
    extraction does and does NOT represent (FMD-04 Step 2) — never claims
    remote feature values exist for the full corpus."""
    validated = [e for e in events if e.fmd_canonical_event_id in extracted_event_ids]
    sri_lanka = sum(1 for e in validated if e.country == "Sri Lanka")
    global_diversity = len(validated) - sri_lanka
    eligible_total = sum(1 for e in events if e.modelling_eligible)
    return {
        "validation_scope": FMD04_VALIDATION_SAMPLE,
        "validation_scope_description": (
            "A real, executed adapter-validation extraction proving the FMD-04 "
            "feature-enrichment pipeline works end-to-end against real remote "
            "sources for a deliberately small, geographically diverse sample. "
            "This is NOT the final modelling feature matrix."
        ),
        "sri_lanka_events": sri_lanka,
        "global_diversity_events": global_diversity,
        "validation_sample_total": len(validated),
        "full_canonical_corpus": len(events),
        "pre_fmd05_model_eligible_flag_count": eligible_total,
        "final_study_cohort": "NOT_YET_FROZEN",
        "full_cohort_feature_extraction": "DEFERRED_UNTIL_AFTER_FMD-05",
        "validated_event_ids": sorted(e.fmd_canonical_event_id for e in validated),
    }


def main(canonical_csv: str, out_dir: str, weather_cache_dir: str, *, limit: int | None = None) -> None:
    events = load_fmd_canonical_events(canonical_csv)
    if limit is not None:
        events = events[:limit]
    stats = run(events, out_dir=out_dir, weather_cache_dir=weather_cache_dir)
    coverage = write_coverage_report(stats["provenance_rows"], stats["events_requested"], Path(out_dir) / "fmd_feature_coverage_report.csv")
    print(f"events requested: {stats['events_requested']}  enriched: {stats['events_enriched']}")
    print(f"feature families reported in coverage: {len(coverage)}")


def main_addressability(canonical_csv: str, out_dir: str) -> None:
    """No extraction, no network calls — a pure local join over the frozen
    canonical corpus and whatever `fmd_feature_table.csv` already exists in
    `out_dir`. Safe to run against the full 9,526-event corpus every time."""
    out_path = Path(out_dir)
    events = load_fmd_canonical_events(canonical_csv)
    extracted_ids = load_extracted_event_ids(out_path / "fmd_feature_table.csv")
    index_rows = write_feature_event_index(events, extracted_ids, out_path / "fmd_feature_event_index.csv")
    manifest = build_validation_scope_manifest(events, extracted_ids)

    import json

    with (out_path / "fmd04_validation_scope_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    unique_ids = {r["fmd_canonical_event_id"] for r in index_rows}
    print(f"canonical events addressable: {len(index_rows)}  unique ids: {len(unique_ids)}")
    print(f"model-eligible addressable: {sum(1 for r in index_rows if r['modelling_eligible'] is True)}")
    print(f"validation sample (extraction complete): {manifest['validation_sample_total']}")
    print(f"  sri_lanka={manifest['sri_lanka_events']}  global_diversity={manifest['global_diversity_events']}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "index":
        canonical_csv = args[1] if len(args) > 1 else "../local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv"
        out_dir = args[2] if len(args) > 2 else "../local_data/processed/fmd/features"
        main_addressability(canonical_csv, out_dir)
    else:
        canonical_csv = args[0] if len(args) > 0 else "../local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv"
        out_dir = args[1] if len(args) > 1 else "../local_data/processed/fmd/features"
        weather_cache_dir = args[2] if len(args) > 2 else "../local_data/cache/weather"
        limit = int(args[3]) if len(args) > 3 else None
        main(canonical_csv, out_dir, weather_cache_dir, limit=limit)
