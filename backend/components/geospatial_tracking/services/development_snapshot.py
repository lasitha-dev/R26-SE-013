"""Strict development-only source snapshots.

This module composes the existing model-fitting exposure firewall with the
existing historical source-snapshot implementation.  It deliberately owns no
role-classification or temporal-filtering rules of its own.
"""

from __future__ import annotations

from ..repositories.base import OutbreakRepository
from .forecast_origin import ForecastOrigin, SourceSnapshot, build_source_snapshot
from .model_fitting_exposure import assert_fit_development_only


def build_fit_development_source_snapshots(
    repo: OutbreakRepository,
    forecast_origins: list[ForecastOrigin],
    *,
    disease: str,
    active_window_days: int,
    cutoff: str,
) -> list[SourceSnapshot]:
    """Build one temporal source snapshot per development forecast origin.

    Callers select development origins with
    :func:`model_fitting_exposure.fit_development_origins`.  This entry point
    independently enforces the hard firewall before repository access, so a
    held-out or case-study origin is rejected instead of being silently
    filtered from a mixed input list.

    ``cutoff`` is required explicitly so a disease-specific workflow cannot
    accidentally inherit another workflow's cutoff.  Snapshot time semantics
    remain those of :func:`forecast_origin.build_source_snapshot`: source
    availability at or before ``t0`` may enter the requested active window,
    while availability after ``t0`` cannot enter.
    """
    assert_fit_development_only(
        forecast_origins,
        cutoff=cutoff,
        caller="build_fit_development_source_snapshots",
    )
    return [
        build_source_snapshot(
            repo,
            origin,
            disease=disease,
            active_window_days=active_window_days,
        )
        for origin in forecast_origins
    ]
