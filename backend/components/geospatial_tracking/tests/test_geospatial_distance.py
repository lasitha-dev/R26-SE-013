"""GEO-01..05."""

import math

from components.geospatial_tracking.services.geospatial.crs import analysis_crs_for, utm_zone_for
from components.geospatial_tracking.services.geospatial.distance import (
    distance_km,
    geodesic,
    source_to_cell_unit_vector,
)

# real Sri Lanka Event_3473 coordinates (Kopay, Chavakachcheri)
KOPAY = (9.7151701, 80.0668497)
CHAVAKACHCHERI = (9.6579014, 80.1643076)

# real Thailand Event_3644 coordinate (Muang Suang, earliest EXACT-GPS candidate)
MUANG_SUANG = (15.785878, 103.807367)


def test_geo_01_identical_coordinates_zero_distance():
    d = distance_km(9.71517, 80.066849, 9.71517, 80.066849)
    assert d == 0.0


def test_geo_02_no_degrees_as_km_calculation():
    # A naive sqrt(dlat^2 + dlon^2) "distance" for Kopay<->Chavakachcheri
    # would be ~0.128 (degrees) -- nowhere near a real km figure. The real
    # geodesic distance between these two actual outbreak points is on
    # the order of ~12 km (well-separated villages in the same district).
    naive_degree_distance = math.sqrt(
        (KOPAY[0] - CHAVAKACHCHERI[0]) ** 2 + (KOPAY[1] - CHAVAKACHCHERI[1]) ** 2
    )
    real_km = distance_km(*KOPAY, *CHAVAKACHCHERI)
    assert real_km != naive_degree_distance
    assert 1 < real_km < 50  # sanity: real-world separation, not a degree value
    # naive value is a bare fraction-of-a-degree number, not plausible km
    assert naive_degree_distance < 1


def test_geo_02_one_degree_longitude_is_not_111_km_everywhere():
    # a degree of longitude shrinks with latitude (~111km * cos(lat)) —
    # never a constant, so no fixed "1 degree = X km" conversion is valid.
    equator_1deg = distance_km(0.0, 0.0, 0.0, 1.0)
    high_lat_1deg = distance_km(60.0, 0.0, 60.0, 1.0)
    assert equator_1deg > high_lat_1deg
    assert abs(equator_1deg - 111.0) < 2  # ~111km at the equator, geodesic-computed
    assert abs(high_lat_1deg - equator_1deg * math.cos(math.radians(60))) < 2


def test_geo_03_sri_lanka_coordinates_work():
    d = distance_km(*KOPAY, *CHAVAKACHCHERI)
    assert d > 0
    result = geodesic(*KOPAY, *CHAVAKACHCHERI)
    assert 0 <= result.forward_azimuth_deg < 360


def test_geo_03_thailand_coordinates_work():
    other_thai_point = (15.9, 103.9)
    d = distance_km(*MUANG_SUANG, *other_thai_point)
    assert d > 0
    result = geodesic(*MUANG_SUANG, *other_thai_point)
    assert 0 <= result.forward_azimuth_deg < 360


def test_geo_04_source_to_cell_vector_orientation_correct():
    # cell due EAST of source -> t_hat_east ~ 1, t_hat_north ~ 0
    source_lat, source_lon = 9.0, 80.0
    cell_lat, cell_lon = 9.0, 80.1  # same latitude, higher longitude = due east
    v = source_to_cell_unit_vector(source_lat, source_lon, cell_lat, cell_lon)
    assert v.t_hat_east > 0.99
    assert abs(v.t_hat_north) < 0.05

    # cell due NORTH of source -> t_hat_north ~ 1, t_hat_east ~ 0
    cell_lat2, cell_lon2 = 9.1, 80.0
    v2 = source_to_cell_unit_vector(source_lat, source_lon, cell_lat2, cell_lon2)
    assert v2.t_hat_north > 0.99
    assert abs(v2.t_hat_east) < 0.05

    # reversing source/cell reverses the vector direction
    v_reversed = source_to_cell_unit_vector(cell_lat, cell_lon, source_lat, source_lon)
    assert v_reversed.t_hat_east < -0.99


def test_geo_04_unit_vector_has_unit_length():
    v = source_to_cell_unit_vector(9.0, 80.0, 15.8, 103.8)
    length = math.sqrt(v.t_hat_east**2 + v.t_hat_north**2)
    assert abs(length - 1.0) < 1e-9


def test_geo_04_same_point_yields_zero_vector_not_undefined_direction():
    v = source_to_cell_unit_vector(9.0, 80.0, 9.0, 80.0)
    assert v.distance_km == 0.0
    assert v.t_hat_east == 0.0
    assert v.t_hat_north == 0.0


def test_geo_05_geometry_by_source_keeps_separate_entries_for_multiple_sources():
    # A grid cell's geometry relative to TWO different sources must be
    # computed and kept independently — see services/geospatial/grid.py
    # geometry_by_source builder; this proves the underlying per-pair
    # calculation genuinely differs (not accidentally memoized/shared).
    cell = (9.9, 80.5)
    v_from_kopay = source_to_cell_unit_vector(*KOPAY, *cell)
    v_from_chavakachcheri = source_to_cell_unit_vector(*CHAVAKACHCHERI, *cell)
    assert v_from_kopay.distance_km != v_from_chavakachcheri.distance_km
    assert (v_from_kopay.t_hat_east, v_from_kopay.t_hat_north) != (
        v_from_chavakachcheri.t_hat_east,
        v_from_chavakachcheri.t_hat_north,
    )


def test_utm_zone_and_crs_choice_differ_by_country_not_hardcoded():
    sl_crs = analysis_crs_for(*KOPAY)
    th_crs = analysis_crs_for(*MUANG_SUANG)
    assert sl_crs.analysis_crs != th_crs.analysis_crs
    assert sl_crs.utm_zone == 44  # Sri Lanka
    assert th_crs.utm_zone == 48  # Thailand (Muang Suang, ~103.8E)
    assert sl_crs.hemisphere == "N"
    assert th_crs.hemisphere == "N"
    # never hardcoded to Sri Lanka's national grid EPSG:5235 for anything
    assert sl_crs.analysis_crs != "EPSG:5235"
    assert th_crs.analysis_crs != "EPSG:5235"


def test_utm_zone_for_known_longitudes():
    assert utm_zone_for(80.0668497) == 44  # Sri Lanka
    assert utm_zone_for(103.807367) == 48  # Thailand
    assert utm_zone_for(-0.5) == 30  # near Greenwich, sanity check
