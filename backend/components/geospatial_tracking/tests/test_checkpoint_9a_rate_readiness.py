"""Checkpoint 9A: apparent local spread-front rate methodology freeze,
development-data readiness, target-level de-pseudoreplication,
temporal/GPS quality audit, and zero-leakage S0 design.

READINESS/DATA-DERIVATION ONLY. No S0 aggregate value is computed or
frozen as the system rate anywhere in this file. No held-out/Sri Lanka
rate values are used. No direction/wind input enters any rate formula."""

from __future__ import annotations

import inspect

import pytest

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.geospatial.distance import distance_km
from components.geospatial_tracking.services.model_development import rate_readiness_9a
from components.geospatial_tracking.services.model_development.candidate_registry_7c import C0_FAMILY, build_candidate_registry_7c
from components.geospatial_tracking.services.model_development.development_run_7b import dedupe_targets_by_origin_and_event
from components.geospatial_tracking.services.model_development.local_evaluation_scope import PRIMARY_LOCAL_EVALUATION_DISTANCE_KM
from components.geospatial_tracking.services.model_development.rate_protocol_9a import (
    FROZEN_7C_SPEC_HASH_9A,
    FROZEN_C0_SELECTED_CANDIDATE_ID_9A,
    OUTSIDE_LOCAL_RATE_SCOPE_LABEL_9A,
    rate_readiness_protocol_dict_9a,
    rate_readiness_protocol_hash_9a,
)
from components.geospatial_tracking.services.model_development.rate_readiness_9a import (
    EXCLUDED_LEAD_DAYS_NOT_POSITIVE,
    ORIGIN_NO_ELIGIBLE_SOURCE,
    ORIGIN_READY,
    VALID,
    derive_fit_development_rate_observations,
    derive_origin_rate_observations,
    target_level_medians,
    valid_observations,
)

DISEASE = "Lumpy skin disease"


@pytest.fixture
def repo(tmp_path):
    r = SQLiteOutbreakRepository(tmp_path / "test.db")
    r.init_schema()
    yield r
    r.close()


def _historical(**overrides):
    fields = dict(
        country="Thailand", disease=DISEASE, outbreak_start_date="2021/01/03",
        proxy_availability_date="2021/01/03", proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        gps_quality=GpsQuality.EXACT.value, dedup_status=DedupStatus.AUTO_MERGED_HIGH.value, model_candidate=True,
    )
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


def _origin(*, forecast_origin_id, trigger_ids, t0, country="Thailand") -> ForecastOrigin:
    return ForecastOrigin(
        forecast_origin_id=forecast_origin_id, country=country, t0=t0, temporal_mode="RETROSPECTIVE_PROXY",
        trigger_source_ids_at_t0=list(trigger_ids), trigger_source_count=len(trigger_ids),
    )


class _TouchRepo:
    def __getattr__(self, name):
        def _fail(*args, **kwargs):
            raise AssertionError(f"repository method {name!r} was called before the FIT_DEVELOPMENT firewall check")
        return _fail


# ---------------------------------------------------------------------------
# 9A-FREEZE-01
# ---------------------------------------------------------------------------


def test_9a_freeze_01_frozen_c0_candidate_spec_unchanged():
    assert FROZEN_C0_SELECTED_CANDIDATE_ID_9A == "C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8"
    assert FROZEN_7C_SPEC_HASH_9A == "ef3511d3527da6d85598846c0d828509ed07f134ac8d987c3d5702b507505a6d"
    registry = build_candidate_registry_7c()
    c0 = next(c for c in registry if c.family == C0_FAMILY)
    assert c0.candidate_id == FROZEN_C0_SELECTED_CANDIDATE_ID_9A


# ---------------------------------------------------------------------------
# 9A-DIR-01/02, 9A-WIND-01: direction/wind cannot enter rate formula
# ---------------------------------------------------------------------------


def test_9a_dir_01_resultant_magnitude_cannot_enter_rate_formula():
    src = inspect.getsource(rate_readiness_9a)
    assert "resultant_magnitude" not in src
    assert "resultant_east" not in src and "resultant_north" not in src


def test_9a_dir_02_directional_clarity_cannot_enter_rate_formula():
    src = inspect.getsource(rate_readiness_9a)
    assert "directional_clarity" not in src
    assert "directional_input_coverage" not in src


def test_9a_wind_01_wind_speed_cannot_enter_rate_formula():
    import ast

    tree = ast.parse(inspect.getsource(rate_readiness_9a))
    direct_imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
    for forbidden in ("weather", "wind", "era5", "anisotropy", "direction"):
        assert not any(forbidden in m.lower() for m in direct_imports), direct_imports


# ---------------------------------------------------------------------------
# 9A-ROLE-01/02/03
# ---------------------------------------------------------------------------


def test_9a_role_01_fit_development_accepted(repo):
    repo.add_historical_record(_historical(source_record_id="A1", latitude=15.0, longitude=101.0))
    origin = _origin(forecast_origin_id="ORIGIN:Thailand:2021-01-05", trigger_ids=["A1"], t0="2021-01-05")
    result = derive_fit_development_rate_observations(repo, [origin], active_window_days=14)
    assert origin.forecast_origin_id in result
    assert result[origin.forecast_origin_id].status in (ORIGIN_READY, ORIGIN_NO_ELIGIBLE_SOURCE)


def test_9a_role_02_held_out_rejected_before_any_repository_access():
    held_out = _origin(forecast_origin_id="ORIGIN:Thailand:2024-06-01", trigger_ids=["X"], t0="2024-06-01")
    with pytest.raises(ValueError, match="HELD_OUT_FROM_MODEL_FITTING"):
        derive_fit_development_rate_observations(_TouchRepo(), [held_out], active_window_days=14)


def test_9a_role_03_sri_lanka_rejected_before_any_repository_access():
    sri_lanka = _origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-06-01", trigger_ids=["X"], t0="2020-06-01", country="Sri Lanka")
    with pytest.raises(ValueError, match="SRI_LANKA_TRANSFER_CASE_STUDY"):
        derive_fit_development_rate_observations(_TouchRepo(), [sri_lanka], active_window_days=14)


# ---------------------------------------------------------------------------
# 9A-TEMP-01/02/03
# ---------------------------------------------------------------------------


def test_9a_temp_01_lead_days_must_be_positive(repo):
    repo.add_historical_record(_historical(source_record_id="A1", latitude=15.0, longitude=101.0))
    repo.add_historical_record(_historical(
        source_record_id="T1", latitude=15.1, longitude=101.1,
        outbreak_start_date="2021/01/07", proxy_availability_date="2021/01/07",
    ))
    origin = _origin(forecast_origin_id="ORIGIN:Thailand:2021-01-05", trigger_ids=["A1"], t0="2021-01-05")
    outcome = derive_origin_rate_observations(repo, origin, active_window_days=14)
    for obs in outcome.observations:
        assert obs.lead_days > 0 or obs.observation_status == EXCLUDED_LEAD_DAYS_NOT_POSITIVE
    src = inspect.getsource(rate_readiness_9a)
    assert "t.lead_days <= 0" in src  # the defensive guard exists in source


def test_9a_temp_02_future_target_cannot_enter_t0_source_set(repo):
    repo.add_historical_record(_historical(source_record_id="A1", latitude=15.0, longitude=101.0))
    origin = _origin(forecast_origin_id="ORIGIN:Thailand:2021-01-05", trigger_ids=["A1"], t0="2021-01-05")
    outcome = derive_origin_rate_observations(repo, origin, active_window_days=14)
    assert outcome.status == ORIGIN_NO_ELIGIBLE_SOURCE or all(o.target_event_id != "A1" for o in outcome.observations)


def test_9a_temp_03_source_availability_after_t0_excluded(repo):
    repo.add_historical_record(_historical(source_record_id="A1", latitude=15.0, longitude=101.0))
    # a record available only AFTER t0 -- must never be treated as an eligible t0 source
    repo.add_historical_record(_historical(
        source_record_id="FUTURE_SRC", latitude=15.05, longitude=101.05,
        outbreak_start_date="2021/01/10", proxy_availability_date="2021/01/10",
    ))
    origin = _origin(forecast_origin_id="ORIGIN:Thailand:2021-01-05", trigger_ids=["A1"], t0="2021-01-05")
    outcome = derive_origin_rate_observations(repo, origin, active_window_days=14)
    assert outcome.n_eligible_sources == 1  # only A1, never FUTURE_SRC


# ---------------------------------------------------------------------------
# 9A-GEO-01/02/03
# ---------------------------------------------------------------------------


def test_9a_geo_01_d_min_is_geodesic_minimum_over_all_eligible_sources(repo):
    repo.add_historical_record(_historical(source_record_id="NEAR", latitude=15.0, longitude=101.0))
    repo.add_historical_record(_historical(source_record_id="FAR", latitude=16.0, longitude=102.0))
    repo.add_historical_record(_historical(
        source_record_id="T1", latitude=15.01, longitude=101.01,
        outbreak_start_date="2021/01/07", proxy_availability_date="2021/01/07",
    ))
    origin = _origin(forecast_origin_id="ORIGIN:Thailand:2021-01-05", trigger_ids=["NEAR"], t0="2021-01-05")
    outcome = derive_origin_rate_observations(repo, origin, active_window_days=14)
    assert outcome.n_eligible_sources == 2
    obs = next(o for o in outcome.observations if o.target_event_id == "T1")
    expected_min = min(distance_km(15.0, 101.0, 15.01, 101.01), distance_km(16.0, 102.0, 15.01, 101.01))
    assert obs.d_min_km == pytest.approx(expected_min)
    assert obs.nearest_source_id == "NEAR"


def test_9a_geo_02_nearest_source_labelled_geometric_reference_only(repo):
    repo.add_historical_record(_historical(source_record_id="A1", latitude=15.0, longitude=101.0))
    repo.add_historical_record(_historical(
        source_record_id="T1", latitude=15.01, longitude=101.01,
        outbreak_start_date="2021/01/07", proxy_availability_date="2021/01/07",
    ))
    origin = _origin(forecast_origin_id="ORIGIN:Thailand:2021-01-05", trigger_ids=["A1"], t0="2021-01-05")
    outcome = derive_origin_rate_observations(repo, origin, active_window_days=14)
    obs = next(o for o in outcome.observations if o.target_event_id == "T1")
    assert obs.nearest_source_role == "NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE"
    for forbidden in ("causal", "confirmed_transmission", "infection_origin"):
        assert forbidden not in obs.nearest_source_role.lower()


def test_9a_geo_03_no_degrees_as_km_implementation(repo):
    repo.add_historical_record(_historical(source_record_id="A1", latitude=10.0, longitude=100.0))
    repo.add_historical_record(_historical(
        source_record_id="T1", latitude=10.5, longitude=100.5,
        outbreak_start_date="2021/01/07", proxy_availability_date="2021/01/07",
    ))
    origin = _origin(forecast_origin_id="ORIGIN:Thailand:2021-01-05", trigger_ids=["A1"], t0="2021-01-05")
    outcome = derive_origin_rate_observations(repo, origin, active_window_days=14)
    obs = next(o for o in outcome.observations if o.target_event_id == "T1")
    naive_degree_distance = ((0.5) ** 2 + (0.5) ** 2) ** 0.5  # a naive "degrees as km" (wrong) value
    real_geodesic = distance_km(10.0, 100.0, 10.5, 100.5)
    assert obs.d_min_km == pytest.approx(real_geodesic)
    assert abs(obs.d_min_km - naive_degree_distance) > 1.0  # real geodesic km is nowhere near the naive degree number


# ---------------------------------------------------------------------------
# 9A-DEDUPE-01/02
# ---------------------------------------------------------------------------


def test_9a_dedupe_01_duplicate_cumulative_representation_contributes_once():
    from types import SimpleNamespace

    t1 = SimpleNamespace(forecast_origin_id="O1", target_event_id="EVT1", target_id="O1::EVT1")
    t1_dup = SimpleNamespace(forecast_origin_id="O1", target_event_id="EVT1", target_id="O1::EVT1")
    t2 = SimpleNamespace(forecast_origin_id="O1", target_event_id="EVT2", target_id="O1::EVT2")
    result = dedupe_targets_by_origin_and_event([t1, t1_dup, t2])
    assert len(result) == 2
    assert {t.target_event_id for t in result} == {"EVT1", "EVT2"}


def test_9a_dedupe_02_same_target_across_origins_multiple_observations_one_aggregation_unit(repo):
    repo.add_historical_record(_historical(source_record_id="A1", latitude=15.0, longitude=101.0))
    repo.add_historical_record(_historical(source_record_id="A2", latitude=15.02, longitude=101.02, outbreak_start_date="2021/01/04", proxy_availability_date="2021/01/04"))
    repo.add_historical_record(_historical(
        source_record_id="SHARED_EVT", latitude=15.01, longitude=101.01,
        outbreak_start_date="2021/01/08", proxy_availability_date="2021/01/08",
    ))
    origin1 = _origin(forecast_origin_id="ORIGIN:Thailand:2021-01-05", trigger_ids=["A1"], t0="2021-01-05")
    origin2 = _origin(forecast_origin_id="ORIGIN:Thailand:2021-01-06", trigger_ids=["A2"], t0="2021-01-06")
    outcomes = derive_fit_development_rate_observations(repo, [origin1, origin2], active_window_days=14)

    matches = [o for outcome in outcomes.values() for o in outcome.observations if o.target_event_id == "SHARED_EVT"]
    assert len(matches) == 2  # two independent derived observations (one per origin)
    assert {o.forecast_origin_id for o in matches} == {origin1.forecast_origin_id, origin2.forecast_origin_id}

    medians = target_level_medians(outcomes)
    assert "SHARED_EVT" in medians  # collapsed into exactly ONE aggregation unit


# ---------------------------------------------------------------------------
# 9A-S0-01/02
# ---------------------------------------------------------------------------


def test_9a_s0_01_target_level_v_is_median_of_valid_rows():
    from components.geospatial_tracking.services.model_development.rate_readiness_9a import RateObservation9A

    fake_outcome = type("O", (), {"observations": (
        RateObservation9A("O1", "EVT", "O1::EVT", 2, 10.0, 5.0, "WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE", VALID, "S1", "NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE", "EXACT", "UNIQUE_AMONG_RESOLVED", "EXACT", "EVENT_DATE_PROXY", False),
        RateObservation9A("O2", "EVT", "O2::EVT", 4, 40.0, 10.0, "WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE", VALID, "S2", "NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE", "EXACT", "UNIQUE_AMONG_RESOLVED", "EXACT", "EVENT_DATE_PROXY", False),
        RateObservation9A("O3", "EVT", "O3::EVT", 5, 45.0, 9.0, "WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE", VALID, "S3", "NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE", "EXACT", "UNIQUE_AMONG_RESOLVED", "EXACT", "EVENT_DATE_PROXY", False),
    )})()
    medians = target_level_medians({"O1": fake_outcome})
    assert medians["EVT"] == 9.0  # median of [5.0, 10.0, 9.0]


def test_9a_s0_02_future_s0_formula_is_median_across_unique_targets_not_raw_rows():
    d = rate_readiness_protocol_dict_9a()
    assert "MEDIAN of target_level_v across UNIQUE target_event_id" in d["future_s0_formula"]
    assert "never the median of raw origin-target rows" in d["future_s0_formula"]
    assert d["future_s0_status"] == "FORMULA_FROZEN_VALUE_NOT_YET_COMPUTED"
    # target_level_medians itself never returns a grand aggregate -- it is per-target only
    import inspect as _inspect

    src = _inspect.getsource(rate_readiness_9a)
    assert "def target_level_medians" in src
    assert "statistics.median(target_level_medians" not in src  # no S0 grand-median computed in 9A


# ---------------------------------------------------------------------------
# 9A-ZERO-01
# ---------------------------------------------------------------------------


def test_9a_zero_01_legitimate_zero_distance_retained_with_quality_metadata(repo):
    repo.add_historical_record(_historical(source_record_id="A1", latitude=15.0, longitude=101.0))
    # target at the EXACT same coordinates as the source -- legitimate zero-distance case
    repo.add_historical_record(_historical(
        source_record_id="T1", latitude=15.0, longitude=101.0,
        outbreak_start_date="2021/01/07", proxy_availability_date="2021/01/07",
    ))
    origin = _origin(forecast_origin_id="ORIGIN:Thailand:2021-01-05", trigger_ids=["A1"], t0="2021-01-05")
    outcome = derive_origin_rate_observations(repo, origin, active_window_days=14)
    obs = next(o for o in outcome.observations if o.target_event_id == "T1")
    assert obs.d_min_km == pytest.approx(0.0, abs=1e-9)
    assert obs.is_zero_distance is True
    assert obs.observation_status == VALID
    assert obs.v_obs_km_day == pytest.approx(0.0, abs=1e-9)  # never epsilon-substituted
    assert obs.target_gps_quality is not None  # quality metadata retained


# ---------------------------------------------------------------------------
# 9A-SCOPE-01/02
# ---------------------------------------------------------------------------


def test_9a_scope_01_25km_remains_operational_never_biological():
    assert PRIMARY_LOCAL_EVALUATION_DISTANCE_KM == 25.0
    d = rate_readiness_protocol_dict_9a()
    assert d["local_scope_identity"]["distance_km"] == 25.0
    assert "OPERATIONAL_LOCAL_EVALUATION_ENVELOPE" in d["local_scope_identity"]["semantics"]
    assert "BIOLOGICAL" not in d["local_scope_identity"]["semantics"] or "NEVER" in d["local_scope_identity"]["semantics"]


def test_9a_scope_02_outside_target_retained_in_audit_excluded_from_estimator(repo):
    repo.add_historical_record(_historical(source_record_id="A1", latitude=15.0, longitude=101.0))
    # a target ~200km away -- well outside the 25km envelope
    repo.add_historical_record(_historical(
        source_record_id="FAR_T1", latitude=16.8, longitude=101.0,
        outbreak_start_date="2021/01/07", proxy_availability_date="2021/01/07",
    ))
    origin = _origin(forecast_origin_id="ORIGIN:Thailand:2021-01-05", trigger_ids=["A1"], t0="2021-01-05")
    outcome = derive_origin_rate_observations(repo, origin, active_window_days=14)
    obs = next(o for o in outcome.observations if o.target_event_id == "FAR_T1")
    assert obs.observation_status == OUTSIDE_LOCAL_RATE_SCOPE_LABEL_9A  # retained, labelled
    assert obs.v_obs_km_day is None  # excluded from the primary local-rate estimator
    assert obs in outcome.observations  # never deleted from provenance


# ---------------------------------------------------------------------------
# 9A-OUTLIER-01
# ---------------------------------------------------------------------------


def test_9a_outlier_01_no_winsorization_clipping_path():
    src = inspect.getsource(rate_readiness_9a)
    for forbidden in ("winsoriz", "clip(", "np.clip", "log1p", "log(", "percentile_clip"):
        assert forbidden not in src.lower()


# ---------------------------------------------------------------------------
# 9A-HASH-01
# ---------------------------------------------------------------------------


def test_9a_hash_01_protocol_hash_deterministic_and_timestamp_free():
    d = rate_readiness_protocol_dict_9a()
    assert "generated_at" not in d
    assert "timestamp" not in d
    assert rate_readiness_protocol_hash_9a() == rate_readiness_protocol_hash_9a()


# ---------------------------------------------------------------------------
# 9A-REACH-01
# ---------------------------------------------------------------------------


def test_9a_reach_01_nominal_reach_cannot_alter_risk_or_target_eligibility():
    d = rate_readiness_protocol_dict_9a()
    assert d["nominal_reach_status"] == "NOT_YET_COMPUTED"
    formula = d["nominal_reach_formula"]
    for forbidden_effect in ("truncat", "target scope", "infection probability", "biological radius"):
        idx = formula.lower().find(forbidden_effect)
        if idx != -1:
            preceding = formula.lower()[max(0, idx - 20):idx]
            assert "never" in preceding
    # nominal reach must never be computed against real risk/target-eligibility state in 9A
    src = inspect.getsource(rate_readiness_9a)
    assert "nominal_reach" not in src.lower()


# ---------------------------------------------------------------------------
# Evidence-summary consistency (never skips) + local SHA256 verification
# ---------------------------------------------------------------------------


def test_9a_evidence_summary_internally_consistent():
    import json as _json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "CHECKPOINT_9A_EVIDENCE_SUMMARY.json"
    assert path.exists(), "CHECKPOINT_9A_EVIDENCE_SUMMARY.json must be tracked alongside source"
    d = _json.loads(path.read_text(encoding="utf-8"))

    assert d["rate_readiness_protocol_hash_9a"] == rate_readiness_protocol_hash_9a()
    assert d["frozen_c0_selected_candidate_id"] == FROZEN_C0_SELECTED_CANDIDATE_ID_9A
    assert d["s0_status"] == "FORMULA_FROZEN_VALUE_NOT_YET_COMPUTED"
    assert d["nominal_reach_status"] == "NOT_YET_COMPUTED"
    assert d["s1_status"] == "NOT_SELECTED_IN_CHECKPOINT_9A"
    assert d["not_final_system_rate"] is True
    assert d["held_out_and_sri_lanka_excluded"] is True

    audit = d["readiness_audit_summary"]
    assert audit["n_within_primary_local_scope"] + audit["n_outside_local_scope"] == audit["n_deduplicated_origin_target_observations"]
    assert audit["n_valid_v_obs_observations"] == audit["n_within_primary_local_scope"]


@pytest.mark.skipif(
    not (__import__("pathlib").Path(__file__).resolve().parents[4] / "local_data" / "model_development" / "9a_rate").exists(),
    reason="local_data/model_development/9a_rate absent (clean clone)",
)
def test_9a_local_artifacts_sha256_match_evidence_summary():
    import hashlib
    import json as _json
    from pathlib import Path

    evidence_path = Path(__file__).resolve().parents[1] / "CHECKPOINT_9A_EVIDENCE_SUMMARY.json"
    d = _json.loads(evidence_path.read_text(encoding="utf-8"))
    stored_hashes = d["local_artifact_sha256"]
    out_dir = Path(__file__).resolve().parents[4] / "local_data" / "model_development" / "9a_rate"

    for filename, expected in stored_hashes.items():
        local_path = out_dir / filename
        assert local_path.exists(), f"{filename} referenced in evidence summary but missing locally"
        actual = hashlib.sha256(local_path.read_bytes()).hexdigest()
        assert actual == expected, f"{filename}: stored {expected} != actual {actual}"
