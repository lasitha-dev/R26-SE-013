"""SPLIT-6B-01..06."""

from __future__ import annotations

import random

from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.model_fitting_exposure import (
    FIT_DEVELOPMENT,
    HELD_OUT_FROM_MODEL_FITTING,
    MODEL_FITTING_CUTOFF,
    SRI_LANKA_TRANSFER_CASE_STUDY,
    build_calendar_year_folds,
    build_model_fitting_exposure_manifest,
    classify_origin_role,
    fit_development_origins,
)


def _origin(**overrides) -> ForecastOrigin:
    fields = dict(
        forecast_origin_id="ORIGIN:Thailand:2021-06-01",
        country="Thailand",
        t0="2021-06-01",
        temporal_mode="RETROSPECTIVE_PROXY",
        trigger_source_ids_at_t0=["X1"],
        trigger_source_count=1,
    )
    fields.update(overrides)
    return ForecastOrigin(**fields)


def test_split_6b_01_before_cutoff_non_sri_lanka_is_fit_development():
    origin = _origin(t0="2023-12-31", country="Thailand")
    assert classify_origin_role(origin) == FIT_DEVELOPMENT


def test_split_6b_01_sri_lanka_before_cutoff_is_still_case_study():
    origin = _origin(t0="2020-09-09", country="Sri Lanka", forecast_origin_id="ORIGIN:Sri Lanka:2020-09-09")
    assert classify_origin_role(origin) == SRI_LANKA_TRANSFER_CASE_STUDY


def test_split_6b_02_at_or_after_cutoff_is_held_out():
    origin_at = _origin(t0=MODEL_FITTING_CUTOFF, country="Thailand")
    origin_after = _origin(t0="2024-06-15", country="Thailand")
    assert classify_origin_role(origin_at) == HELD_OUT_FROM_MODEL_FITTING
    assert classify_origin_role(origin_after) == HELD_OUT_FROM_MODEL_FITTING


def test_split_6b_03_sri_lanka_after_cutoff_also_case_study():
    origin = _origin(t0="2025-01-01", country="Sri Lanka")
    assert classify_origin_role(origin) == SRI_LANKA_TRANSFER_CASE_STUDY


def test_split_6b_04_held_out_origins_excluded_from_fit_development_origins():
    origins = [
        _origin(forecast_origin_id="A", t0="2023-01-01", country="Thailand"),
        _origin(forecast_origin_id="B", t0="2024-01-01", country="Thailand"),
        _origin(forecast_origin_id="C", t0="2020-01-01", country="Sri Lanka"),
    ]
    dev = fit_development_origins(origins)
    dev_ids = {o.forecast_origin_id for o in dev}
    assert dev_ids == {"A"}
    assert "B" not in dev_ids  # held-out
    assert "C" not in dev_ids  # Sri Lanka


def test_split_6b_04_calendar_year_folds_never_contain_held_out_or_sri_lanka():
    origins = [
        _origin(forecast_origin_id=f"DEV_{y}", t0=f"{y}-06-01", country="Thailand")
        for y in (2019, 2020, 2021, 2022, 2023)
    ] + [
        _origin(forecast_origin_id="HELDOUT_2024", t0="2024-06-01", country="Thailand"),
        _origin(forecast_origin_id="SL_2020", t0="2020-06-01", country="Sri Lanka"),
    ]
    folds = build_calendar_year_folds(origins)
    all_ids_in_folds = set()
    for fold in folds:
        all_ids_in_folds.update(fold.training_origin_ids)
        all_ids_in_folds.update(fold.validation_origin_ids)
        all_ids_in_folds.update(fold.purged_origin_ids)
    assert "HELDOUT_2024" not in all_ids_in_folds
    assert "SL_2020" not in all_ids_in_folds


def test_split_6b_05_seven_day_purge_boundary_equality_is_purged():
    # origin t0 exactly 7 days before the boundary -> t0 + 7 == boundary -> purged (>=)
    boundary_year = 2023
    origins = [
        _origin(forecast_origin_id="EXACT7", t0="2022-12-25", country="Thailand"),  # +7d = 2023-01-01
        _origin(forecast_origin_id="EXACT8", t0="2022-12-24", country="Thailand"),  # +7d = 2022-12-31, safe
        # a real 2023 origin so the FOLD:2023 validation year actually
        # gets built (build_calendar_year_folds only creates folds for
        # years that have at least one eligible development origin)
        _origin(forecast_origin_id="VAL2023", t0="2023-03-01", country="Thailand"),
    ]
    folds = build_calendar_year_folds(origins)
    fold_2023 = next(f for f in folds if f.validation_year == boundary_year)
    assert "EXACT7" in fold_2023.purged_origin_ids
    assert "EXACT7" not in fold_2023.training_origin_ids
    assert "EXACT8" in fold_2023.training_origin_ids
    assert "EXACT8" not in fold_2023.purged_origin_ids


def test_split_6b_06_no_random_shuffle_folds_are_deterministic():
    origins = [
        _origin(forecast_origin_id=f"O{i}", t0=f"2021-{(i % 12) + 1:02d}-01", country="Thailand") for i in range(20)
    ]
    shuffled = list(origins)
    random.Random(42).shuffle(shuffled)

    folds_a = build_calendar_year_folds(origins)
    folds_b = build_calendar_year_folds(shuffled)

    assert [f.as_dict() for f in folds_a] == [f.as_dict() for f in folds_b]


def test_manifest_reports_every_origin_reason_never_hidden():
    origins = [
        _origin(forecast_origin_id="A", t0="2023-01-01", country="Thailand"),
        _origin(forecast_origin_id="B", t0="2024-06-01", country="Thailand"),
        _origin(forecast_origin_id="C", t0="2020-01-01", country="Sri Lanka"),
    ]
    manifest = build_model_fitting_exposure_manifest(origins)
    assert len(manifest) == 3
    for row in manifest:
        assert row.reason  # never empty/hidden
