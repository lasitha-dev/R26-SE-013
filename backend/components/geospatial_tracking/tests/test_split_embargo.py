"""SPLIT-01/02, PURGE-01..04."""

import inspect

from components.geospatial_tracking.services import (
    aggregation,
    forecast_origin,
    forecast_target,
    historical_trigger,
    source_selector,
    split_embargo,
)
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.split_embargo import (
    AT_OR_AFTER_BOUNDARY,
    BEFORE_BOUNDARY,
    PURGED_7_DAY_HORIZON_POLICY,
    assess_embargo,
    assess_validation_block,
    embargoed_before_origins,
)


def _origin(t0):
    return ForecastOrigin(
        forecast_origin_id=f"ORIGIN:Thailand:{t0}",
        country="Thailand",
        t0=t0,
        temporal_mode="RETROSPECTIVE_PROXY",
    )


def test_split_01_no_random_shuffling_anywhere_in_the_service_layer():
    modules = [aggregation, forecast_origin, forecast_target, historical_trigger, source_selector, split_embargo]
    for module in modules:
        src = inspect.getsource(module)
        assert "import random" not in src
        assert "train_test_split" not in src
        assert "np.random" not in src
        assert "shuffle(" not in src


def test_split_02_origin_well_before_boundary_is_not_embargoed():
    # boundary 2026-02-01, horizon 7 -> window_end must stay < boundary
    origin = _origin("2026-01-01")  # window_end = 2026-01-08, well clear
    results = assess_embargo([origin], boundary="2026-02-01")
    assert results[0].partition == BEFORE_BOUNDARY
    assert results[0].embargoed is False


def test_split_02_origin_whose_window_reaches_boundary_is_embargoed():
    # boundary 2026-01-10, horizon 7 -> t0=2026-01-05 gives window_end=2026-01-12 >= boundary
    origin = _origin("2026-01-05")
    results = assess_embargo([origin], boundary="2026-01-10")
    assert results[0].partition == BEFORE_BOUNDARY
    assert results[0].embargoed is True
    assert results[0].target_window_end == "2026-01-12"


def test_split_02_origin_whose_window_ends_exactly_at_boundary_is_embargoed():
    # inclusive: window_end == boundary counts as reaching it
    origin = _origin("2026-01-03")  # window_end = 2026-01-10 == boundary
    results = assess_embargo([origin], boundary="2026-01-10")
    assert results[0].embargoed is True


def test_split_02_origin_at_or_after_boundary_is_never_embargoed():
    origin = _origin("2026-01-10")  # t0 == boundary -> AT_OR_AFTER_BOUNDARY
    results = assess_embargo([origin], boundary="2026-01-10")
    assert results[0].partition == AT_OR_AFTER_BOUNDARY
    assert results[0].embargoed is False


def test_embargoed_before_origins_filters_correctly():
    origins = [_origin("2026-01-01"), _origin("2026-01-05"), _origin("2026-01-10")]
    embargoed = embargoed_before_origins(origins, boundary="2026-01-10")
    assert {a.forecast_origin_id for a in embargoed} == {"ORIGIN:Thailand:2026-01-05"}


class TestFrozenPurgePolicy:
    """PURGE-01..04 — the frozen PURGED_7_DAY_HORIZON_POLICY rule."""

    def test_purge_01_t0_plus_7_before_boundary_stays_in_earlier_partition(self):
        # boundary 2026-01-20, t0=2026-01-10 -> t0+7=2026-01-17 < boundary
        origin = _origin("2026-01-10")
        results = assess_embargo([origin], boundary="2026-01-20")
        assert results[0].partition == BEFORE_BOUNDARY
        assert results[0].embargoed is False

    def test_purge_02_t0_plus_7_equal_to_boundary_is_purged(self):
        # boundary 2026-01-17, t0=2026-01-10 -> t0+7=2026-01-17 == boundary
        origin = _origin("2026-01-10")
        results = assess_embargo([origin], boundary="2026-01-17")
        assert results[0].partition == BEFORE_BOUNDARY
        assert results[0].embargoed is True

    def test_purge_03_t0_plus_7_after_boundary_is_purged(self):
        # boundary 2026-01-15, t0=2026-01-10 -> t0+7=2026-01-17 > boundary
        origin = _origin("2026-01-10")
        results = assess_embargo([origin], boundary="2026-01-15")
        assert results[0].embargoed is True

    def test_purged_origin_is_never_clipped_and_kept_as_normal_training(self):
        # The policy is "purge the whole origin", never "truncate its
        # horizon and pretend it's a clean training origin" — this module
        # exposes only a boolean embargoed flag, never a partial/clipped
        # target-window substitute.
        import dataclasses

        from components.geospatial_tracking.services.split_embargo import EmbargoAssessment

        field_names = {f.name for f in dataclasses.fields(EmbargoAssessment)}
        assert "clipped_target_window_end" not in field_names
        assert "truncated" not in field_names

    def test_purge_04_validation_targets_stay_inside_finite_validation_block(self):
        # block [2026-02-01, 2026-02-10], horizon 7:
        # - t0=2026-02-01 -> window_end=2026-02-08 <= E -> complete
        # - t0=2026-02-05 -> window_end=2026-02-12 > E -> incomplete, excluded
        # - t0=2026-01-25 -> before block_start -> not part of this block at all
        origins = [_origin("2026-01-25"), _origin("2026-02-01"), _origin("2026-02-05")]
        results = assess_validation_block(origins, block_start="2026-02-01", block_end="2026-02-10")
        result_ids = {r.forecast_origin_id: r for r in results}
        assert "ORIGIN:Thailand:2026-01-25" not in result_ids  # not part of the block
        assert result_ids["ORIGIN:Thailand:2026-02-01"].complete is True
        assert result_ids["ORIGIN:Thailand:2026-02-05"].complete is False

    def test_purge_04_open_ended_final_block_has_no_upper_completeness_bound(self):
        origin = _origin("2026-02-05")
        results = assess_validation_block([origin], block_start="2026-02-01", block_end=None)
        assert results[0].complete is True

    def test_purged_7_day_horizon_policy_constant_is_documented(self):
        assert PURGED_7_DAY_HORIZON_POLICY == "PURGED_7_DAY_HORIZON_POLICY"
