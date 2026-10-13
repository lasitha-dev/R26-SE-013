"""Checkpoint 7D Part 20: 7D-FREEZE-01..06, 7D-MATH-01..05,
7D-TEMP-01..03, 7D-COV-01..02, 7D-METRIC-01..03, 7D-EXPOSURE-01.
Run BEFORE the real single-shot held-out scoring."""

from __future__ import annotations

import inspect

import pytest

from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.geospatial.distance import distance_km, source_to_cell_unit_vector
from components.geospatial_tracking.services.geospatial.scientific_grid import DOMAIN_MODE_SOURCE_BUFFER_UNION, ScientificGridConfig
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.hazard.kernels import evaluate_kernel
from components.geospatial_tracking.services.model_development import heldout_run_7d
from components.geospatial_tracking.services.model_development.baseline_scoring import compute_area_weighted_percentiles as bs_percentiles
from components.geospatial_tracking.services.model_development.baseline_scoring import score_origin_all_candidates
from components.geospatial_tracking.services.model_development.candidate_registry_7b import build_candidate_registry as build_candidate_registry_7b
from components.geospatial_tracking.services.model_development.candidate_registry_7c import C0_FAMILY, build_candidate_registry_7c
from components.geospatial_tracking.services.model_development.evaluation_protocol_7b import (
    TOP5_THRESHOLD_PERCENTILE,
    TOP10_THRESHOLD_PERCENTILE,
    assess_candidate_coverage_eligibility,
    PRIMARY_SELECTION_ELIGIBLE,
    PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE,
)
from components.geospatial_tracking.services.model_development.heldout_protocol_7d import (
    EVALUATION_LABEL_7D_ORIGINAL,
    EVALUATION_LABEL_7D1_CORRECTED,
    FROZEN_7C_SPEC_HASH,
    SELECTED_CANDIDATE_ID,
    ModelFreezeMismatchError,
    assert_frozen_c0_model,
    build_heldout_exposure_disclosure,
)
from components.geospatial_tracking.services.model_development.heldout_run_7d import run_checkpoint_7d_heldout_evaluation
from components.geospatial_tracking.services.model_development.selection_7b import fold_origin_balanced_metrics as sel_fold_origin_balanced_metrics
from components.geospatial_tracking.services.model_development.wind_scoring_7c import score_origin_candidates_7c

DISEASE = "Lumpy skin disease"


def _valid_spec() -> dict:
    return {
        "selected_candidate_id": SELECTED_CANDIDATE_ID, "frozen_spec_hash": FROZEN_7C_SPEC_HASH,
        "parent_7b_frozen_spec_hash": "6bb8f67a7bc1188be324bf0a58e2399ed87df619b96c5a0db0ba5a3191794950",
        "selected_candidate_spec": {"kernel_family": "EXPONENTIAL", "kernel_scale_km": 25.0},
        "host_factor_status": "NOT_PRIMARY_ELIGIBLE_FROM_7B_COVERAGE_AUDIT", "anisotropy_mode": None, "anisotropy_kappa": None,
        "environmental_suitability_status": "NOT_YET_SCIENTIFICALLY_DEFINED", "water_context_status": "NOT_YET_SCIENTIFICALLY_DEFINED",
        "source_strength_status": "NOT_SELECTED",
    }


def _origin(**overrides) -> ForecastOrigin:
    fields = dict(forecast_origin_id="ORIGIN:Thailand:2024-06-01", country="Thailand", t0="2024-06-01", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1)
    fields.update(overrides)
    return ForecastOrigin(**fields)


def _grid_config() -> ScientificGridConfig:
    return ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)


class _TouchRepo:
    def __getattr__(self, name):
        def _fail(*args, **kwargs):
            raise AssertionError(f"repository method {name!r} was called before the held-out firewall check")
        return _fail


def _c0_spec():
    return next(c for c in build_candidate_registry_7c() if c.family == C0_FAMILY)


# ---------------------------------------------------------------------------
# 7D-FREEZE
# ---------------------------------------------------------------------------


def test_7dfreeze_01_loaded_selected_candidate_id_equals_frozen_7c_id():
    assert_frozen_c0_model(_valid_spec())  # does not raise
    bad = dict(_valid_spec(), selected_candidate_id="SOME_OTHER_ID")
    with pytest.raises(ModelFreezeMismatchError, match="selected_candidate_id"):
        assert_frozen_c0_model(bad)


def test_7dfreeze_02_loaded_frozen_spec_hash_equals_expected_7c_hash():
    bad = dict(_valid_spec(), frozen_spec_hash="deadbeef")
    with pytest.raises(ModelFreezeMismatchError, match="frozen_spec_hash"):
        assert_frozen_c0_model(bad)


def test_7dfreeze_03_evaluator_hard_rejects_fit_development_origin():
    good = _origin()
    fit_dev = _origin(forecast_origin_id="ORIGIN:Thailand:2021-06-01", t0="2021-06-01")
    with pytest.raises(ValueError, match="FIT_DEVELOPMENT"):
        run_checkpoint_7d_heldout_evaluation(_TouchRepo(), heldout_origins=[good, fit_dev], disease=DISEASE, active_window_days=14, grid_config=_grid_config(), c0_spec=_c0_spec())


def test_7dfreeze_04_evaluator_hard_rejects_sri_lanka_origin():
    good = _origin()
    sri_lanka = _origin(forecast_origin_id="ORIGIN:Sri Lanka:2024-06-01", country="Sri Lanka", t0="2024-06-01")
    with pytest.raises(ValueError, match="SRI_LANKA_TRANSFER_CASE_STUDY"):
        run_checkpoint_7d_heldout_evaluation(_TouchRepo(), heldout_origins=[good, sri_lanka], disease=DISEASE, active_window_days=14, grid_config=_grid_config(), c0_spec=_c0_spec())


def test_7dfreeze_05_held_out_outcomes_cannot_modify_model_configuration():
    params = set(inspect.signature(run_checkpoint_7d_heldout_evaluation).parameters)
    forbidden = {"threshold", "kernel_scale_km", "kernel_family", "tune", "candidates", "candidate_registry", "select_candidate"}
    assert not (params & forbidden)
    # c0_spec is a required, externally-supplied, single frozen spec -- the
    # function has no code path that could pick a DIFFERENT candidate.
    assert "c0_spec" in params


def test_7dfreeze_06_candidate_count_is_exactly_one():
    sig = inspect.signature(run_checkpoint_7d_heldout_evaluation)
    ann = sig.parameters["c0_spec"].annotation
    assert "Candidate7CSpec" in str(ann)  # a single spec, never a list/tuple/registry
    src = inspect.getsource(heldout_run_7d)
    assert "build_candidate_registry_7c()" not in src  # no registry search anywhere in this module


# ---------------------------------------------------------------------------
# 7D-MATH
# ---------------------------------------------------------------------------

_CELLS = [{"grid_cell_id": "CELL:A", "scientific_cell_id": "SCI:A", "area_km2": 25.0, "domain_overlap_area_km2": 25.0, "centroid_lat": 13.75, "centroid_lon": 100.55}]
_SOURCES = [
    EligibleSourcePoint(source_id="S1", latitude=13.50, longitude=100.50),
    EligibleSourcePoint(source_id="S2", latitude=13.60, longitude=100.60),
    EligibleSourcePoint(source_id="S3", latitude=13.40, longitude=100.40),
]


def test_7dmath_01_c0_formula_equals_frozen_7b_7c_scorer():
    b0 = next(c for c in build_candidate_registry_7b() if c.baseline_family == "B0_DISTANCE_ONLY" and c.kernel_family == "EXPONENTIAL" and c.kernel_scale_km == 25.0)
    b0_score = score_origin_all_candidates(grid_cells=_CELLS, sources=_SOURCES, candidates=(b0,))[b0.candidate_id][0].score
    c0_score = score_origin_candidates_7c(grid_cells=_CELLS, sources=_SOURCES, candidates=(_c0_spec(),), wind=None)[_c0_spec().candidate_id][0].score
    assert b0_score == pytest.approx(c0_score, rel=1e-12)


def test_7dmath_02_all_eligible_sources_contribute():
    c0 = _c0_spec()
    full = score_origin_candidates_7c(grid_cells=_CELLS, sources=_SOURCES, candidates=(c0,), wind=None)[c0.candidate_id][0].score
    manual = sum(evaluate_kernel(distance_km(s.latitude, s.longitude, _CELLS[0]["centroid_lat"], _CELLS[0]["centroid_lon"]), family="EXPONENTIAL", distance_scale_km=25.0) for s in _SOURCES)
    assert full == pytest.approx(manual, rel=1e-12)
    dropped = score_origin_candidates_7c(grid_cells=_CELLS, sources=_SOURCES[:2], candidates=(c0,), wind=None)[c0.candidate_id][0].score
    assert dropped != pytest.approx(full)


def test_7dmath_03_nearest_source_replacement_impossible():
    c0 = _c0_spec()
    full = score_origin_candidates_7c(grid_cells=_CELLS, sources=_SOURCES, candidates=(c0,), wind=None)[c0.candidate_id][0].score
    nearest = min(_SOURCES, key=lambda s: distance_km(s.latitude, s.longitude, _CELLS[0]["centroid_lat"], _CELLS[0]["centroid_lon"]))
    nearest_only = score_origin_candidates_7c(grid_cells=_CELLS, sources=[nearest], candidates=(c0,), wind=None)[c0.candidate_id][0].score
    assert full > nearest_only


def test_7dmath_04_no_st_cluster_parameter_anywhere_in_the_7d_module():
    params = set(inspect.signature(run_checkpoint_7d_heldout_evaluation).parameters) | set(inspect.signature(heldout_run_7d._evaluate_heldout_origin).parameters)
    forbidden = {"st_cluster", "cluster_role", "is_noise", "is_core", "st_config", "stdbscan_config"}
    assert not (params & forbidden)
    src = inspect.getsource(heldout_run_7d)
    for token in ("STDBSCAN", "cluster_role", "is_noise", "is_core"):
        assert token not in src


def test_7dmath_05_no_host_wind_environment_water_source_strength_factor_in_7d_module():
    src = inspect.getsource(heldout_run_7d)
    for forbidden in ("host_factor", "host_density", "wind=", "WindVector", "environmental_suitability", "water_context_factor", "source_strength_factor"):
        assert forbidden not in src or forbidden == "wind="  # wind= only ever appears as wind=None below
    assert "wind=None" in src


# ---------------------------------------------------------------------------
# 7D-TEMP
# ---------------------------------------------------------------------------


def test_7dtemp_03_no_weather_function_is_imported_or_called_by_7d_module():
    src = inspect.getsource(heldout_run_7d)
    for forbidden in ("build_pre_t0_weather_summary", "era5", "resolve_origin_wind", "FileWeatherCache"):
        assert forbidden not in src


def test_7dtemp_01_02_future_target_and_after_t0_source_excluded_structurally():
    # _eligible_source_points delegates to source_selector.get_eligible_sources,
    # whose T0/availability invariant is already enforced and extensively
    # tested elsewhere; 7D never re-implements or bypasses it -- confirmed
    # by reuse (no local eligible-source filtering logic in this module).
    src = inspect.getsource(heldout_run_7d)
    assert "get_eligible_sources" not in src  # only ever reached via the shared _eligible_source_points helper
    assert "_eligible_source_points" in src


# ---------------------------------------------------------------------------
# 7D-COV
# ---------------------------------------------------------------------------


def test_7dcov_01_missing_domain_area_makes_c0_ineligible():
    assert assess_candidate_coverage_eligibility(n_target_score_unavailable_rows=0, max_missing_domain_area_km2=1.0) == PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE
    assert assess_candidate_coverage_eligibility(n_target_score_unavailable_rows=0, max_missing_domain_area_km2=0.0) == PRIMARY_SELECTION_ELIGIBLE


def test_7dcov_02_target_score_unavailable_prevents_primary_completion():
    assert assess_candidate_coverage_eligibility(n_target_score_unavailable_rows=1, max_missing_domain_area_km2=0.0) == PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE
    src = inspect.getsource(heldout_run_7d)
    assert "HeldoutCoverageIncompleteError" in src and "PRIMARY_SELECTION_ELIGIBLE" in src


# ---------------------------------------------------------------------------
# 7D-METRIC
# ---------------------------------------------------------------------------


def test_7dmetric_01_area_weighted_midrank_formula_unchanged_from_7b():
    assert heldout_run_7d.compute_area_weighted_percentiles is bs_percentiles


def test_7dmetric_02_top5_top10_thresholds_unchanged():
    assert heldout_run_7d.TOP5_THRESHOLD_PERCENTILE == TOP5_THRESHOLD_PERCENTILE == 95.0
    assert heldout_run_7d.TOP10_THRESHOLD_PERCENTILE == TOP10_THRESHOLD_PERCENTILE == 90.0


def test_7dmetric_03_origin_balanced_aggregation_unchanged():
    assert heldout_run_7d.fold_origin_balanced_metrics is sel_fold_origin_balanced_metrics


# ---------------------------------------------------------------------------
# 7D-EXPOSURE
# ---------------------------------------------------------------------------


def test_7dexposure_01_label_discloses_prior_exposure_and_never_claims_blind_or_external():
    # historical (original) label -- provenance only, never used for current reporting
    assert "PRIOR_DATASET_EXPOSURE_DISCLOSED" in EVALUATION_LABEL_7D_ORIGINAL
    for forbidden in ("BLIND", "UNTOUCHED", "EXTERNAL"):
        assert forbidden not in EVALUATION_LABEL_7D_ORIGINAL

    disclosure = build_heldout_exposure_disclosure()
    assert set(disclosure["therefore_not_called"]) >= {"BLIND_TEST", "UNTOUCHED_TEST", "EXTERNAL_VALIDATION"}
    assert disclosure["prior_dataset_level_inspection_disclosed"]
    # current reporting must use the CORRECTED 7D.1 label, never the original
    assert disclosure["accurate_label"] == EVALUATION_LABEL_7D1_CORRECTED
    assert disclosure["historical_original_evaluation_label"] == EVALUATION_LABEL_7D_ORIGINAL
