"""Checkpoint 5 Part 16: temporal-leakage guard functions.

Pure, standalone checks that catch the exact leakage patterns the
master prompt names explicitly: (1) WorldCover 2021 used for a 2020
forecast target, (2) FAO GLW treated as exact/current livestock truth,
(3) future-dated ERA5-Land reanalysis (D+1..D+7) leaking into a primary
prediction. No model or training loop exists yet — these are guards for
callers (this checkpoint's smoke tests, and later PISTES feature
assembly) to run, not a policy decision made here.
"""

from __future__ import annotations


def landcover_year_mismatches_forecast_year(dataset_version_label: str, forecast_year: str) -> bool:
    """True if a WorldCover result's `dataset_version` (e.g.
    "v200 (2021)") was produced for a different year than the forecast
    target year. WorldCover only ships two years (2020/2021), so a
    mismatch is not automatically forbidden here — but it must always be
    flagged, never silently treated as time-matched ground truth."""
    return forecast_year not in dataset_version_label


def host_density_used_as_exact_truth(temporal_role: str) -> bool:
    """True if a host-density result's temporal_role is anything other
    than STATIC_REFERENCE_PROXY — GLW (reference year 2015) must never
    be presented as an exact, time-matched livestock census for any
    other year."""
    return temporal_role != "STATIC_REFERENCE_PROXY"


def weather_leaks_future_information(temporal_role: str) -> bool:
    """True if a weather result's temporal_role is
    REALIZED_FUTURE_REANALYSIS — i.e. reanalysis for a date after the
    forecast origin (D+1..D+7 or any future-relative date) being
    treated as if it were available at prediction time. Such values
    must never enter a primary deployable feature set."""
    return temporal_role == "REALIZED_FUTURE_REANALYSIS"
