"""GEO-AREA-01 Section 13: nearest real historical source to the area."""

import math

from components.geospatial_tracking.services.my_area.nearest_source import find_nearest_historical_source

_COLOMBO = (6.9271, 79.8612)


class TestNearestSourceSelection:
    def test_selects_nearest_of_several_real_sources(self):
        sources = [
            ("FAR", 9.0, 82.0, "ACTUAL", "EXACT"),
            ("NEAR", _COLOMBO[0] + 0.01, _COLOMBO[1] + 0.01, "ACTUAL", "EXACT"),
        ]
        result = find_nearest_historical_source(sources, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1])
        assert result.source_id == "NEAR"

    def test_distance_is_finite_and_non_negative(self):
        sources = [("S1", 7.0, 80.0, "ACTUAL", "EXACT")]
        result = find_nearest_historical_source(sources, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1])
        assert result.distance_from_area_km >= 0
        assert math.isfinite(result.distance_from_area_km)

    def test_carries_availability_and_gps_quality_through(self):
        sources = [("S1", 7.0, 80.0, "CONFIRMATION_PROXY", "APPROXIMATE")]
        result = find_nearest_historical_source(sources, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1])
        assert result.availability_quality == "CONFIRMATION_PROXY"
        assert result.gps_quality == "APPROXIMATE"


class TestNoSourceCoordinatesUnavailable:
    def test_empty_source_list_returns_none(self):
        assert find_nearest_historical_source([], area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1]) is None

    def test_all_sources_missing_coordinates_returns_none(self):
        sources = [("S1", None, None, "ACTUAL", "EXACT")]
        assert find_nearest_historical_source(sources, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1]) is None

    def test_malformed_coordinate_never_calculated(self):
        sources = [
            ("BAD", float("nan"), float("inf"), "ACTUAL", "EXACT"),
            ("GOOD", 7.0, 80.0, "ACTUAL", "EXACT"),
        ]
        result = find_nearest_historical_source(sources, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1])
        assert result.source_id == "GOOD"


class TestNoUnsupportedFallback:
    def test_never_returns_a_source_with_no_real_coordinate(self):
        sources = [("S1", None, 80.0, "ACTUAL", "EXACT")]  # partial coordinate
        assert find_nearest_historical_source(sources, area_latitude=_COLOMBO[0], area_longitude=_COLOMBO[1]) is None
