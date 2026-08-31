"""WATER-01/02."""

from shapely.geometry import LineString, Point

from components.geospatial_tracking.services.geospatial.hydrology.hydrosheds import (
    distance_to_nearest_lake_km,
    nearest_feature_distance_km,
)


def test_water_01_distance_to_known_planar_line_is_correct():
    # a vertical line 3000m (3km) east of the point -> distance 3.0km
    point_xy = (0.0, 0.0)
    line = LineString([(3000.0, -1000.0), (3000.0, 1000.0)])
    distance = nearest_feature_distance_km(point_xy, [line])
    assert abs(distance - 3.0) < 1e-6


def test_water_01_zero_distance_when_point_on_line():
    point_xy = (0.0, 0.0)
    line = LineString([(-100.0, 0.0), (100.0, 0.0)])
    distance = nearest_feature_distance_km(point_xy, [line])
    assert abs(distance - 0.0) < 1e-6


def test_water_01_nearest_of_multiple_candidates_is_chosen():
    point_xy = (0.0, 0.0)
    near = LineString([(1000.0, -50.0), (1000.0, 50.0)])  # 1km away
    far = LineString([(5000.0, -50.0), (5000.0, 50.0)])  # 5km away
    distance = nearest_feature_distance_km(point_xy, [far, near])
    assert abs(distance - 1.0) < 1e-6


def test_water_01_no_candidates_returns_none_not_fabricated():
    assert nearest_feature_distance_km((0.0, 0.0), []) is None


def test_water_02_planar_distance_never_uses_degrees_as_km():
    # a synthetic point that would be wildly wrong if degrees were
    # mistaken for km (e.g. a 0.03-degree offset is NOT 0.03km real-world)
    point_xy = (0.0, 0.0)
    line = LineString([(30000.0, -100.0), (30000.0, 100.0)])  # 30km in real projected meters
    distance = nearest_feature_distance_km(point_xy, [line])
    assert abs(distance - 30.0) < 1e-6
    assert distance != 0.03  # would be the wrong "degrees == km" answer


def test_water_02_hydrolakes_deferred_not_fabricated():
    result = distance_to_nearest_lake_km(center_lat=9.66, center_lon=80.16, search_radius_km=10.0)
    assert result.status == "BLOCKED"
    assert result.value is None
    assert "HydroLAKES" in result.quality_notes
