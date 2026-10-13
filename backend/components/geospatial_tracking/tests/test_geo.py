from components.geospatial_tracking.data_processing.geo import haversine_km


def test_same_point_is_zero_distance():
    assert haversine_km(9.71517, 80.066849, 9.71517, 80.066849) == 0.0


def test_known_short_distance_is_small():
    # Kopay CSV pair's two coordinate-precision variants (sub-meter apart).
    d = haversine_km(9.71517, 80.066849, 9.7151701, 80.0668497)
    assert d < 0.001


def test_distance_is_symmetric():
    d1 = haversine_km(9.0, 80.0, 9.1, 80.1)
    d2 = haversine_km(9.1, 80.1, 9.0, 80.0)
    assert d1 == d2
