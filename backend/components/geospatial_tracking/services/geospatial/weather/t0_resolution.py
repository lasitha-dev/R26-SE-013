"""Checkpoint 5.6 Parts 4-7: timezone-safe t0 boundary resolution.

The single point every pre-t0 weather-eligibility decision in this
package goes through. Two corrections from Checkpoint 5.5:

1. **`DATE_ONLY` t0 is the AOI's own SOURCE-LOCAL CIVIL DATE, not an
   unconditional UTC date.** Checkpoint 5.5 always used midnight UTC —
   defensible only if the source date field is itself explicitly a UTC
   calendar date, which this corpus's `outbreak_start_date` fields are
   not (they are civil dates in whatever timezone the outbreak was
   reported in). The real IANA timezone for an AOI is resolved OFFLINE
   via `timezonefinder`'s polygon lookup (`resolve_iana_timezone`) —
   never a hardcoded per-country UTC offset, and never a network call
   (so this module is directly, deterministically pytest-testable).

2. **Historical UTC offset, not today's UTC offset.** Once a real IANA
   name is known, `zoneinfo.ZoneInfo` + Python's `datetime` compute the
   HISTORICAL offset actually in force on the specific t0 date — this
   matters concretely, not hypothetically: Sri Lanka's real UTC offset
   was different before ~2006 (+6:00, per IANA tzdata) than it is today
   (+5:30). A naive "always +5:30 for Sri Lanka" rule, or trusting a
   convenience API's "current offset" field, would silently misdate
   every pre-2006 record by up to 30 minutes. (Confirmed empirically:
   Open-Meteo's own `timezone=auto` convenience parameter returns
   `utc_offset_seconds=19800` — today's +5:30 — even when queried for a
   2000-06-01 date, i.e. it does NOT apply period-specific historical
   offsets. `zoneinfo` does. This is why timezone NAME resolution and
   historical OFFSET computation are kept as two separate steps here —
   the name can safely come from a coordinate-only lookup, but the
   offset must come from `zoneinfo` + the actual historical date.)

If no IANA timezone can be defensibly resolved for a coordinate (open
ocean, disputed/uncovered polygon), the boundary is NOT silently
resolved as UTC — `T0Boundary.resolved` is `False` and callers must
treat that as `BLOCKED`, never a fabricated cutoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from timezonefinder import TimezoneFinder

from .base import T0Precision

# Loaded once, offline (bundled polygon data) — no network call, so every
# function below is deterministic and pytest-safe without mocking.
_finder = TimezoneFinder()


def resolve_iana_timezone(latitude: float, longitude: float) -> str | None:
    """Offline, deterministic real IANA timezone name for a coordinate
    (e.g. `"Asia/Colombo"`), via `timezonefinder`'s LAND-polygon lookup
    (`timezone_at_land`, not `timezone_at`). This distinction matters:
    plain `timezone_at` falls back to conventional "Etc/GMT+N" ocean
    zones for every open-ocean point and even the poles, so it never
    returns `None` — which would make "timezone cannot be defensibly
    resolved" untestable and would silently accept a bogus/corrupted
    coordinate (this pipeline's domain is livestock, always terrestrial)
    as if it had a real observed civil calendar. `timezone_at_land`
    correctly returns `None` for a genuine non-land coordinate, which
    this pipeline treats as BLOCKED rather than resolved."""
    return _finder.timezone_at_land(lat=latitude, lng=longitude)


@dataclass(frozen=True)
class T0Boundary:
    t0_precision: str
    source_local_date: str | None
    source_timezone: str | None
    t0_timezone_quality: str
    t0_start_local: str | None
    cutoff_utc: datetime | None
    resolved: bool
    quality_notes: str

    def as_dict(self) -> dict:
        return {
            "t0_precision": self.t0_precision,
            "source_local_date": self.source_local_date,
            "source_timezone": self.source_timezone,
            "t0_timezone_quality": self.t0_timezone_quality,
            "t0_start_local": self.t0_start_local,
            "cutoff_utc": self.cutoff_utc.isoformat() if self.cutoff_utc else None,
            "resolved": self.resolved,
            "quality_notes": self.quality_notes,
        }


def resolve_t0_boundary(*, t0: str, t0_precision: str, latitude: float, longitude: float) -> T0Boundary:
    """`DATE_ONLY`: resolves the AOI's real IANA timezone offline, builds
    local midnight of `t0`'s calendar date in that timezone, converts to
    UTC via `zoneinfo` (historically accurate for that exact date).
    `TIMESTAMP`: trusts an explicit UTC offset if present; a naive input
    is used but stamped `ASSUMED_UTC_NAIVE_TIMESTAMP_INPUT` (explicit,
    never a silent default)."""
    if t0_precision == T0Precision.DATE_ONLY.value:
        date_part = t0[:10]
        tz_name = resolve_iana_timezone(latitude, longitude)
        if tz_name is None:
            return T0Boundary(
                t0_precision=t0_precision,
                source_local_date=date_part,
                source_timezone=None,
                t0_timezone_quality="UNKNOWN",
                t0_start_local=None,
                cutoff_utc=None,
                resolved=False,
                quality_notes=(
                    f"no IANA timezone polygon found for ({latitude}, {longitude}) — cannot defensibly "
                    "establish a source-local-midnight cutoff; refusing to silently assume UTC"
                ),
            )
        local_midnight = datetime.fromisoformat(date_part).replace(tzinfo=ZoneInfo(tz_name))
        cutoff_utc = local_midnight.astimezone(timezone.utc)
        return T0Boundary(
            t0_precision=t0_precision,
            source_local_date=date_part,
            source_timezone=tz_name,
            t0_timezone_quality="RESOLVED",
            t0_start_local=local_midnight.isoformat(),
            cutoff_utc=cutoff_utc,
            resolved=True,
            quality_notes=(
                f"source-local midnight in {tz_name} converted to UTC via zoneinfo, using the historically "
                "correct offset for this specific date (not necessarily today's offset)"
            ),
        )
    if t0_precision == T0Precision.TIMESTAMP.value:
        dt = datetime.fromisoformat(t0)
        if dt.tzinfo is not None:
            cutoff_utc = dt.astimezone(timezone.utc)
            quality = "EXPLICIT_OFFSET"
            notes = f"exact timestamp with explicit UTC offset {dt.utcoffset()} converted to UTC"
        else:
            cutoff_utc = dt.replace(tzinfo=timezone.utc)
            quality = "ASSUMED_UTC_NAIVE_TIMESTAMP_INPUT"
            notes = "naive timestamp (no tzinfo) — explicitly ASSUMED UTC, never a silent default"
        return T0Boundary(
            t0_precision=t0_precision,
            source_local_date=None,
            source_timezone=None,
            t0_timezone_quality=quality,
            t0_start_local=None,
            cutoff_utc=cutoff_utc,
            resolved=True,
            quality_notes=notes,
        )
    raise ValueError(f"unknown t0_precision {t0_precision!r}; expected {T0Precision.DATE_ONLY.value!r} or {T0Precision.TIMESTAMP.value!r}")


def is_timestamp_eligible(ts: datetime, t0_precision: str, cutoff: datetime) -> bool:
    """`DATE_ONLY` -> strictly before cutoff. `TIMESTAMP` -> at or before
    cutoff. Unchanged rule from Checkpoint 5.5 — now always fed a
    historically-correct, timezone-resolved cutoff rather than a bare
    UTC-midnight assumption."""
    if t0_precision == T0Precision.DATE_ONLY.value:
        return ts < cutoff
    if t0_precision == T0Precision.TIMESTAMP.value:
        return ts <= cutoff
    raise ValueError(f"unknown t0_precision {t0_precision!r}")


def pre_t0_window_bounds(boundary: T0Boundary, lookback_hours: float) -> tuple[datetime | None, datetime | None]:
    """`(window_start, cutoff)`. Both `None` when `boundary.resolved` is
    `False` — callers must treat that as BLOCKED, never substitute a
    fabricated window."""
    if not boundary.resolved or boundary.cutoff_utc is None:
        return None, None
    window_start = boundary.cutoff_utc - timedelta(hours=lookback_hours)
    return window_start, boundary.cutoff_utc
