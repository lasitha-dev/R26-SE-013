"""FMD-07B minimum executable set: structural readiness only.

No test in this module fits a model, scores a real/synthetic origin, calculates
a candidate metric, or opens an FMD dataset.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from components.geospatial_tracking.services.fmd_model_development_7b import (
    DEPENDENCY_REQUIREMENT,
    DEVELOPMENT_METRICS_GENERATED,
    FMD07B_BLOCKED,
    FMD07B_EXECUTABLE_SELECTION_ELIGIBLE,
    FMD07B_MINIMUM_EXECUTABLE_COMPARISON_SET_READY,
    HELD_OUT_USED,
    MINIMUM_EXECUTABLE_EXPERIMENT_IDS,
    REAL_TRAINING_RUN,
    REGISTERED_EXPERIMENT_IDS,
    REQUIRED_SKLEARN_VERSION,
    SRI_LANKA_USED,
    build_fmd_spatial_candidate_specs,
    build_minimum_candidate_runners,
    build_ml_candidate_specs,
    build_ml_estimator_runner,
    build_naive_statistical_runner,
    build_runner,
    build_spatial_distance_runner,
    registered_candidate_eligibility,
    structural_readiness_audit,
    validate_fmd07b_fold_input,
)
from components.geospatial_tracking.services.fmd_model_development_r1 import (
    build_ml_candidate_registry,
    build_spatial_baseline_kernel_scale_registry,
)
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.model_fitting_exposure import CalendarYearFold
from components.geospatial_tracking.services.model_development.baseline_registry import (
    BASELINE_CANDIDATES,
    KERNEL_CANDIDATE_FAMILIES,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]


def _origin(origin_id: str, country: str, t0: str) -> ForecastOrigin:
    return ForecastOrigin(
        forecast_origin_id=origin_id,
        country=country,
        t0=t0,
        temporal_mode="HISTORICAL_REPLAY",
    )


def _synthetic_fold() -> tuple[list[ForecastOrigin], CalendarYearFold]:
    origins = [
        _origin("ORIGIN:TRAIN", "India", "2020-06-01"),
        _origin("ORIGIN:PURGED", "India", "2020-12-28"),
        _origin("ORIGIN:VALIDATION", "India", "2021-06-01"),
    ]
    fold = CalendarYearFold(
        fold_id="FOLD:2021",
        validation_year=2021,
        training_date_range_end="2021-01-01",
        validation_date_range_start="2021-01-01",
        validation_date_range_end="2021-12-31",
        training_origin_ids=["ORIGIN:TRAIN"],
        validation_origin_ids=["ORIGIN:VALIDATION"],
        purged_origin_ids=["ORIGIN:PURGED"],
    )
    return origins, fold


def test_fmd07b_dependency_is_observed_exact_version_and_explicitly_declared():
    import sklearn

    assert sklearn.__version__ == REQUIRED_SKLEARN_VERSION == "1.8.0"
    assert DEPENDENCY_REQUIREMENT == "scikit-learn==1.8.0"
    requirements = (_REPO_ROOT / "backend/requirements.txt").read_text(encoding="utf-8")
    assert requirements.splitlines().count(DEPENDENCY_REQUIREMENT) == 1


def test_fmd07b_registered_universe_and_minimum_runners_are_exact_and_deterministic():
    assert REGISTERED_EXPERIMENT_IDS == (
        "FMD-EXP-01",
        "FMD-EXP-02",
        "FMD-EXP-03",
        "FMD-EXP-04",
        "FMD-EXP-05",
    )
    first = build_minimum_candidate_runners()
    second = build_minimum_candidate_runners()
    assert tuple(first) == MINIMUM_EXECUTABLE_EXPERIMENT_IDS
    assert tuple(second) == MINIMUM_EXECUTABLE_EXPERIMENT_IDS
    assert first["FMD-EXP-01"].candidate.as_dict() == second["FMD-EXP-01"].candidate.as_dict()
    assert [c.as_dict() for c in first["FMD-EXP-02"].candidates] == [
        c.as_dict() for c in second["FMD-EXP-02"].candidates
    ]
    assert [c.as_dict() for c in first["FMD-EXP-04"].candidates] == [
        c.as_dict() for c in second["FMD-EXP-04"].candidates
    ]


def test_fmd07b_naive_runner_is_instantiable_without_fitting():
    runner = build_naive_statistical_runner()
    assert runner.candidate.experiment_id == "FMD-EXP-01"
    assert runner.candidate.registry_status == "FULLY_SPECIFIED"
    assert runner.candidate.output_semantics == "COUNTRY_HISTORICAL_OCCURRENCE_RATE"
    assert callable(runner.fit_training_fold)


def test_fmd07b_spatial_composition_matches_complete_frozen_fmd_registry():
    registry = build_spatial_baseline_kernel_scale_registry()
    candidates = build_fmd_spatial_candidate_specs()
    expected_count = len(BASELINE_CANDIDATES) * len(KERNEL_CANDIDATE_FAMILIES) * len(
        registry["candidate_kernel_scale_km"]
    )
    assert len(candidates) == expected_count == registry["total_candidate_grid"]["total"]
    assert {candidate.baseline_family for candidate in candidates} == {
        candidate.family for candidate in BASELINE_CANDIDATES
    }
    assert {candidate.kernel_family for candidate in candidates} == set(KERNEL_CANDIDATE_FAMILIES)
    assert {candidate.kernel_scale_km for candidate in candidates} == set(
        registry["candidate_kernel_scale_km"]
    )
    assert all(candidate.candidate_id.startswith("FMD07B:SPATIAL:") for candidate in candidates)
    assert callable(build_spatial_distance_runner().score_validation_origin)


def test_fmd07b_ml_candidate_expansion_matches_frozen_registry_exactly():
    frozen = build_ml_candidate_registry()
    candidates = build_ml_candidate_specs()
    assert len(candidates) == frozen["total_hyperparameter_candidate_count"] == 11
    by_family = {}
    for candidate in candidates:
        by_family.setdefault(candidate.algorithm_family, []).append(candidate.hyperparameter_dict())
    assert set(by_family) == {entry["algorithm_family"] for entry in frozen["candidates"]}
    assert len(by_family["LOGISTIC_REGRESSION"]) == 3
    assert len(by_family["RANDOM_FOREST"]) == 4
    assert len(by_family["GRADIENT_BOOSTED_TREES"]) == 4
    assert all(candidate.random_seed == 42 for candidate in candidates)
    assert all(candidate.candidate_id.startswith("FMD07B:ML:") for candidate in candidates)


def test_fmd07b_ml_pipelines_are_fresh_unfitted_and_train_fold_safe_by_construction():
    runner = build_ml_estimator_runner()
    seen_families = set()
    for candidate in runner.candidates:
        if candidate.algorithm_family in seen_families:
            continue
        seen_families.add(candidate.algorithm_family)
        pipeline = runner.build_unfitted_pipeline(candidate.candidate_id)
        estimator = pipeline.named_steps["estimator"]
        assert estimator.random_state == 42
        assert not hasattr(estimator, "classes_")
        if candidate.algorithm_family == "LOGISTIC_REGRESSION":
            assert isinstance(estimator, LogisticRegression)
            assert isinstance(pipeline.named_steps["imputer"], SimpleImputer)
            assert pipeline.named_steps["imputer"].strategy == "median"
            assert isinstance(pipeline.named_steps["scaler"], StandardScaler)
            assert not hasattr(pipeline.named_steps["imputer"], "statistics_")
            assert not hasattr(pipeline.named_steps["scaler"], "mean_")
        elif candidate.algorithm_family == "RANDOM_FOREST":
            assert isinstance(estimator, RandomForestClassifier)
            assert isinstance(pipeline.named_steps["imputer"], SimpleImputer)
            assert pipeline.named_steps["imputer"].strategy == "median"
            assert "scaler" not in pipeline.named_steps
            assert not hasattr(pipeline.named_steps["imputer"], "statistics_")
        else:
            assert isinstance(estimator, HistGradientBoostingClassifier)
            assert tuple(pipeline.named_steps) == ("estimator",)


def test_fmd07b_chronological_fold_is_accepted_without_model_execution():
    origins, fold = _synthetic_fold()
    validated = validate_fmd07b_fold_input(origins, fold)
    assert validated.fold_id == "FOLD:2021"
    assert validated.training_origin_ids == ("ORIGIN:TRAIN",)
    assert validated.validation_origin_ids == ("ORIGIN:VALIDATION",)
    assert validated.purged_origin_ids == ("ORIGIN:PURGED",)
    assert validated.firewall_status == "FIT_DEVELOPMENT_ONLY"


@pytest.mark.parametrize(
    ("country", "t0"),
    [
        ("India", "2026-02-01"),
        ("Sri Lanka", "2021-06-01"),
    ],
)
def test_fmd07b_fold_firewall_rejects_held_out_and_sri_lanka(country, t0):
    origins, fold = _synthetic_fold()
    origins.append(_origin("ORIGIN:FORBIDDEN", country, t0))
    with pytest.raises(ValueError, match="non-FIT_DEVELOPMENT"):
        validate_fmd07b_fold_input(origins, fold)


def test_fmd07b_pistes_and_hybrid_remain_registered_blocked_and_non_executable():
    eligibility = registered_candidate_eligibility()
    assert eligibility["FMD-EXP-03"]["registry_status"] == "BLOCKED"
    assert eligibility["FMD-EXP-03"]["eligibility"] == FMD07B_BLOCKED
    assert eligibility["FMD-EXP-05"]["registry_status"] == "BLOCKED_BY_PISTES"
    assert eligibility["FMD-EXP-05"]["eligibility"] == FMD07B_BLOCKED
    for experiment_id in ("FMD-EXP-03", "FMD-EXP-05"):
        with pytest.raises(RuntimeError, match="has no FMD-07B executable runner"):
            build_runner(experiment_id)
    for experiment_id in MINIMUM_EXECUTABLE_EXPERIMENT_IDS:
        assert eligibility[experiment_id]["eligibility"] == FMD07B_EXECUTABLE_SELECTION_ELIGIBLE


def test_fmd07b_readiness_audit_proves_no_training_data_or_metrics_were_used():
    audit = structural_readiness_audit()
    assert audit["naive_ready"] is True
    assert audit["spatial_ready"] is True
    assert audit["ml_ready"] is True
    assert audit["dependency_declared"] is True
    assert audit["minimum_candidate_set_ready"] is True
    assert audit["held_out_used"] is HELD_OUT_USED is False
    assert audit["sri_lanka_used"] is SRI_LANKA_USED is False
    assert audit["real_training_run"] is REAL_TRAINING_RUN is False
    assert audit["development_metrics_generated"] is DEVELOPMENT_METRICS_GENERATED is False
    assert audit["readiness_token"] == FMD07B_MINIMUM_EXECUTABLE_COMPARISON_SET_READY
