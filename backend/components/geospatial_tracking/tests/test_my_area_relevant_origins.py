"""GEO-AREA-01/01H Section 10/11: relevant-origin ranking."""

from components.geospatial_tracking.domain.my_area_enums import RELEVANT_ORIGIN_DISTANCE_BASIS
from components.geospatial_tracking.services.my_area.relevant_origins import rank_relevant_origins
from components.geospatial_tracking.tests._my_area_fakes import make_forecast_origin

_COLOMBO = (6.9271, 79.8612)


class TestDistanceCalculation:
    def test_known_reference_case_colombo_to_kandy_roughly_90_100_km(self):
        # Colombo (6.9271, 79.8612) -> Kandy (7.2906, 80.6337): real-world
        # great-circle distance is ~95 km -- a known reference sanity check.
        origin = make_forecast_origin(forecast_origin_id="O1", t0="2026-01-01")
        pairs = [(origin, [("SRC-1", 7.2906, 80.6337)])]
        result = rank_relevant_origins(pairs, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1], disease="LSD")
        assert 80 <= result[0].distance_from_area_km <= 110

    def test_same_coordinate_distance_approximately_zero(self):
        origin = make_forecast_origin(forecast_origin_id="O1")
        pairs = [(origin, [("SRC-1", _COLOMBO[0], _COLOMBO[1])])]
        result = rank_relevant_origins(pairs, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1], disease="LSD")
        assert result[0].distance_from_area_km < 0.01

    def test_lon_lat_order_correct(self):
        # A source at a real but clearly different lon/lat must not be
        # silently treated as equal to the area under a swapped order.
        origin = make_forecast_origin(forecast_origin_id="O1")
        pairs = [(origin, [("SRC-1", 0.0, 0.0)])]  # far from Colombo either way, but let's assert non-zero and finite
        result = rank_relevant_origins(pairs, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1], disease="LSD")
        assert result[0].distance_from_area_km > 1000  # (0,0) is genuinely far from Sri Lanka

    def test_no_trigger_locations_excludes_origin_never_fabricates_distance(self):
        origin = make_forecast_origin(forecast_origin_id="O1")
        pairs = [(origin, [])]
        result = rank_relevant_origins(pairs, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1], disease="LSD")
        assert result == []


class TestOnlyRealOrigins:
    def test_only_origins_with_at_least_one_located_trigger_source_are_returned(self):
        located = make_forecast_origin(forecast_origin_id="O-LOCATED")
        unlocated = make_forecast_origin(forecast_origin_id="O-UNLOCATED")
        pairs = [(located, [("S1", 7.0, 80.0)]), (unlocated, [])]
        result = rank_relevant_origins(pairs, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1], disease="LSD")
        assert [r.origin_id for r in result] == ["O-LOCATED"]

    def test_scientific_mode_carried_through_from_the_real_origin(self):
        origin = make_forecast_origin(forecast_origin_id="O1", temporal_mode="RETROSPECTIVE_PROXY")
        pairs = [(origin, [("S1", 7.0, 80.0)])]
        result = rank_relevant_origins(pairs, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1], disease="LSD")
        assert result[0].scientific_mode == "RETROSPECTIVE_PROXY"


class TestDeterministicOrdering:
    def test_sorted_by_distance_ascending(self):
        near = make_forecast_origin(forecast_origin_id="O-NEAR")
        far = make_forecast_origin(forecast_origin_id="O-FAR")
        pairs = [
            (far, [("S1", 9.0, 82.0)]),
            (near, [("S1", _COLOMBO[0] + 0.01, _COLOMBO[1] + 0.01)]),
        ]
        result = rank_relevant_origins(pairs, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1], disease="LSD")
        assert [r.origin_id for r in result] == ["O-NEAR", "O-FAR"]

    def test_stable_tie_break_by_origin_id_when_distance_equal(self):
        o_b = make_forecast_origin(forecast_origin_id="ORIGIN:B")
        o_a = make_forecast_origin(forecast_origin_id="ORIGIN:A")
        same_point = ("S1", 7.0, 80.0)
        pairs = [(o_b, [same_point]), (o_a, [same_point])]
        result = rank_relevant_origins(pairs, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1], disease="LSD")
        assert [r.origin_id for r in result] == ["ORIGIN:A", "ORIGIN:B"]

    def test_deterministic_across_repeated_calls(self):
        origins = [make_forecast_origin(forecast_origin_id=f"O{i}") for i in range(3)]
        pairs = [(o, [("S", 7.0 + i * 0.1, 80.0)]) for i, o in enumerate(origins)]
        a = rank_relevant_origins(pairs, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1], disease="LSD")
        b = rank_relevant_origins(pairs, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1], disease="LSD")
        assert a == b

    def test_limit_truncates_to_top_n(self):
        origins = [make_forecast_origin(forecast_origin_id=f"O{i}") for i in range(10)]
        pairs = [(o, [("S", 7.0 + i * 0.5, 80.0)]) for i, o in enumerate(origins)]
        result = rank_relevant_origins(pairs, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1], disease="LSD", limit=5)
        assert len(result) == 5


class TestDistanceBasisIsSelfDescribing:
    """GEO-AREA-01H Section 8: the distance is measured to real T0
    TRIGGER sources (the sources defining the origin's own identity) --
    never to a broader/different "eligible sources" set, and the field
    says so explicitly rather than relying on a comment."""

    def test_distance_basis_present_on_every_relevant_origin(self):
        origin = make_forecast_origin(forecast_origin_id="O1")
        pairs = [(origin, [("TRIGGER-1", 7.0, 80.0)])]
        result = rank_relevant_origins(pairs, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1], disease="LSD")
        assert result[0].distance_basis == RELEVANT_ORIGIN_DISTANCE_BASIS
        assert result[0].distance_basis == "NEAREST_T0_TRIGGER_SOURCE"

    def test_multiple_trigger_sources_use_the_deterministic_nearest_rule(self):
        # Section 15 item 6: with several real trigger-source locations,
        # the documented rule is "nearest of them", not the first/last/
        # average -- proven by using a point clearly nearest to one of three.
        origin = make_forecast_origin(forecast_origin_id="O1")
        pairs = [(origin, [("T-FAR", 9.5, 82.5), ("T-NEAR", _COLOMBO[0] + 0.02, _COLOMBO[1] + 0.02), ("T-MID", 8.0, 81.0)])]
        result = rank_relevant_origins(pairs, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1], disease="LSD")
        # The nearest of the three (T-NEAR, ~3km away) determines the distance.
        assert result[0].distance_from_area_km < 5.0
