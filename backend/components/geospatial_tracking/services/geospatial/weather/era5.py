"""Checkpoint 5.5/5.6: real historical weather adapter — explicit model
selection, hourly-paired wind vectors, timezone-safe t0-precision-aware
pre-t0 cutoff, and an explicit valid-time-vs-availability-time split.

**Provider vs. model — stated separately, every time:**
`WEATHER_PROVIDER` is the Open-Meteo Historical Weather API
(https://open-meteo.com/en/docs/historical-weather-api), a free,
no-authentication INTERMEDIARY — NOT a direct Copernicus Climate Data
Store (CDS) call (CDS requires a registered personal API key/account
this environment does not have). `WEATHER_MODEL` is the specific
reanalysis model explicitly requested from that provider via the API's
own `models=` parameter, verified directly against the provider (both
via official docs and live request/response probing on 2026-08-19,
not from memory) rather than assumed.

**Why `models=era5`, not `era5_land`, `ecmwf_ifs`, `era5_seamless`, or
the unset default `best_match`:**

- `era5_land` (0.1°/~11km) does NOT provide `wind_speed_10m`,
  `wind_direction_10m`, or `precipitation` through this API at all —
  confirmed empirically: a real request for those variables with
  `models=era5_land` returns HTTP 200 with every value `null` for the
  full requested range. It cannot coherently supply this pipeline's
  required variables, so it is disqualified outright.
- `era5_seamless` and the unset default (`best_match`) both blend
  ERA5-Land (for temperature/dewpoint) with ERA5 (for wind/precipitation)
  transparently per grid cell/date — confirmed empirically: their
  temperature/dewpoint values are byte-identical to a pure `era5_land`
  request while their wind/precipitation values are byte-identical to a
  pure `era5` request, at the same coordinates/dates. That is exactly
  the "silently mixing sources" this checkpoint forbids, and `best_match`
  additionally switches models by date without notice — never
  reproducible across the corpus's real date range.
- `ecmwf_ifs` (2017-present, ~9km) DOES have all required variables as a
  single request, and covers this corpus's real date range, but Open-
  Meteo's own documentation states it is an operational analysis archive
  assembled from "the most up-to-date version of IFS" at each date, NOT
  a fixed-version reanalysis, and explicitly warns to use ERA5/ERA5-Land
  instead for multi-year data consistency.
- `cerra` (5km, 1985-June2021) covers Europe only — confirmed empirically
  it does not cover either smoke AOI at all.
- `era5` (0.25°/~25km, 1940-present) is the only remaining candidate: a
  single, fixed-version reanalysis system, confirmed via a real request
  to provide non-null `temperature_2m`, `dew_point_2m`, `precipitation`,
  `wind_speed_10m`, and `wind_direction_10m` together, and fully covers
  the corpus's real 2018-2026 date range. Coarser resolution than
  ERA5-Land/IFS/CERRA is the accepted tradeoff — explicitly NOT chosen
  for any performance reason (no model exists yet).

**Checkpoint 5.6 — valid-time vs. availability-time (see `base.py` for
the full permanent-rule statement).** ERA5 is a *retrospective*
reanalysis: a value whose meteorological VALID TIME is before t0 was, in
almost every real historical case, not actually published until much
later. Official ECMWF/Copernicus documentation (confirmed 2026-08-19):
the preliminary release (ERA5T) is published about 5 days after each
day; the quality-controlled final ERA5 is published about 2 months
later (https://confluence.ecmwf.int/spaces/CKB/pages/76414402/ERA5+data+documentation).
`ERA5T_PRELIMINARY_LAG_DAYS` records this for the OPTIONAL
`strict_operational_availability` sensitivity mode — the PRIMARY path
never claims a value was operationally available at t0, only that its
valid time was safely pre-t0 (`WeatherTemporalRole.RETROSPECTIVE_REANALYSIS_STATE_PROXY`,
`WeatherAvailabilityQuality.UNKNOWN` by default).

Every request below passes `models=era5` explicitly — never the unset
default — so a result can never be silently served by whatever
`best_match` happened to resolve to for that date/location.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

from ..distance import distance_km
from ..feature_result import FeatureResult, FeatureStatus
from .base import T0Precision, WeatherAvailabilityQuality, WeatherTemporalRole
from .humidity import relative_humidity_percent
from .t0_resolution import T0Boundary, is_timestamp_eligible, pre_t0_window_bounds, resolve_t0_boundary
from .wind import wind_components_from_speed_direction, wind_speed_from_components

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

WEATHER_PROVIDER = "Open-Meteo Historical Weather API (archive-api.open-meteo.com) — intermediary, not direct Copernicus CDS access"
WEATHER_MODEL = "era5"
WEATHER_MODEL_LABEL = "ERA5 (ECMWF fixed-version reanalysis, redistributed via Copernicus C3S)"
WEATHER_MODEL_RESOLUTION = "0.25 degrees (~25km at equator) — ERA5 native reanalysis grid"

# Official ECMWF/Copernicus documentation (Checkpoint 5.6, confirmed 2026-08-19,
# https://confluence.ecmwf.int/spaces/CKB/pages/76414402/ERA5+data+documentation):
# "daily updates for ERA5T are available about 5 days behind real time";
# "the final ERA5 data are available about two months after the month in
# question." These are OFFICIAL DOCUMENTED LAGS, never an invented exact
# historical publication timestamp — used only as an optional, explicitly
# opt-in conservative sensitivity bound (strict_operational_availability
# below), never applied silently to the primary path.
ERA5T_PRELIMINARY_LAG_DAYS = 5
ERA5_FINAL_LAG_MONTHS_APPROX = 2

DATASET_NAME = WEATHER_PROVIDER
DATASET_VERSION = f"{WEATHER_MODEL_LABEL} (models={WEATHER_MODEL})"
SOURCE_RESOLUTION = WEATHER_MODEL_RESOLUTION
SOURCE_CRS = "EPSG:4326"

_DAILY_VARS = "temperature_2m_mean,dew_point_2m_mean,precipitation_sum"
_HOURLY_VARS = "temperature_2m,dew_point_2m,precipitation,wind_speed_10m,wind_direction_10m"


def _daily_request_params(latitude: float, longitude: float, date: str) -> dict:
    """Pure: the exact request parameters `fetch_daily_weather` sends.
    `models` is ALWAYS present — WX-ID-01/02 verify this directly, so a
    default `best_match` response can never be silently mislabeled as
    this module's declared `WEATHER_MODEL`."""
    return {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": date,
        "end_date": date,
        "daily": _DAILY_VARS,
        "models": WEATHER_MODEL,
        "timezone": "UTC",
    }


def _hourly_request_params(latitude: float, longitude: float, start_date: str, end_date: str, model: str = WEATHER_MODEL) -> dict:
    """Pure: the exact request parameters `build_pre_t0_weather_summary`
    sends. `models` is ALWAYS present (WX-ID-01/02) and is ALWAYS the
    caller's own `model` argument — Checkpoint 6A.5 correction: this
    function previously hardcoded the `WEATHER_MODEL` module constant
    here regardless of what `model` a caller passed to
    `build_pre_t0_weather_summary`, so the request actually sent to
    Open-Meteo could silently disagree with the model name recorded in
    a `FeatureResult`'s own metadata. `timezone=UTC` is deliberate —
    returned hourly timestamps are compared directly against the
    `zoneinfo`-computed UTC cutoff from `t0_resolution.py`, never
    against Open-Meteo's own `timezone=auto` local-time convenience
    field (confirmed NOT historically offset-accurate — see
    `t0_resolution.py` module docstring)."""
    return {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": _HOURLY_VARS,
        "models": model,
        "wind_speed_unit": "ms",
        "timezone": "UTC",
    }


def fetch_hourly_payload(
    latitude: float, longitude: float, start_date: str, end_date: str, *, model: str = WEATHER_MODEL, timeout_seconds: float = 30.0,
) -> dict:
    """Checkpoint FMD-07A-R2B2-R1 Section 5: the ONE place this package
    issues a live hourly `requests.get(ARCHIVE_URL, params=...)` call --
    both `build_pre_t0_weather_summary`'s own per-window live fetch below
    and any consolidated-request caller (`fmd_model_development_r2b2.py`'s
    `fetch_consolidated_weather_windows`) go through this single function,
    so endpoint/params/timeout/response-shape stay one source of truth
    instead of a second, independent Open-Meteo client. Raises
    `requests.RequestException` on failure -- callers decide how to
    report that (BLOCKED, NETWORK_ERROR, ...); this function never
    swallows or reinterprets the error, and never fabricates a payload."""
    params = _hourly_request_params(latitude, longitude, start_date, end_date, model=model)
    response = requests.get(ARCHIVE_URL, params=params, timeout=timeout_seconds)
    response.raise_for_status()
    return response.json()


def _classify_temporal_role(date: str, forecast_origin_t0: str | None) -> str:
    if forecast_origin_t0 is None:
        return WeatherTemporalRole.RETROSPECTIVE_REANALYSIS_STATE_PROXY.value
    if date <= forecast_origin_t0:
        return WeatherTemporalRole.RETROSPECTIVE_REANALYSIS_STATE_PROXY.value
    return WeatherTemporalRole.REALIZED_FUTURE_REANALYSIS.value


# ---------------------------------------------------------------------------
# Part 4: hourly-paired wind vector construction (pure — WIND-01..06)
# ---------------------------------------------------------------------------


def aggregate_hourly_wind(speeds_m_s: list[float], directions_deg: list[float]) -> tuple[float, float]:
    """Pure: converts EACH hour's own (speed, direction) pair to (u, v)
    independently via `wind.wind_components_from_speed_direction`, then
    averages the COMPONENTS — never averages compass directions
    arithmetically (350 deg + 10 deg must never become 180 deg) and
    never pairs one hour's speed with a different hour's/day's
    direction. Raises on empty input — callers must treat "no eligible
    hourly samples" as MISSING, never a fabricated (0, 0)."""
    if not speeds_m_s:
        raise ValueError("aggregate_hourly_wind requires at least one (speed, direction) pair")
    if len(speeds_m_s) != len(directions_deg):
        raise ValueError("speeds_m_s and directions_deg must be the same length (paired per hour)")
    us = []
    vs = []
    for speed, direction in zip(speeds_m_s, directions_deg):
        u, v = wind_components_from_speed_direction(speed, direction)
        us.append(u)
        vs.append(v)
    return sum(us) / len(us), sum(vs) / len(vs)


# ---------------------------------------------------------------------------
# Part 1 (preserved): daily-aggregate fetch — wind REMOVED from this path
# (Checkpoint 5.5 Part 4: "Remove the current scientific-use path that
# pairs daily maximum wind speed with daily dominant wind direction").
# Retained only for non-wind daily-aggregate covariates; wind is only
# ever produced by build_pre_t0_weather_summary's hourly pairing below.
# ---------------------------------------------------------------------------


def _blocked(feature_name: str, units: str, retrieved_at: str, reason: str) -> FeatureResult:
    return FeatureResult(
        feature_name=feature_name,
        value=None,
        units=units,
        status=FeatureStatus.BLOCKED.value,
        dataset_name=DATASET_NAME,
        dataset_version=DATASET_VERSION,
        reference_time=None,
        retrieved_at=retrieved_at,
        source_resolution=SOURCE_RESOLUTION,
        source_crs=SOURCE_CRS,
        analysis_method="Open-Meteo archive API request",
        quality_notes=reason,
    )


def fetch_daily_weather(
    *,
    latitude: float,
    longitude: float,
    date: str,
    forecast_origin_t0: str | None = None,
    allow_future_reanalysis: bool = False,
    timeout_seconds: float = 20.0,
) -> list[FeatureResult]:
    """`date`: ISO `YYYY-MM-DD`. `forecast_origin_t0`: ISO `YYYY-MM-DD`,
    optional — when provided, classifies this request's temporal role
    (see `base.py`). If the classification would be
    `REALIZED_FUTURE_REANALYSIS` and `allow_future_reanalysis` is not
    explicitly `True`, every returned feature is `BLOCKED` with an
    explanatory `quality_notes` — the hard leakage gate (WX-04),
    preserved unchanged from Checkpoint 5.

    Returns one `FeatureResult` per DAILY-AGGREGATE variable:
    `temperature_2m`, `dewpoint_2m`, `relative_humidity_2m` (derived,
    see `humidity.py`), `precipitation`. Wind is intentionally NOT
    included here (Checkpoint 5.5 Part 4) — use
    `build_pre_t0_weather_summary` for wind, which pairs each hour's own
    speed with that same hour's own direction.
    """
    retrieved_at = datetime.now(timezone.utc).isoformat()
    temporal_role = _classify_temporal_role(date, forecast_origin_t0)
    feature_names = ["temperature_2m", "dewpoint_2m", "relative_humidity_2m", "precipitation"]

    if temporal_role == WeatherTemporalRole.REALIZED_FUTURE_REANALYSIS.value and not allow_future_reanalysis:
        reason = (
            f"date {date} is AFTER forecast_origin_t0={forecast_origin_t0} — this would be "
            "REALIZED_FUTURE_REANALYSIS (a valid_time after t0, which an operational forecaster at t0 "
            "could not have observed regardless of any availability-lag question). Refused: pass "
            "allow_future_reanalysis=True only for clearly-labeled retrospective sensitivity/oracle "
            "analysis, never primary t0 features."
        )
        return [_blocked(name, "n/a", retrieved_at, reason) for name in feature_names]

    try:
        response = requests.get(ARCHIVE_URL, params=_daily_request_params(latitude, longitude, date), timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        reason = f"Open-Meteo archive API request failed (models={WEATHER_MODEL}): {exc}"
        return [_blocked(name, "n/a", retrieved_at, reason) for name in feature_names]

    daily = payload.get("daily", {})
    times = daily.get("time") or []
    if not times:
        reason = f"Open-Meteo returned no daily record for this date/location (models={WEATHER_MODEL})"
        return [_blocked(name, "n/a", retrieved_at, reason) for name in feature_names]

    def _value(key: str):
        values = daily.get(key) or []
        return values[0] if values and values[0] is not None else None

    temperature_c = _value("temperature_2m_mean")
    dewpoint_c = _value("dew_point_2m_mean")
    precipitation_mm = _value("precipitation_sum")

    def _result(feature_name: str, value, units: str, method: str, notes: str = "") -> FeatureResult:
        if value is None:
            return FeatureResult(
                feature_name=feature_name,
                value=None,
                units=units,
                status=FeatureStatus.MISSING.value,
                dataset_name=DATASET_NAME,
                dataset_version=DATASET_VERSION,
                reference_time=date,
                retrieved_at=retrieved_at,
                source_resolution=SOURCE_RESOLUTION,
                source_crs=SOURCE_CRS,
                analysis_method=method,
                quality_notes=notes or f"no value returned for {feature_name} on {date} (models={WEATHER_MODEL})",
            )
        return FeatureResult(
            feature_name=feature_name,
            value=value,
            units=units,
            status=FeatureStatus.REAL.value,
            dataset_name=DATASET_NAME,
            dataset_version=DATASET_VERSION,
            reference_time=date,
            retrieved_at=retrieved_at,
            source_resolution=SOURCE_RESOLUTION,
            source_crs=SOURCE_CRS,
            analysis_method=method,
            quality_notes=(
                f"temporal_role={temporal_role}; weather_model={WEATHER_MODEL}; "
                "availability_quality=UNKNOWN (valid_time-only safety; see base.py)"
            )
            + (f"; {notes}" if notes else ""),
        )

    results = [
        _result("temperature_2m", temperature_c, "degC", "daily mean, direct from source"),
        _result("dewpoint_2m", dewpoint_c, "degC", "daily mean, direct from source"),
        _result("precipitation", precipitation_mm, "mm", "daily sum, direct from source"),
    ]

    if temperature_c is not None and dewpoint_c is not None:
        rh = relative_humidity_percent(temperature_c, dewpoint_c)
        results.append(
            _result(
                "relative_humidity_2m",
                rh,
                "%",
                "derived: Magnus-Tetens approximation from temperature_2m + dewpoint_2m (see humidity.py)",
            )
        )
    else:
        results.append(
            _result("relative_humidity_2m", None, "%", "derived: Magnus-Tetens approximation", "missing temperature or dewpoint input")
        )

    return results


def fetch_weather_for_source(
    *,
    source_latitude: float,
    source_longitude: float,
    aoi_latitude: float,
    aoi_longitude: float,
    date: str,
    forecast_origin_t0: str | None = None,
    allow_future_reanalysis: bool = False,
    max_offset_km: float = 50.0,
) -> list[FeatureResult]:
    """Convenience wrapper documenting that weather is fetched at the
    AOI's own coordinates, not silently substituted from a distant point —
    raises if `aoi` is implausibly far from `source` (a sanity check, not
    a scientific claim about representativeness)."""
    offset = distance_km(source_latitude, source_longitude, aoi_latitude, aoi_longitude)
    if offset > max_offset_km:
        raise ValueError(f"AOI is {offset:.1f} km from the source point — exceeds max_offset_km={max_offset_km}")
    return fetch_daily_weather(
        latitude=aoi_latitude,
        longitude=aoi_longitude,
        date=date,
        forecast_origin_t0=forecast_origin_t0,
        allow_future_reanalysis=allow_future_reanalysis,
    )


# ---------------------------------------------------------------------------
# Part 6-7 (5.5) / Parts 1-8 (5.6): frozen primary rule + the pre-t0
# weather summary builder, now timezone-safe and availability-explicit.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreT0WeatherWindow:
    """Provenance metadata for one `build_pre_t0_weather_summary` call.
    Checkpoint 5.6 additions: `source_local_date`/`source_timezone`/
    `t0_timezone_quality`/`t0_start_local` (the timezone-resolution
    trail — Part 4) and `availability_quality`/`strict_operational_availability`/
    `availability_lag_days_used` (the valid-time vs. availability-time
    split — Parts 1-3/7-8)."""

    window_start: str | None
    window_end: str | None
    number_of_hourly_samples: int
    weather_provider: str
    weather_model: str
    weather_model_resolution: str
    request_parameters: dict
    retrieval_date: str
    temporal_role: str
    weather_available_time: None  # always None: no exact historical ERA5/ERA5T publication timestamp is known or fabricated (WX-AVAIL-04)
    availability_quality: str
    strict_operational_availability: bool
    availability_lag_days_used: int | None
    source_local_date: str | None
    source_timezone: str | None
    t0_timezone_quality: str
    t0_start_local: str | None

    def as_dict(self) -> dict:
        return {
            "window_start": self.window_start,
            "window_end": self.window_end,
            "number_of_hourly_samples": self.number_of_hourly_samples,
            "weather_provider": self.weather_provider,
            "weather_model": self.weather_model,
            "weather_model_resolution": self.weather_model_resolution,
            "request_parameters": self.request_parameters,
            "retrieval_date": self.retrieval_date,
            "temporal_role": self.temporal_role,
            "weather_available_time": self.weather_available_time,
            "availability_quality": self.availability_quality,
            "strict_operational_availability": self.strict_operational_availability,
            "availability_lag_days_used": self.availability_lag_days_used,
            "source_local_date": self.source_local_date,
            "source_timezone": self.source_timezone,
            "t0_timezone_quality": self.t0_timezone_quality,
            "t0_start_local": self.t0_start_local,
        }


def _pre_t0_blocked(feature_name: str, units: str, window: PreT0WeatherWindow, reason: str) -> FeatureResult:
    return FeatureResult(
        feature_name=feature_name,
        value=None,
        units=units,
        status=FeatureStatus.BLOCKED.value,
        dataset_name=DATASET_NAME,
        dataset_version=DATASET_VERSION,
        reference_time=f"{window.window_start}..{window.window_end}",
        retrieved_at=window.retrieval_date,
        source_resolution=SOURCE_RESOLUTION,
        source_crs=SOURCE_CRS,
        analysis_method="pre-t0 hourly window aggregation",
        quality_notes=reason,
    )


def _pre_t0_missing(feature_name: str, units: str, window: PreT0WeatherWindow, reason: str) -> FeatureResult:
    return FeatureResult(
        feature_name=feature_name,
        value=None,
        units=units,
        status=FeatureStatus.MISSING.value,
        dataset_name=DATASET_NAME,
        dataset_version=DATASET_VERSION,
        reference_time=f"{window.window_start}..{window.window_end}",
        retrieved_at=window.retrieval_date,
        source_resolution=SOURCE_RESOLUTION,
        source_crs=SOURCE_CRS,
        analysis_method="pre-t0 hourly window aggregation",
        quality_notes=reason,
    )


def _pre_t0_real(feature_name: str, value: float, units: str, window: PreT0WeatherWindow, method: str) -> FeatureResult:
    return FeatureResult(
        feature_name=feature_name,
        value=value,
        units=units,
        status=FeatureStatus.REAL.value,
        dataset_name=DATASET_NAME,
        dataset_version=DATASET_VERSION,
        reference_time=f"{window.window_start}..{window.window_end}",
        retrieved_at=window.retrieval_date,
        source_resolution=SOURCE_RESOLUTION,
        source_crs=SOURCE_CRS,
        analysis_method=method,
        quality_notes=(
            f"temporal_role={window.temporal_role}; availability_quality={window.availability_quality}; "
            f"weather_model={window.weather_model}; n_hourly_samples={window.number_of_hourly_samples}; "
            f"window={window.window_start}..{window.window_end}; source_timezone={window.source_timezone}"
        ),
    )


def build_pre_t0_weather_summary(
    *,
    latitude: float,
    longitude: float,
    t0: str,
    t0_precision: str,
    lookback_hours: float,
    model: str = WEATHER_MODEL,
    strict_operational_availability: bool = False,
    timeout_seconds: float = 30.0,
    cache: object | None = None,
) -> tuple[PreT0WeatherWindow, list[FeatureResult]]:
    """The PRIMARY historical weather feature builder — PRE-T0 OBSERVED
    REANALYSIS HISTORY ONLY, timezone-safe.

    **Two separate safety questions (Checkpoint 5.6, `base.py`):**
    A) meteorological valid-time safety — every hourly sample used has a
    valid_time strictly pre-cutoff, enforced structurally by
    `is_timestamp_eligible`/`t0_resolution.py` (this function never even
    requests a post-cutoff timestamp). B) operational availability
    safety — whether that value was actually published/computable by
    t0 — is a SEPARATE, harder question this function does NOT claim to
    answer by default (`availability_quality=UNKNOWN`). Passing A never
    implies B.

    `t0_precision=DATE_ONLY`: `t0`'s calendar date is interpreted as the
    AOI's own SOURCE-LOCAL CIVIL DATE (IANA timezone resolved offline via
    `t0_resolution.resolve_iana_timezone` — never hardcoded), converted
    to a UTC cutoff via `zoneinfo` using the HISTORICALLY correct offset
    for that date. If no timezone can be defensibly resolved for the
    coordinate, every returned feature is BLOCKED — never silently
    treated as UTC.

    `strict_operational_availability=True` — the **ERA5T_LAG_FILTER_SENSITIVITY**
    diagnostic mode (Checkpoint 6A Part 8, renamed/labeled explicitly
    here so it is never mistaken for genuine operational reconstruction):
    an OPTIONAL, explicitly opt-in conservative sensitivity mode —
    additionally excludes any hour whose value would not yet have been
    published under the documented ERA5T ~5-day preliminary-release lag
    (`ERA5T_PRELIMINARY_LAG_DAYS`, official ECMWF/Copernicus
    documentation). The underlying numerical values returned are still
    FINAL ERA5 values, never genuine issue-time/versioned ERA5T
    values — this mode is a documented-lag FILTER on which valid-times
    are included, not a fetch of different (ERA5T-vintage) numbers. When
    used, `availability_quality=LAG_RULE_PROXY` (never `ACTUAL` — no
    exact historical publication timestamp is known). It MUST NOT be
    used as a primary historical training/validation feature mode, and
    MUST NOT be described as "ACTUAL_OPERATIONAL_ERA5" or a
    "historically available ERA5T reconstruction." Default `False`: the
    primary path (used by `services/features/assembler.py`) only ever
    claims A, with `temporal_role=RETROSPECTIVE_REANALYSIS_STATE_PROXY`.

    `lookback_hours` is an `UNFROZEN_DEVELOPMENT_PARAMETER`
    (`config.WEATHER_LOOKBACK_HOURS_DEV_DEFAULT`) — callers must pass it
    explicitly.

    `cache`: optional duck-typed object with `.get(key) -> dict | None`
    and `.set(key, payload)` (e.g. `services/features/cache.FileWeatherCache`)
    — this module never imports that class, only calls these two methods,
    so `services/geospatial/weather` stays decoupled from the higher-level
    `services/features` package. The cache key is derived from the exact
    hourly request parameters (model, lat/lon, window, variables,
    timezone) — an identical request always hits the same key; nothing
    here ever returns a fabricated value for a key that does not match.

    Wind is built from PAIRED HOURLY (speed, direction) — never daily
    max-speed + dominant-direction (`aggregate_hourly_wind`).
    """
    retrieval_date = datetime.now(timezone.utc).isoformat()

    feature_names_units_for_unsupported_model = [
        ("mean_temperature_2m", "degC"),
        ("mean_relative_humidity_2m", "%"),
        ("precipitation_accumulation", "mm"),
        ("mean_u10", "m/s"),
        ("mean_v10", "m/s"),
        ("mean_wind_speed", "m/s"),
        ("vector_resultant_speed", "m/s"),
        ("directional_persistence", "ratio"),
    ]
    if model != WEATHER_MODEL:
        # Checkpoint 6A.5 Part 2: only `WEATHER_MODEL` ("era5") has been
        # investigated/verified for this adapter's provenance constants
        # (resolution, temporal coverage, variable coherence — see module
        # docstring). Rather than silently request a different model
        # while still reporting era5-specific metadata, refuse outright —
        # a declared `model` can never disagree with the actual request.
        unsupported_model_window = PreT0WeatherWindow(
            window_start=None,
            window_end=None,
            number_of_hourly_samples=0,
            weather_provider=WEATHER_PROVIDER,
            weather_model=model,
            weather_model_resolution=None,
            request_parameters={},
            retrieval_date=retrieval_date,
            temporal_role=WeatherTemporalRole.UNKNOWN.value,
            weather_available_time=None,
            availability_quality=WeatherAvailabilityQuality.UNKNOWN.value,
            strict_operational_availability=strict_operational_availability,
            availability_lag_days_used=None,
            source_local_date=None,
            source_timezone=None,
            t0_timezone_quality="UNKNOWN",
            t0_start_local=None,
        )
        reason = (
            f"unsupported weather model {model!r}: only {WEATHER_MODEL!r} is investigated/verified in this "
            "adapter (see era5.py module docstring for the full model-selection evidence); refusing rather "
            "than silently requesting a different model than declared"
        )
        return unsupported_model_window, [
            _pre_t0_blocked(name, units, unsupported_model_window, reason) for name, units in feature_names_units_for_unsupported_model
        ]

    boundary = resolve_t0_boundary(t0=t0, t0_precision=t0_precision, latitude=latitude, longitude=longitude)

    availability_quality = (
        WeatherAvailabilityQuality.LAG_RULE_PROXY.value
        if strict_operational_availability
        else WeatherAvailabilityQuality.UNKNOWN.value
    )
    lag_days_used = ERA5T_PRELIMINARY_LAG_DAYS if strict_operational_availability else None

    feature_names_units = [
        ("mean_temperature_2m", "degC"),
        ("mean_relative_humidity_2m", "%"),
        ("precipitation_accumulation", "mm"),
        ("mean_u10", "m/s"),
        ("mean_v10", "m/s"),
        ("mean_wind_speed", "m/s"),
        ("vector_resultant_speed", "m/s"),
        ("directional_persistence", "ratio"),
    ]

    if not boundary.resolved:
        unresolved_window = PreT0WeatherWindow(
            window_start=None,
            window_end=None,
            number_of_hourly_samples=0,
            weather_provider=WEATHER_PROVIDER,
            weather_model=model,
            weather_model_resolution=WEATHER_MODEL_RESOLUTION,
            request_parameters={},
            retrieval_date=retrieval_date,
            temporal_role=WeatherTemporalRole.UNKNOWN.value,
            weather_available_time=None,
            availability_quality=WeatherAvailabilityQuality.UNKNOWN.value,
            strict_operational_availability=strict_operational_availability,
            availability_lag_days_used=None,
            source_local_date=boundary.source_local_date,
            source_timezone=boundary.source_timezone,
            t0_timezone_quality=boundary.t0_timezone_quality,
            t0_start_local=boundary.t0_start_local,
        )
        return unresolved_window, [
            _pre_t0_blocked(name, units, unresolved_window, boundary.quality_notes) for name, units in feature_names_units
        ]

    window_start, cutoff = pre_t0_window_bounds(boundary, lookback_hours)
    request_params = _hourly_request_params(latitude, longitude, window_start.date().isoformat(), cutoff.date().isoformat(), model=model)

    empty_window = PreT0WeatherWindow(
        window_start=window_start.isoformat(),
        window_end=cutoff.isoformat(),
        number_of_hourly_samples=0,
        weather_provider=WEATHER_PROVIDER,
        weather_model=model,
        weather_model_resolution=WEATHER_MODEL_RESOLUTION,
        request_parameters=request_params,
        retrieval_date=retrieval_date,
        temporal_role=WeatherTemporalRole.RETROSPECTIVE_REANALYSIS_STATE_PROXY.value,
        weather_available_time=None,
        availability_quality=availability_quality,
        strict_operational_availability=strict_operational_availability,
        availability_lag_days_used=lag_days_used,
        source_local_date=boundary.source_local_date,
        source_timezone=boundary.source_timezone,
        t0_timezone_quality=boundary.t0_timezone_quality,
        t0_start_local=boundary.t0_start_local,
    )

    cache_key = None
    if cache is not None:
        cache_key = hashlib.sha256(json.dumps(request_params, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        payload = cache.get(cache_key)
        if payload is None:
            try:
                payload = fetch_hourly_payload(latitude, longitude, request_params["start_date"], request_params["end_date"], model=model, timeout_seconds=timeout_seconds)
            except requests.RequestException as exc:
                reason = f"Open-Meteo archive API request failed (models={model}): {exc}"
                return empty_window, [_pre_t0_blocked(name, units, empty_window, reason) for name, units in feature_names_units]
            cache.set(cache_key, payload)
    else:
        try:
            payload = fetch_hourly_payload(latitude, longitude, request_params["start_date"], request_params["end_date"], model=model, timeout_seconds=timeout_seconds)
        except requests.RequestException as exc:
            reason = f"Open-Meteo archive API request failed (models={model}): {exc}"
            return empty_window, [_pre_t0_blocked(name, units, empty_window, reason) for name, units in feature_names_units]

    return summarize_hourly_payload_for_window(
        payload, boundary, lookback_hours, latitude=latitude, longitude=longitude, model=model,
        strict_operational_availability=strict_operational_availability, retrieval_date=retrieval_date,
    )


def summarize_hourly_payload_for_window(
    payload: dict,
    boundary: T0Boundary,
    lookback_hours: float,
    *,
    latitude: float,
    longitude: float,
    model: str = WEATHER_MODEL,
    strict_operational_availability: bool = False,
    retrieval_date: str | None = None,
) -> tuple[PreT0WeatherWindow, list[FeatureResult]]:
    """PURE (no network, no cache) -- Checkpoint FMD-07A-R2B2-R1 Section 4:
    the single source of truth for turning an already-fetched Open-Meteo
    hourly `payload` into a `(PreT0WeatherWindow, list[FeatureResult])`
    pre-t0 summary. `boundary` must already be `resolved` (callers check
    this themselves -- `build_pre_t0_weather_summary` above never calls
    this helper for an unresolved boundary, exactly as before).

    `payload` may come from ANY real request whose `hourly` arrays cover
    at least `[window_start, cutoff]` for this `lookback_hours` -- an
    exact per-window live/cached fetch (this module's own primary path,
    above) or a real, wider superset fetch a caller has independently
    obtained under ITS OWN exact cache key
    (`fmd_model_development_r2b2.fetch_consolidated_weather_windows` --
    never seeded into `FileWeatherCache` under any OTHER window's key,
    per that checkpoint's Section 3). The eligibility filter below only
    ever looks at each hour's own timestamp against `window_start`/
    `cutoff`, never at what request produced the payload, so both
    callers get byte-identical results for the same boundary/
    lookback_hours/payload content -- this is the ONLY place the
    eligibility filtering / hourly wind pairing / aggregation equations
    are implemented; `build_pre_t0_weather_summary` never duplicates
    them."""
    retrieval_date = retrieval_date or datetime.now(timezone.utc).isoformat()

    availability_quality = (
        WeatherAvailabilityQuality.LAG_RULE_PROXY.value
        if strict_operational_availability
        else WeatherAvailabilityQuality.UNKNOWN.value
    )
    lag_days_used = ERA5T_PRELIMINARY_LAG_DAYS if strict_operational_availability else None

    feature_names_units = [
        ("mean_temperature_2m", "degC"),
        ("mean_relative_humidity_2m", "%"),
        ("precipitation_accumulation", "mm"),
        ("mean_u10", "m/s"),
        ("mean_v10", "m/s"),
        ("mean_wind_speed", "m/s"),
        ("vector_resultant_speed", "m/s"),
        ("directional_persistence", "ratio"),
    ]

    window_start, cutoff = pre_t0_window_bounds(boundary, lookback_hours)
    request_params = _hourly_request_params(latitude, longitude, window_start.date().isoformat(), cutoff.date().isoformat(), model=model)
    t0_precision = boundary.t0_precision

    empty_window = PreT0WeatherWindow(
        window_start=window_start.isoformat(),
        window_end=cutoff.isoformat(),
        number_of_hourly_samples=0,
        weather_provider=WEATHER_PROVIDER,
        weather_model=model,
        weather_model_resolution=WEATHER_MODEL_RESOLUTION,
        request_parameters=request_params,
        retrieval_date=retrieval_date,
        temporal_role=WeatherTemporalRole.RETROSPECTIVE_REANALYSIS_STATE_PROXY.value,
        weather_available_time=None,
        availability_quality=availability_quality,
        strict_operational_availability=strict_operational_availability,
        availability_lag_days_used=lag_days_used,
        source_local_date=boundary.source_local_date,
        source_timezone=boundary.source_timezone,
        t0_timezone_quality=boundary.t0_timezone_quality,
        t0_start_local=boundary.t0_start_local,
    )

    hourly = payload.get("hourly", {})
    times = hourly.get("time") or []
    if not times:
        reason = f"Open-Meteo returned no hourly record for this location (models={model})"
        return empty_window, [_pre_t0_blocked(name, units, empty_window, reason) for name, units in feature_names_units]

    eligible_idx = []
    for i, t in enumerate(times):
        ts = datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
        if not (is_timestamp_eligible(ts, t0_precision, cutoff) and ts >= window_start):
            continue
        if strict_operational_availability and (ts + timedelta(days=ERA5T_PRELIMINARY_LAG_DAYS)) > cutoff:
            continue  # valid-time-safe, but not yet operationally available under the conservative lag rule
        eligible_idx.append(i)

    window = PreT0WeatherWindow(
        window_start=window_start.isoformat(),
        window_end=cutoff.isoformat(),
        number_of_hourly_samples=len(eligible_idx),
        weather_provider=WEATHER_PROVIDER,
        weather_model=model,
        weather_model_resolution=WEATHER_MODEL_RESOLUTION,
        request_parameters=request_params,
        retrieval_date=retrieval_date,
        temporal_role=WeatherTemporalRole.RETROSPECTIVE_REANALYSIS_STATE_PROXY.value,
        weather_available_time=None,
        availability_quality=availability_quality,
        strict_operational_availability=strict_operational_availability,
        availability_lag_days_used=lag_days_used,
        source_local_date=boundary.source_local_date,
        source_timezone=boundary.source_timezone,
        t0_timezone_quality=boundary.t0_timezone_quality,
        t0_start_local=boundary.t0_start_local,
    )

    if not eligible_idx:
        reason = f"no hourly sample fell inside the pre-t0 window {window.window_start}..{window.window_end}"
        return window, [_pre_t0_missing(name, units, window, reason) for name, units in feature_names_units]

    def _series(key: str) -> list:
        raw = hourly.get(key) or []
        return [raw[i] if i < len(raw) else None for i in eligible_idx]

    temps = [v for v in _series("temperature_2m") if v is not None]
    dewpoints_raw = _series("dew_point_2m")
    temps_raw = _series("temperature_2m")
    precs = [v for v in _series("precipitation") if v is not None]
    speeds_raw = _series("wind_speed_10m")
    dirs_raw = _series("wind_direction_10m")

    results: list[FeatureResult] = []

    if temps:
        results.append(_pre_t0_real("mean_temperature_2m", sum(temps) / len(temps), "degC", window, "mean of eligible pre-t0 hourly temperature_2m"))
    else:
        results.append(_pre_t0_missing("mean_temperature_2m", "degC", window, "no non-null temperature_2m in the pre-t0 window"))

    rh_values = [
        relative_humidity_percent(t, d)
        for t, d in zip(temps_raw, dewpoints_raw)
        if t is not None and d is not None
    ]
    if rh_values:
        results.append(
            _pre_t0_real(
                "mean_relative_humidity_2m",
                sum(rh_values) / len(rh_values),
                "%",
                window,
                "mean of per-hour Magnus-Tetens-derived RH (see humidity.py), each from that same hour's own temperature_2m + dew_point_2m",
            )
        )
    else:
        results.append(_pre_t0_missing("mean_relative_humidity_2m", "%", window, "no hour had both temperature_2m and dew_point_2m"))

    if precs:
        results.append(_pre_t0_real("precipitation_accumulation", sum(precs), "mm", window, "sum of eligible pre-t0 hourly precipitation"))
    else:
        results.append(_pre_t0_missing("precipitation_accumulation", "mm", window, "no non-null precipitation in the pre-t0 window"))

    wind_pairs = [(s, d) for s, d in zip(speeds_raw, dirs_raw) if s is not None and d is not None]
    if wind_pairs:
        speeds = [p[0] for p in wind_pairs]
        dirs = [p[1] for p in wind_pairs]
        mean_u, mean_v = aggregate_hourly_wind(speeds, dirs)
        results.append(
            _pre_t0_real(
                "mean_u10",
                mean_u,
                "m/s",
                window,
                "mean of per-hour eastward components, EACH hour's own wind_speed_10m paired with THAT SAME hour's own wind_direction_10m (see aggregate_hourly_wind)",
            )
        )
        results.append(
            _pre_t0_real(
                "mean_v10",
                mean_v,
                "m/s",
                window,
                "mean of per-hour northward components, EACH hour's own wind_speed_10m paired with THAT SAME hour's own wind_direction_10m",
            )
        )
        mean_speed = sum(speeds) / len(speeds)
        results.append(_pre_t0_real("mean_wind_speed", mean_speed, "m/s", window, "mean of eligible pre-t0 hourly wind_speed_10m"))

        # optional, only when mathematically defined
        resultant_speed = wind_speed_from_components(mean_u, mean_v)
        results.append(
            _pre_t0_real(
                "vector_resultant_speed",
                resultant_speed,
                "m/s",
                window,
                "magnitude of the (mean_u10, mean_v10) vector — the net displacement-equivalent wind speed, distinct from mean_wind_speed (the mean of per-hour speed magnitudes)",
            )
        )
        if mean_speed > 0:
            persistence = resultant_speed / mean_speed
            results.append(
                _pre_t0_real(
                    "directional_persistence",
                    persistence,
                    "ratio",
                    window,
                    "vector_resultant_speed / mean_wind_speed, in [0,1] — 1.0 means the window's wind blew from one steady direction, near 0 means directions cancelled out; meteorological covariate only, NEVER 'disease spread confidence'",
                )
            )
    else:
        reason = "no hour had both wind_speed_10m and wind_direction_10m"
        results.append(_pre_t0_missing("mean_u10", "m/s", window, reason))
        results.append(_pre_t0_missing("mean_v10", "m/s", window, reason))
        results.append(_pre_t0_missing("mean_wind_speed", "m/s", window, reason))

    return window, results
