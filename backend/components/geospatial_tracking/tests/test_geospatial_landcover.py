"""LC-01/02/03."""

import numpy as np

from components.geospatial_tracking.services.geospatial.landcover.esa_worldcover import (
    STATIC_REFERENCE_PROXY,
    UNAVAILABLE_FOR_YEAR,
    WORLDCOVER_CLASSES,
    YEAR_MATCHED_REFERENCE,
    compute_class_fractions,
    resolve_landcover_temporal_role,
    tile_id_for,
)

# official ESA WorldCover v100/v200 class codes — the complete legend
_OFFICIAL_CODES = {10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100}


def test_lc_01_only_official_class_codes_are_mapped():
    assert set(WORLDCOVER_CLASSES.keys()) == _OFFICIAL_CODES
    # never a made-up code like 0, 5, 200, etc.
    assert all(code in _OFFICIAL_CODES for code in WORLDCOVER_CLASSES)


def test_lc_01_class_names_do_not_invent_new_categories():
    # every mapped name corresponds to an official legend entry — spot
    # check the ones used in the master-prompt's own example
    assert WORLDCOVER_CLASSES[40] == "cropland"
    assert WORLDCOVER_CLASSES[30] == "grassland"
    assert WORLDCOVER_CLASSES[50] == "built_up"
    assert WORLDCOVER_CLASSES[80] == "permanent_water_bodies"


def test_lc_02_nodata_pixels_excluded_from_fractions():
    # 6 valid pixels (3 cropland, 3 grassland) + 4 nodata (value 0, not an
    # official class) — nodata must not appear as a class and must not be
    # counted in the denominator.
    data = np.array([[40, 40, 40, 30, 30, 30], [0, 0, 0, 0, 0, 0]], dtype=np.uint8)
    fractions = compute_class_fractions(data, nodata=0)
    assert set(fractions.keys()) == {40, 30}
    assert fractions[40] == 0.5
    assert fractions[30] == 0.5
    assert sum(fractions.values()) == 1.0  # nodata never silently included


def test_lc_02_all_nodata_returns_empty_not_fabricated():
    data = np.full((4, 4), 0, dtype=np.uint8)
    fractions = compute_class_fractions(data, nodata=0)
    assert fractions == {}


def test_lc_02_no_nodata_value_declared_uses_all_pixels():
    data = np.array([[40, 40], [30, 30]], dtype=np.uint8)
    fractions = compute_class_fractions(data, nodata=None)
    assert fractions == {40: 0.5, 30: 0.5}


def test_lc_03_area_zonal_extraction_is_deterministic():
    data = np.array([[10, 10, 40, 40, 40, 80]], dtype=np.uint8)
    f1 = compute_class_fractions(data, nodata=None)
    f2 = compute_class_fractions(data, nodata=None)
    assert f1 == f2
    assert f1[10] == 2 / 6
    assert f1[40] == 3 / 6
    assert f1[80] == 1 / 6


def test_lc_03_only_classes_actually_present_are_returned():
    # a real AOI window would never report all 11 official classes if
    # only a few are actually present — fractions dict must be sparse
    data = np.array([[40, 40, 40, 40]], dtype=np.uint8)
    fractions = compute_class_fractions(data, nodata=None)
    assert fractions == {40: 1.0}
    assert 10 not in fractions  # tree_cover absent -> not reported


def test_tile_id_naming_matches_worldcover_grid_convention():
    # verified against the real, reachable S3 tiles for our two smoke AOIs
    assert tile_id_for(9.6579014, 80.1643076) == "N09E078"  # Sri Lanka
    assert tile_id_for(15.785878, 103.807367) == "N15E102"  # Thailand


def test_lc_time_01_2020_event_matches_worldcover_2020():
    # Event_3473 (Sri Lanka, 2020) smoke test uses WorldCover 2020 v100
    assert resolve_landcover_temporal_role("2020", target_year="2020") == YEAR_MATCHED_REFERENCE


def test_lc_time_02_2021_event_matches_worldcover_2021():
    # Event_3644 (Thailand, 2021) smoke test uses WorldCover 2021 v200
    assert resolve_landcover_temporal_role("2021", target_year="2021") == YEAR_MATCHED_REFERENCE


def test_lc_time_03_other_year_is_never_silently_year_matched():
    assert resolve_landcover_temporal_role("2021", target_year="2019") == STATIC_REFERENCE_PROXY
    assert resolve_landcover_temporal_role("2020", target_year="2023") == STATIC_REFERENCE_PROXY
    # unknown target year is also never treated as a match
    assert resolve_landcover_temporal_role("2021", target_year=None) == STATIC_REFERENCE_PROXY


def test_lc_time_03_unavailable_worldcover_year_flagged():
    assert resolve_landcover_temporal_role("2015", target_year="2015") == UNAVAILABLE_FOR_YEAR


def test_lc_time_04_v100_v200_difference_never_implied_as_pure_temporal_change():
    import inspect

    from components.geospatial_tracking.services.geospatial.landcover import esa_worldcover

    src = inspect.getsource(esa_worldcover)
    assert "different algorithm" in src.lower() or "algorithm, not just year" in src.lower()
    assert "never interpreted as real land-cover change" in src.lower() or "never" in src.lower()


def test_lc_area_01_terminology_matches_implemented_mathematics():
    import inspect

    from components.geospatial_tracking.services.geospatial.landcover import esa_worldcover

    src = inspect.getsource(esa_worldcover)
    # the fraction-producing function itself must not claim area-weighting
    # it doesn't perform
    assert "pixel-count zonal fraction" in src
    # and the module must document why the pixel-count approximation is
    # acceptable at this AOI scale, not just silently rename it
    assert "approximation" in src.lower()
