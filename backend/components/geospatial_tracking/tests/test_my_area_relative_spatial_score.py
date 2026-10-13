"""GEO-AREA-01 Section 14/17: Relative Spatial Score at the area.

See `services/my_area/relative_spatial_score.py`'s module docstring for
the full evidence-backed reason this always returns an unavailable
score this checkpoint (the public `/cells` contract is Point-only; true
containment would require re-invoking internal scientific-domain
construction a second time, which Section 12 forbids)."""

from components.geospatial_tracking.domain.my_area_enums import (
    RELATIVE_SPATIAL_SCORE_LABEL,
    RELATIVE_SPATIAL_SCORE_TEMPORAL_BASIS,
    SCORE_STATUS_CELL_GEOMETRY_NOT_EXPOSED,
)
from components.geospatial_tracking.services.my_area.relative_spatial_score import build_relative_spatial_score_context


class TestScoreNeverFabricated:
    def test_value_is_always_none_this_checkpoint(self):
        ctx = build_relative_spatial_score_context()
        assert ctx.value is None

    def test_deterministic_across_calls(self):
        assert build_relative_spatial_score_context() == build_relative_spatial_score_context()

    def test_no_nearest_cell_id_ever_assigned(self):
        ctx = build_relative_spatial_score_context()
        assert ctx.scientific_cell_id is None

    def test_honest_status_explains_why(self):
        ctx = build_relative_spatial_score_context()
        assert ctx.status == SCORE_STATUS_CELL_GEOMETRY_NOT_EXPOSED


class TestNeverAProbabilityOrPercentage:
    def test_label_is_relative_spatial_score_never_probability_wording(self):
        ctx = build_relative_spatial_score_context()
        assert ctx.label == RELATIVE_SPATIAL_SCORE_LABEL
        lowered = ctx.label.lower()
        for forbidden in ("probability", "percent", "chance", "%"):
            assert forbidden not in lowered

    def test_temporal_basis_is_the_frozen_static_t0_constant_never_day_varying(self):
        ctx = build_relative_spatial_score_context()
        assert ctx.temporal_basis == RELATIVE_SPATIAL_SCORE_TEMPORAL_BASIS
        assert "STATIC_T0" in ctx.temporal_basis
