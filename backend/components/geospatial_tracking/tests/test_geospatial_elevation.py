"""ELEV-01."""

from components.geospatial_tracking.services.geospatial.elevation.nasadem import (
    extract_elevation as nasadem_extract,
)
from components.geospatial_tracking.services.geospatial.elevation.terrain_tiles import (
    DATASET_NAME,
    decode_terrarium_elevation,
    lonlat_to_tile_pixel,
)


def test_elev_01_terrarium_decode_zero_offset_is_sea_level():
    # Terrarium's documented zero point: R=128, G=0, B=0 -> 128*256-32768=0
    assert decode_terrarium_elevation(128, 0, 0) == 0.0


def test_elev_01_terrarium_decode_known_positive_value():
    # R=130, G=0, B=0 -> (130*256) - 32768 = 512.0m
    assert decode_terrarium_elevation(130, 0, 0) == 512.0


def test_elev_01_terrarium_decode_fractional_blue_component():
    # blue contributes sub-meter precision: B=256 -> +1.0m
    assert decode_terrarium_elevation(128, 0, 256) == 1.0


def test_elev_01_tile_pixel_math_is_deterministic_and_in_range():
    xtile, ytile, px, py = lonlat_to_tile_pixel(9.6579014, 80.1643076, zoom=12)
    assert 0 <= px < 256
    assert 0 <= py < 256
    xtile2, ytile2, px2, py2 = lonlat_to_tile_pixel(9.6579014, 80.1643076, zoom=12)
    assert (xtile, ytile, px, py) == (xtile2, ytile2, px2, py2)


def test_elev_01_nasadem_is_honestly_blocked_not_relabeled():
    result = nasadem_extract(latitude=9.66, longitude=80.16)
    assert result.status == "BLOCKED"
    assert result.value is None
    assert "Earthdata" in result.quality_notes


def test_elev_01_terrain_tiles_never_calls_itself_nasadem():
    assert "NASADEM" not in DATASET_NAME
