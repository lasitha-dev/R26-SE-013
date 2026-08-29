"""Checkpoint 9A: real FIT_DEVELOPMENT apparent local spread-front rate
observation derivation -- DATA READINESS ONLY.

Computes per-(origin, target) `v_obs = d_min / lead_days` and target-
level medians using the exact already-frozen project primitives
(`get_eligible_sources`, `build_forecast_targets`,
`dedupe_targets_by_origin_and_event`, `classify_target_primary_scope`)
-- no new distance/eligibility/dedup logic is (re)implemented here.
Does NOT compute or freeze the final S0 aggregate median as the system
rate -- that is Checkpoint 9B.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from ...domain.enums import RecordDomainScope
from ...schemas import ValidationMode
from ..forecast_origin import ForecastOrigin
from ..forecast_target import build_forecast_targets
from ..geospatial.source_geometry import EligibleSourcePoint
from ..model_fitting_exposure import assert_fit_development_only
from ..source_selector import EligibleSource, get_eligible_sources
from .development_run_7b import dedupe_targets_by_origin_and_event
from .local_evaluation_scope import (
    LOCAL_SCOPE_UNRESOLVED,
    OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE,
    WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE,
    classify_target_primary_scope,
)
from .rate_protocol_9a import DISEASE_9A, OUTSIDE_LOCAL_RATE_SCOPE_LABEL_9A

ORIGIN_NO_ELIGIBLE_SOURCE = "ORIGIN_NO_ELIGIBLE_SOURCE"
ORIGIN_READY = "ORIGIN_READY"

VALID = "VALID"
EXCLUDED_LEAD_DAYS_NOT_POSITIVE = "EXCLUDED_LEAD_DAYS_NOT_POSITIVE"
EXCLUDED_LOCAL_SCOPE_UNRESOLVED = "EXCLUDED_LOCAL_SCOPE_UNRESOLVED"


@dataclass(frozen=True)
class RateObservation9A:
    forecast_origin_id: str
    target_event_id: str
    target_id: str
    lead_days: int
    d_min_km: float | None
    v_obs_km_day: float | None
    scope_status: str  # WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE | OUTSIDE_DECLARED_LOCAL_RATE_SCOPE | LOCAL_SCOPE_UNRESOLVED
    observation_status: str  # VALID | OUTSIDE_DECLARED_LOCAL_RATE_SCOPE | EXCLUDED_LEAD_DAYS_NOT_POSITIVE | EXCLUDED_LOCAL_SCOPE_UNRESOLVED
    nearest_source_id: str | None
    nearest_source_role: str  # NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE, never causal
    target_gps_quality: str | None
    target_coordinate_collision_status: str | None
    nearest_source_gps_quality: str | None
    nearest_source_availability_quality: str | None
    is_zero_distance: bool

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id, "target_event_id": self.target_event_id,
            "target_id": self.target_id, "lead_days": self.lead_days, "d_min_km": self.d_min_km,
            "v_obs_km_day": self.v_obs_km_day, "scope_status": self.scope_status,
            "observation_status": self.observation_status, "nearest_source_id": self.nearest_source_id,
            "nearest_source_role": self.nearest_source_role, "target_gps_quality": self.target_gps_quality,
            "target_coordinate_collision_status": self.target_coordinate_collision_status,
            "nearest_source_gps_quality": self.nearest_source_gps_quality,
            "nearest_source_availability_quality": self.nearest_source_availability_quality,
            "is_zero_distance": self.is_zero_distance,
        }


@dataclass(frozen=True)
class OriginRateOutcome9A:
    forecast_origin_id: str
    status: str  # ORIGIN_READY | ORIGIN_NO_ELIGIBLE_SOURCE
    n_eligible_sources: int
    source_gps_qualities: tuple
    source_availability_qualities: tuple
    n_raw_target_rows: int
    n_not_risk_eligible_excluded: int  # Part 12/18: dedup/conflict/coordinate/date-quality ineligibility, applied via the existing frozen rule
    n_after_dedup: int  # rows remaining after (forecast_origin_id, target_event_id) dedup, before observation derivation
    observations: tuple  # RateObservation9A


def _eligible_sources_9a(repo, origin: ForecastOrigin, *, active_window_days: int) -> list[EligibleSource]:
    """The EXACT existing eligible-active-source selector -- same call
    shape `development_run_7b._eligible_source_points` already uses,
    but keeping the full `EligibleSource` records (not just id/lat/lon)
    so GPS/availability quality can be reported (Part 12)."""
    result = get_eligible_sources(
        repo, disease=DISEASE_9A, t0=origin.t0, active_window_days=active_window_days,
        temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, country_scope=origin.country,
        domain_scope=RecordDomainScope.HISTORICAL_ONLY,
    )
    return result.sources


def derive_origin_rate_observations(repo, origin: ForecastOrigin, *, active_window_days: int) -> OriginRateOutcome9A:
    """FIT_DEVELOPMENT-only (caller must have already filtered origins
    via `assert_fit_development_only`). Derives real `v_obs` observations
    for one origin -- never computes/returns a target-level or S0
    aggregate (that happens once, across all origins, in the caller)."""
    eligible = _eligible_sources_9a(repo, origin, active_window_days=active_window_days)
    if not eligible:
        return OriginRateOutcome9A(origin.forecast_origin_id, ORIGIN_NO_ELIGIBLE_SOURCE, 0, (), (), 0, 0, 0, ())

    source_points = [EligibleSourcePoint(source_id=s.source_id, latitude=s.latitude, longitude=s.longitude) for s in eligible]
    by_source_id = {s.source_id: s for s in eligible}

    targets = build_forecast_targets(repo, origin, disease=DISEASE_9A, source_ids_at_origin={s.source_id for s in eligible}, horizon_days=7)
    n_raw = len(targets)
    risk_eligible_targets = [t for t in targets if t.risk_target_eligible]
    n_not_risk_eligible = n_raw - len(risk_eligible_targets)
    targets = dedupe_targets_by_origin_and_event(risk_eligible_targets)
    n_after_dedup = len(targets)

    observations: list[RateObservation9A] = []
    for t in targets:
        scope = classify_target_primary_scope(target=t, sources=source_points)
        d_min = scope.min_distance_to_eligible_source_km
        nearest = by_source_id.get(scope.nearest_source_id) if scope.nearest_source_id else None

        if scope.scope_status == LOCAL_SCOPE_UNRESOLVED:
            observations.append(RateObservation9A(
                origin.forecast_origin_id, t.target_event_id, t.target_id, t.lead_days, d_min, None,
                LOCAL_SCOPE_UNRESOLVED, EXCLUDED_LOCAL_SCOPE_UNRESOLVED, scope.nearest_source_id,
                "NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE", t.gps_quality, t.coordinate_collision_status,
                nearest.gps_quality if nearest else None, nearest.availability_quality if nearest else None, False,
            ))
            continue

        if scope.scope_status == OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE:
            observations.append(RateObservation9A(
                origin.forecast_origin_id, t.target_event_id, t.target_id, t.lead_days, d_min, None,
                OUTSIDE_LOCAL_RATE_SCOPE_LABEL_9A, OUTSIDE_LOCAL_RATE_SCOPE_LABEL_9A, scope.nearest_source_id,
                "NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE", t.gps_quality, t.coordinate_collision_status,
                nearest.gps_quality if nearest else None, nearest.availability_quality if nearest else None,
                d_min is not None and d_min == 0.0,
            ))
            continue

        # WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE
        if t.lead_days <= 0:
            observations.append(RateObservation9A(
                origin.forecast_origin_id, t.target_event_id, t.target_id, t.lead_days, d_min, None,
                WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE, EXCLUDED_LEAD_DAYS_NOT_POSITIVE, scope.nearest_source_id,
                "NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE", t.gps_quality, t.coordinate_collision_status,
                nearest.gps_quality if nearest else None, nearest.availability_quality if nearest else None, False,
            ))
            continue

        v_obs = d_min / t.lead_days
        observations.append(RateObservation9A(
            origin.forecast_origin_id, t.target_event_id, t.target_id, t.lead_days, d_min, v_obs,
            WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE, VALID, scope.nearest_source_id,
            "NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE", t.gps_quality, t.coordinate_collision_status,
            nearest.gps_quality if nearest else None, nearest.availability_quality if nearest else None,
            d_min == 0.0,
        ))

    return OriginRateOutcome9A(
        origin.forecast_origin_id, ORIGIN_READY, len(eligible),
        tuple(s.gps_quality for s in eligible), tuple(s.availability_quality for s in eligible),
        n_raw, n_not_risk_eligible, n_after_dedup, tuple(observations),
    )


def derive_fit_development_rate_observations(repo, fit_development_origins: list[ForecastOrigin], *, active_window_days: int) -> dict:
    """Top-level entry point. Hard-rejects any non-FIT_DEVELOPMENT origin
    BEFORE any repository access (Part 6). Returns `{forecast_origin_id:
    OriginRateOutcome9A}` -- callers aggregate target-level medians and
    diagnostics; this function computes no S0."""
    assert_fit_development_only(fit_development_origins, caller="derive_fit_development_rate_observations")
    return {o.forecast_origin_id: derive_origin_rate_observations(repo, o, active_window_days=active_window_days) for o in fit_development_origins}


def valid_observations(outcomes: dict) -> list[RateObservation9A]:
    """Every `VALID` (WITHIN-scope, lead_days>0, v_obs computed)
    observation across all origins -- raw origin-target rows, NOT yet
    de-pseudoreplicated."""
    return [obs for outcome in outcomes.values() for obs in outcome.observations if obs.observation_status == VALID]


def target_level_medians(outcomes: dict) -> dict[str, float]:
    """Part 9 (frozen): `target_level_v(target_event_id) = MEDIAN` of
    every valid FIT_DEVELOPMENT `v_obs` associated with that unique
    `target_event_id` -- collapses pseudo-replication from the same
    real outbreak appearing as a future target for multiple forecast
    origins. This is the ONLY function that may compute a per-target
    median; it never computes a grand median-of-medians (that is
    Checkpoint 9B's frozen S0 estimator, not derived here)."""
    by_target: dict[str, list[float]] = {}
    for obs in valid_observations(outcomes):
        by_target.setdefault(obs.target_event_id, []).append(obs.v_obs_km_day)
    return {target_event_id: statistics.median(values) for target_event_id, values in by_target.items()}
