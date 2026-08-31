"""Checkpoint 3 configuration.

Two development parameters live here. Both are explicitly labeled
UNFROZEN_DEVELOPMENT_PARAMETER — neither is a claimed scientific or
biological constant, and neither is used as a silent default inside the
functions that need them: `get_eligible_sources` and
`aggregate_reports_into_episodes` both REQUIRE their window/gap argument
to be passed explicitly by the caller. The values below exist only for
local development convenience (e.g. the Checkpoint 3 smoke test) and must
never be cited as scientifically justified without later evidence.
"""

from __future__ import annotations

UNFROZEN_DEVELOPMENT_PARAMETER = "UNFROZEN_DEVELOPMENT_PARAMETER"

ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT = 14
"""Development-only convenience value for `active_window_days` in
`services.source_selector.get_eligible_sources`. NOT scientifically
validated. Callers must pass a value explicitly — this is not read as an
implicit default by that function."""

EPISODE_GAP_DAYS_DEV_DEFAULT = 30
"""Development-only convenience value for `episode_gap_days` in
`services.aggregation.aggregate_reports_into_episodes` — an OPERATIONAL
aggregation rule (how far apart two reports at the same farm must be
before they're treated as separate outbreak episodes), not a claimed
epidemiological incubation/recovery constant. NOT scientifically
validated. Callers must pass a value explicitly."""

WEATHER_LOOKBACK_HOURS_DEV_DEFAULT = 24
"""Development-only convenience value for `lookback_hours` in
`services.geospatial.weather.era5.build_pre_t0_weather_summary` (Checkpoint
5.5) — the previous completed 24 hours before a historical t0. NOT a claimed
epidemiologically optimal window; candidate lookback durations are future
development-fold work. Callers must pass a value explicitly."""

DEFAULT_SQLITE_DB_PATH = "data/local/pistes_dev.db"
"""Relative to `components/geospatial_tracking/`. Development persistence
only (master-prompt §6) — gitignored, never committed. See
REPOSITORY_DESIGN.md."""
