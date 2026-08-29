"""Checkpoint 5/5.5/5.6: historical-weather adapter interface + the
critical valid-time vs. availability-time distinction.

**Historical ERA5 data is HISTORICAL_REANALYSIS. It is NEVER a live
operational weather forecast** — a future live deployment needs a
genuinely separate LIVE WEATHER ADAPTER (not built here; only this
interface exists so a later implementation has something to conform to —
`LiveWeatherAdapter` below is a stub Protocol, never called).

**PERMANENT RULE (Checkpoint 5.6): PRE-T0 REANALYSIS VALID TIME IS NOT
THE SAME AS REAL-TIME DATA AVAILABILITY.** A weather value's
METEOROLOGICAL VALID TIME (the instant the value describes) and its
DATA AVAILABILITY TIME (when that reanalysis value was actually
published/computable) are different questions. ERA5 is a *retrospective*
reanalysis: even a value whose valid time is "before t0" was, in most
real historical cases, not literally computed and published until weeks
or months after that valid time (ERA5's preliminary release, ERA5T, is
published ~5 days after each day; the quality-controlled final ERA5 is
published ~2 months later — official ECMWF/Copernicus documentation,
confirmed 2026-08-19, not assumed from memory; see `era5.py`'s
`ERA5T_PRELIMINARY_LAG_DAYS`). Checkpoint 5.5's wording ("information a
real deployed forecaster would have had") OVERSTATED this — it
conflated "meteorologically dated before t0" with "operationally
available by t0," which are not the same claim and were never
established as the same claim.

Two SEPARATE safety questions, both explicit from Checkpoint 5.6 on:

- **A. METEOROLOGICAL VALID-TIME SAFETY** — was this weather value's
  own valid_time strictly before t0? (`is_timestamp_eligible`,
  `t0_resolution.py`.) Passing A does NOT automatically imply B.
- **B. OPERATIONAL AVAILABILITY SAFETY** — was this exact reanalysis
  value actually published/computable by t0? Unknown by default
  (`WeatherAvailabilityQuality.UNKNOWN`) — a `LAG_RULE_PROXY` value is
  only produced when the caller explicitly opts into the documented,
  citation-backed ERA5T conservative-lag sensitivity mode
  (`strict_operational_availability=True` in
  `build_pre_t0_weather_summary`). Never `ACTUAL`: no exact historical
  publication timestamp is fabricated anywhere in this pipeline.

`WeatherTemporalRole.RETROSPECTIVE_REANALYSIS_STATE_PROXY` (renamed from
Checkpoint 5.5's `OBSERVED_REANALYSIS_AT_T0` — the old name is exactly
the overclaim being corrected) is the accurate label for the PRIMARY
historical research mode: a retrospective environmental-state proxy
whose meteorological valid timestamps are limited to pre-t0
observations, acceptable for retrospective environmental modeling, but
never proof that the exact historical real-time weather pipeline would
have produced identical inputs — the future production system will use
a genuinely separate, live operational weather source
(`LiveWeatherAdapter` below).

**Temporal leakage rule (unchanged in substance):** weather dated AFTER
t0 is `REALIZED_FUTURE_REANALYSIS` — what actually happened, which an
operational forecaster at t0 could not have known regardless of the
availability-time question above. Using `REALIZED_FUTURE_REANALYSIS` as
if it were a normal input feature for primary historical model
validation is a textbook leakage bug. This module's concrete adapter
(`era5.py`) enforces this as a hard gate, not just a docstring warning:
fetching a `REALIZED_FUTURE_REANALYSIS` result requires the caller to
pass `allow_future_reanalysis=True` explicitly, and every such result is
stamped `temporal_role=REALIZED_FUTURE_REANALYSIS` so it can never be
silently mistaken for a t0-legitimate feature downstream.

No historically-available FORECAST archive (as opposed to reanalysis) is
implemented in this checkpoint — for primary deployable-like historical
modeling, D+1..D+7 weather beyond t0 is simply unavailable
(`FeatureStatus.MISSING`/`BLOCKED`) unless the caller explicitly opts into
`REALIZED_FUTURE_REANALYSIS` for clearly-labeled retrospective
sensitivity/oracle analysis (`ENVIRONMENTAL_FEATURE_PROTOCOL.md`).

**Checkpoint 5.5/5.6: date-level t0 is not the same as knowing an entire
calendar day's weather, and "midnight" is not timezone-free.**
`T0Precision` records how precisely a historical forecast origin is
actually known:

- `DATE_ONLY` — only the calendar date is known (the common case for
  this corpus's `outbreak_start_date`/`proxy_availability_date`
  fields). Checkpoint 5.6 correction: this calendar date is the AOI's
  own SOURCE-LOCAL CIVIL DATE, not an unconditional UTC date. The cutoff
  is midnight in the AOI's real, offline-resolved IANA timezone
  (`t0_resolution.resolve_iana_timezone` — never a hardcoded per-country
  offset), converted to UTC via `zoneinfo` for the *specific historical
  date* (which correctly applies a historical offset change if one
  occurred — verified empirically for Sri Lanka, whose real UTC offset
  differed before ~2006 from today's). If no IANA timezone can be
  defensibly resolved for a coordinate, the cutoff is NOT silently
  assumed as UTC — the result is unresolved and callers must treat it as
  BLOCKED (`t0_resolution.T0Boundary.resolved=False`).
- `TIMESTAMP` — an exact instant is known. An explicit UTC offset on the
  input is trusted; a naive (offset-less) input is still usable but
  explicitly stamped `ASSUMED_UTC_NAIVE_TIMESTAMP_INPUT` — never a
  silent default.

Enforced by `t0_resolution.py`'s `resolve_t0_boundary`/
`is_timestamp_eligible` (TIMEZONE-01..06, TIMEWX-01..05).
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol


class WeatherTemporalRole(str, Enum):
    RETROSPECTIVE_REANALYSIS_STATE_PROXY = "RETROSPECTIVE_REANALYSIS_STATE_PROXY"
    OPERATIONALLY_AVAILABLE_REANALYSIS = "OPERATIONALLY_AVAILABLE_REANALYSIS"
    REALIZED_FUTURE_REANALYSIS = "REALIZED_FUTURE_REANALYSIS"
    LIVE_OPERATIONAL = "LIVE_OPERATIONAL"
    UNKNOWN = "UNKNOWN"


class WeatherAvailabilityQuality(str, Enum):
    """Answers safety question B (operational availability), separate
    from A (meteorological valid-time). `ACTUAL` is never produced by
    this pipeline — no exact historical ERA5/ERA5T publication timestamp
    is known or fabricated anywhere in it."""

    ACTUAL = "ACTUAL"
    LAG_RULE_PROXY = "LAG_RULE_PROXY"
    UNKNOWN = "UNKNOWN"


class T0Precision(str, Enum):
    DATE_ONLY = "DATE_ONLY"
    TIMESTAMP = "TIMESTAMP"


class LiveWeatherAdapter(Protocol):
    """Stub interface only — no implementation exists yet. A future live
    deployment's weather source (an operational forecast feed, not
    reanalysis) must implement this separately; it must never reuse the
    historical reanalysis adapter's code path, since the temporal-role/
    leakage/availability semantics above do not apply to a genuine live
    forecast (a live feed's availability time and valid time are, by
    definition, both "now")."""

    def fetch_live(self, *, latitude: float, longitude: float) -> list:
        ...
