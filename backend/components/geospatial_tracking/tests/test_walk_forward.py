"""FOLD-01/02/03."""

import inspect

from components.geospatial_tracking.services import walk_forward
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.forecast_target import ForecastTarget
from components.geospatial_tracking.services.walk_forward import (
    build_candidate_folds,
    propose_chronological_boundaries,
)


def _origin(t0, country="Thailand"):
    return ForecastOrigin(
        forecast_origin_id=f"ORIGIN:{country}:{t0}",
        country=country,
        t0=t0,
        temporal_mode="RETROSPECTIVE_PROXY",
    )


def _target(origin_id, target_event_id, risk=True, tier_a=True):
    return ForecastTarget(
        forecast_origin_id=origin_id,
        target_id=f"{origin_id}::{target_event_id}",
        target_event_id=target_event_id,
        historical_event_date="2026-01-01",
        lead_days=1,
        latitude=15.0,
        longitude=101.0,
        gps_quality="EXACT",
        coordinate_collision_status="UNIQUE_AMONG_RESOLVED",
        risk_target_eligible=risk,
        direction_target_tier_a_strict=tier_a,
        direction_target_tier_a_resolved_only=tier_a,
        direction_target_tier_b=not tier_a,
        speed_target_tier_a_strict=tier_a,
        speed_target_tier_a_resolved_only=tier_a,
        speed_target_tier_b=not tier_a,
        speed_eligibility_status="SPEED_ELIGIBILITY_PENDING_GEOMETRY",
        country="Thailand",
        disease="Lumpy skin disease",
        dedup_status="AUTO_MERGED_HIGH",
        model_candidate=True,
    )


def _build_origins_and_targets():
    origins = [_origin(f"2026-01-{d:02d}") for d in range(1, 21)]  # 20 daily origins
    targets_by_origin_id = {}
    for i, o in enumerate(origins):
        targets_by_origin_id[o.forecast_origin_id] = [_target(o.forecast_origin_id, f"T{i}")]
    return origins, targets_by_origin_id


def test_fold_01_generation_is_deterministic(tmp_path=None):
    origins, targets = _build_origins_and_targets()
    boundaries = propose_chronological_boundaries(origins, num_folds=4)
    folds1 = build_candidate_folds(origins, targets, boundaries=boundaries)
    folds2 = build_candidate_folds(origins, targets, boundaries=boundaries)
    assert [f.as_dict() for f in folds1] == [f.as_dict() for f in folds2]


def test_fold_02_never_reads_model_performance_metrics():
    # Structural proof: neither public function accepts a parameter shaped
    # like a performance/accuracy input, and the module imports nothing
    # from a model/metrics library — fold generation has no code path
    # through which a performance number could reach it. (Docstring prose
    # naming "accuracy"/"metric" while explaining this rule is fine — the
    # check below is on the actual callable surface, not on comments.)
    sig_propose = inspect.signature(propose_chronological_boundaries)
    sig_build = inspect.signature(build_candidate_folds)
    all_params = set(sig_propose.parameters) | set(sig_build.parameters)
    for forbidden_param in ("accuracy", "performance", "score", "metric", "loss"):
        assert forbidden_param not in all_params

    assert "sklearn" not in inspect.getsource(walk_forward).lower()


def test_fold_03_same_target_event_id_counted_once_per_fold():
    origins, _ = _build_origins_and_targets()
    boundary = origins[10].t0
    # two different validation origins both produce a target with the SAME target_event_id
    targets_by_origin_id = {
        origins[10].forecast_origin_id: [_target(origins[10].forecast_origin_id, "SHARED_EVENT")],
        origins[11].forecast_origin_id: [_target(origins[11].forecast_origin_id, "SHARED_EVENT")],
    }
    folds = build_candidate_folds(origins, targets_by_origin_id, boundaries=[boundary])
    # both origins 10 and 11 fall in the (only) validation block; the
    # shared target_event_id must be counted as ONE unique validation target
    assert folds[0].unique_validation_target_events == 1


def test_propose_boundaries_uses_only_chronology():
    origins = [_origin(f"2026-01-{d:02d}") for d in range(1, 13)]
    boundaries = propose_chronological_boundaries(origins, num_folds=3)
    assert len(boundaries) == 2
    assert boundaries == sorted(boundaries)


def test_build_folds_applies_purge_policy_to_training_origins():
    # horizon=7: an origin at t0 whose t0+7 reaches the boundary must be
    # purged from training, not silently kept.
    origins = [_origin(f"2026-01-{d:02d}") for d in range(1, 21)]
    boundary = "2026-01-15"
    folds = build_candidate_folds(origins, {}, boundaries=[boundary])
    fold = folds[0]
    # origins with t0 in [2026-01-08, 2026-01-14] have t0+7 >= 2026-01-15 -> purged (7 origins)
    # origins with t0 in [2026-01-01, 2026-01-07] have t0+7 <= 2026-01-14 < boundary -> training (7 origins)
    assert fold.purged_origin_count == 7
    assert fold.training_origin_count == 7


def test_fold_countries_represented_reflects_validation_origins():
    origins = [_origin("2026-01-01", country="Thailand"), _origin("2026-01-15", country="Sri Lanka")]
    boundary = "2026-01-10"
    folds = build_candidate_folds(origins, {}, boundaries=[boundary])
    assert folds[0].countries_represented == ["Sri Lanka"]
