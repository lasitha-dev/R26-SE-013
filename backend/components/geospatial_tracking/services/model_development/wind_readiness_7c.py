"""Checkpoint 7C Part 7: real, t0-safe AOI-center wind acquisition for one
forecast origin.

Reuses the EXISTING weather adapter (`services.geospatial.weather.era5.build_pre_t0_weather_summary`)
exactly as `services.features.assembler.assemble_feature_snapshot` already
calls it for the primary historical path -- `t0_precision=DATE_ONLY`
(this corpus's real precision, `services.geospatial.weather.base.T0Precision`),
`strict_operational_availability=False`, `model="era5"`. No new weather
fetch/parse logic is written here. The AOI center itself reuses the same
rule `assemble_feature_snapshot._aoi_center` already uses (centroid of
the origin's own trigger sources, falling back to the centroid of every
eligible source) -- imported directly rather than re-derived, so 7C's
AOI-center definition can never silently drift from 6A's.

Missing wind (`BLOCKED`/`MISSING` u10 or v10) is `WEATHER_INPUT_UNAVAILABLE`
(Part 18) -- never replaced with 0 m/s, north, or a previous value.

**Checkpoint 7C.1 Part 7 (temporal-role hardening)**: a REAL primary wind
vector requires the EXACT `PRIMARY_WEATHER_TEMPORAL_ROLE_7C`
(`RETROSPECTIVE_REANALYSIS_STATE_PROXY`) -- `UNKNOWN` never admits a
wind vector as REAL primary input, even if `u10`/`v10` happen to carry
`REAL`-looking values, and is instead reported as
`WEATHER_TEMPORAL_ROLE_UNAVAILABLE`. In the current `era5.py`
implementation `temporal_role=UNKNOWN` only occurs alongside every
result already `BLOCKED` (unresolved timezone boundary / unsupported
model), so this never actually admitted a real REAL-status wind in the
completed 579-origin run -- this is a structural hardening, proven
never to have changed a real result (7C-TEMP-01..03,
`n_origins_unknown_temporal_role_with_real_wind == 0` in the real-run
audit)."""

from __future__ import annotations

from dataclasses import dataclass

from ..features.assembler import _aoi_center
from ..geospatial.source_geometry import EligibleSourcePoint
from ..geospatial.weather.base import T0Precision
from ..geospatial.weather.era5 import build_pre_t0_weather_summary
from ..hazard.contracts import WindVector
from .evaluation_protocol_7c import (
    PRIMARY_WEATHER_TEMPORAL_ROLE_7C,
    STRICT_OPERATIONAL_AVAILABILITY_7C,
    WEATHER_INPUT_UNAVAILABLE,
    WEATHER_LOOKBACK_HOURS_7C,
    WEATHER_MODEL_7C,
)

WEATHER_TEMPORAL_ROLE_UNAVAILABLE = "WEATHER_TEMPORAL_ROLE_UNAVAILABLE"
REAL = "REAL"


@dataclass(frozen=True)
class OriginWindResult:
    forecast_origin_id: str
    wind: WindVector | None
    status: str  # REAL | WEATHER_INPUT_UNAVAILABLE | WEATHER_TEMPORAL_ROLE_UNAVAILABLE
    aoi_latitude: float | None
    aoi_longitude: float | None
    aoi_anchor_source_ids: tuple
    window_dict: dict | None


def resolve_origin_wind(
    *, forecast_origin_id: str, t0: str, trigger_source_ids_at_t0: list, sources: list[EligibleSourcePoint], weather_cache,
) -> OriginWindResult:
    if not sources:
        return OriginWindResult(forecast_origin_id, None, WEATHER_INPUT_UNAVAILABLE, None, None, (), None)

    aoi_lat, aoi_lon, anchor_ids = _aoi_center(sources, trigger_source_ids_at_t0)
    window, results = build_pre_t0_weather_summary(
        latitude=aoi_lat, longitude=aoi_lon, t0=t0, t0_precision=T0Precision.DATE_ONLY.value,
        lookback_hours=WEATHER_LOOKBACK_HOURS_7C, model=WEATHER_MODEL_7C,
        strict_operational_availability=STRICT_OPERATIONAL_AVAILABILITY_7C, cache=weather_cache,
    )
    if window.temporal_role != PRIMARY_WEATHER_TEMPORAL_ROLE_7C:
        # Part 7: UNKNOWN (or any other non-exact role) can never become a
        # REAL primary wind input -- explicit block, never a permissive
        # assertion that would let an ambiguous role slip through.
        return OriginWindResult(forecast_origin_id, None, WEATHER_TEMPORAL_ROLE_UNAVAILABLE, aoi_lat, aoi_lon, tuple(anchor_ids), window.as_dict())

    by_name = {r.feature_name: r for r in results}
    u10_fr, v10_fr = by_name.get("mean_u10"), by_name.get("mean_v10")
    if u10_fr is None or v10_fr is None or u10_fr.status != REAL or v10_fr.status != REAL:
        return OriginWindResult(forecast_origin_id, None, WEATHER_INPUT_UNAVAILABLE, aoi_lat, aoi_lon, tuple(anchor_ids), window.as_dict())

    wind = WindVector(u10=u10_fr.value, v10=v10_fr.value)
    return OriginWindResult(forecast_origin_id, wind, REAL, aoi_lat, aoi_lon, tuple(anchor_ids), window.as_dict())
