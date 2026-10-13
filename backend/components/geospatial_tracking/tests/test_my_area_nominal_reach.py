"""GEO-AREA-01H Section 15/16/17: D0/D+N nominal-reach context.

Corrected from GEO-AREA-01's original version: no distance-to-origin
parameter exists anymore. `nominal_reach_km(day_h) = frozen_S0_rate_km_day
* day_h` (`services/integration/nominal_reach_9c.py`, verified read-only)
is a pure function of `day_h` alone, with zero spatial input -- no
scientifically defined reach anchor exists, so `relation` is always
`NOT_APPLICABLE`."""

from components.geospatial_tracking.domain.my_area_enums import (
    NOMINAL_REACH_DISCLAIMER,
    ForecastDayBasis,
    NominalReachAnchorBasis,
    NominalReachRelation,
)
from components.geospatial_tracking.services.my_area.nominal_reach_context import build_nominal_reach_context

_ENTRIES = [{"day": d, "nominal_reach_km": 10.0 * d, "derived_interval_lower_km": None, "derived_interval_upper_km": None} for d in range(1, 8)]


class TestDayZero:
    def test_day_zero_does_not_fabricate_reach_zero(self):
        ctx = build_nominal_reach_context(day=0, t0="2026-01-01", nominal_reach_entries=_ENTRIES)
        assert ctx.nominal_reach_km is None

    def test_day_zero_identified_as_observed_origin_context(self):
        ctx = build_nominal_reach_context(day=0, t0="2026-01-01", nominal_reach_entries=_ENTRIES)
        assert ctx.basis == ForecastDayBasis.OBSERVED_ORIGIN_CONTEXT.value
        assert ctx.relation == NominalReachRelation.NOT_APPLICABLE.value

    def test_day_zero_forecast_date_is_the_real_t0(self):
        ctx = build_nominal_reach_context(day=0, t0="2026-01-01", nominal_reach_entries=_ENTRIES)
        assert ctx.forecast_date == "2026-01-01"


class TestRealDaysReturned:
    def test_real_scalar_reach_preserved_d_plus_1(self):
        ctx = build_nominal_reach_context(day=1, t0="2026-01-01", nominal_reach_entries=_ENTRIES)
        assert ctx.nominal_reach_km == 10.0
        assert ctx.basis == ForecastDayBasis.FORECAST.value

    def test_real_scalar_reach_preserved_d_plus_7(self):
        ctx = build_nominal_reach_context(day=7, t0="2026-01-01", nominal_reach_entries=_ENTRIES)
        assert ctx.nominal_reach_km == 70.0

    def test_missing_frame_returns_none_for_the_caller_to_map_to_forecast_frame_unavailable(self):
        sparse_entries = [e for e in _ENTRIES if e["day"] != 3]
        ctx = build_nominal_reach_context(day=3, t0="2026-01-01", nominal_reach_entries=sparse_entries)
        assert ctx is None


class TestUnsupportedAnchorNeverGuessesARelation:
    def test_relation_is_always_not_applicable_this_checkpoint(self):
        for day in range(0, 8):
            ctx = build_nominal_reach_context(day=day, t0="2026-01-01", nominal_reach_entries=_ENTRIES)
            assert ctx.relation == NominalReachRelation.NOT_APPLICABLE.value

    def test_never_produces_within_or_outside_reach(self):
        for day in range(0, 8):
            ctx = build_nominal_reach_context(day=day, t0="2026-01-01", nominal_reach_entries=_ENTRIES)
            assert ctx.relation != NominalReachRelation.WITHIN_NOMINAL_VISUALIZATION_REACH.value
            assert ctx.relation != NominalReachRelation.OUTSIDE_NOMINAL_VISUALIZATION_REACH.value

    def test_anchor_basis_explicitly_explains_why(self):
        ctx = build_nominal_reach_context(day=1, t0="2026-01-01", nominal_reach_entries=_ENTRIES)
        assert ctx.anchor_basis == NominalReachAnchorBasis.NO_SCIENTIFICALLY_DEFINED_REACH_ANCHOR.value

    def test_function_signature_has_no_distance_parameter(self):
        import inspect

        signature = inspect.signature(build_nominal_reach_context)
        assert "distance_area_to_origin_km" not in signature.parameters
        assert "distance_to_origin_km" not in signature.parameters
        assert not any("distance" in name for name in signature.parameters)


class TestDisclaimerAndWording:
    def test_required_disclaimer_present_on_every_context(self):
        for day in range(0, 8):
            ctx = build_nominal_reach_context(day=day, t0="2026-01-01", nominal_reach_entries=_ENTRIES)
            assert ctx.disclaimer == NOMINAL_REACH_DISCLAIMER

    def test_disclaimer_exact_required_wording(self):
        assert NOMINAL_REACH_DISCLAIMER == "Nominal reach — visualization only, not a disease boundary."

    def test_never_labelled_disease_boundary_or_clinical_terms(self):
        ctx = build_nominal_reach_context(day=1, t0="2026-01-01", nominal_reach_entries=_ENTRIES)
        forbidden = ["infected", "safe", "inside outbreak", "outside outbreak", "predicted infection zone", "quarantine"]
        rendered = " ".join(str(v) for v in [ctx.relation, ctx.basis, ctx.anchor_basis, ctx.disclaimer]).lower()
        for word in forbidden:
            assert word not in rendered
        # "disease boundary" IS present -- only inside the required
        # disclaimer's own negation ("not a disease boundary"), never
        # asserted affirmatively elsewhere.
        assert "not a disease boundary" in ctx.disclaimer.lower()


class TestNoFakeDayVaryingScore:
    def test_changing_day_never_touches_a_score_field(self):
        # NominalReachContext has no score-related field at all -- proves
        # structurally that changing day cannot fabricate a changing
        # Relative Spatial Score through this object.
        ctx = build_nominal_reach_context(day=1, t0="2026-01-01", nominal_reach_entries=_ENTRIES)
        field_names = set(ctx.__dataclass_fields__)
        assert field_names.isdisjoint({"score", "relative_spatial_score", "raw_c0_score"})

    def test_only_the_scalar_reach_and_basis_change_across_days_relation_stays_constant(self):
        ctx1 = build_nominal_reach_context(day=1, t0="2026-01-01", nominal_reach_entries=_ENTRIES)
        ctx7 = build_nominal_reach_context(day=7, t0="2026-01-01", nominal_reach_entries=_ENTRIES)
        assert ctx1.nominal_reach_km != ctx7.nominal_reach_km
        assert ctx1.relation == ctx7.relation == NominalReachRelation.NOT_APPLICABLE.value
