"""Checkpoint 6D.5 Part 23: raster-observation dedup tests —
RASTER-REF-01..05."""

from __future__ import annotations

from components.geospatial_tracking.services.factors.host_transform import compute_host_density_total
from components.geospatial_tracking.services.factors.reference_observations import (
    QUERY_CENTROID_FALLBACK,
    RASTER_LEGACY_PIXEL_SET_IDENTITY,
    resolve_static_observation_identity,
)
from components.geospatial_tracking.services.geospatial.host_density.fao_glw import contributing_pixel_sample_identity

_UNITS = "animals_per_km2"


def _real_fr(value, *, feature_name, sample_identity, dataset_version="2015"):
    return {"feature_name": feature_name, "value": value, "units": _UNITS, "status": "REAL", "dataset_name": "GLW4", "dataset_version": dataset_version, "sample_identity": sample_identity}


def test_raster_ref_01_same_pixel_from_two_origins_one_observation():
    # two different query cells, SAME underlying pixel identity (as a
    # real adapter would report when both cells fall inside one coarse
    # GLW4 pixel). This fixture only supplies `sample_identity` (pixel
    # SET only, no normalized weights) -- Checkpoint 7A Part 0B relabels
    # that path RASTER_LEGACY_PIXEL_SET_IDENTITY (never implying
    # weight-awareness it doesn't have); the real GLW4 adapter's REAL
    # results always carry `sample_support_digest` too, which resolves
    # via RASTER_EFFECTIVE_SAMPLE_IDENTITY instead (see test_factors_weighted_raster.py).
    fr_a = _real_fr(24.0, feature_name="host_density_cattle_grid_cell", sample_identity="GLW4PIXELS:same")
    fr_b = _real_fr(24.0, feature_name="host_density_cattle_grid_cell", sample_identity="GLW4PIXELS:same")
    id_a, source_a = resolve_static_observation_identity(fr_a, cell={"centroid_lat": 15.0, "centroid_lon": 101.0})
    id_b, source_b = resolve_static_observation_identity(fr_b, cell={"centroid_lat": 15.05, "centroid_lon": 101.05})  # DIFFERENT query centroid
    assert source_a == source_b == RASTER_LEGACY_PIXEL_SET_IDENTITY
    assert id_a == id_b  # same underlying pixel -> one observation


def test_raster_ref_02_different_query_centroids_same_pixel_one_observation():
    # explicit restatement of RASTER-REF-01's core claim via a direct
    # pixel-identity computation (never fabricated -- built from real
    # pixel bounds).
    cell_bounds = (100.0, 15.0, 100.01, 15.01)
    pixel_records = [((99.9, 14.9, 100.2, 15.2), 100.0, 10.0, False)]  # one big pixel fully covering the cell
    id1 = contributing_pixel_sample_identity(cell_bounds, pixel_records, dataset_name="GLW4", dataset_version="2015", species="cattle", source_asset_id="asset.tif")
    # a second, nearby cell fully inside the SAME pixel
    cell_bounds_2 = (100.05, 15.05, 100.06, 15.06)
    id2 = contributing_pixel_sample_identity(cell_bounds_2, pixel_records, dataset_name="GLW4", dataset_version="2015", species="cattle", source_asset_id="asset.tif")
    assert id1 == id2


def test_raster_ref_03_different_pixels_distinct_observations():
    cell_a = (100.0, 15.0, 100.01, 15.01)
    cell_b = (200.0, 25.0, 200.01, 25.01)
    pixel_records = [((99.9, 14.9, 100.2, 15.2), 100.0, 10.0, False), ((199.9, 24.9, 200.2, 25.2), 50.0, 10.0, False)]
    id_a = contributing_pixel_sample_identity(cell_a, pixel_records, dataset_name="GLW4", dataset_version="2015", species="cattle", source_asset_id="asset.tif")
    id_b = contributing_pixel_sample_identity(cell_b, pixel_records, dataset_name="GLW4", dataset_version="2015", species="cattle", source_asset_id="asset.tif")
    assert id_a != id_b


def test_raster_ref_04_same_pixel_coords_different_dataset_version_distinct_identity():
    cell_bounds = (100.0, 15.0, 100.01, 15.01)
    pixel_records = [((99.9, 14.9, 100.2, 15.2), 100.0, 10.0, False)]
    id_2015 = contributing_pixel_sample_identity(cell_bounds, pixel_records, dataset_name="GLW4", dataset_version="2015", species="cattle", source_asset_id="asset.tif")
    id_2020 = contributing_pixel_sample_identity(cell_bounds, pixel_records, dataset_name="GLW4", dataset_version="2020", species="cattle", source_asset_id="asset.tif")
    assert id_2015 != id_2020


def test_raster_ref_05_host_total_identity_derived_from_species_ids():
    cell = {
        "centroid_lat": 15.0, "centroid_lon": 101.0,
        "host_density": {
            "cattle": _real_fr(8.0, feature_name="host_density_cattle_grid_cell", sample_identity="GLW4PIXELS:cattle1"),
            "buffalo": _real_fr(2.0, feature_name="host_density_buffalo_grid_cell", sample_identity="GLW4PIXELS:buffalo1"),
        },
    }
    raw = compute_host_density_total(cell)
    assert raw.host_density_total_observation_id is not None
    # changing ONLY the buffalo pixel identity (same numeric values) must
    # change the host-total identity, because it is derived from BOTH
    # species observation identities, never independently re-derived.
    cell2 = {
        "centroid_lat": 15.0, "centroid_lon": 101.0,
        "host_density": {
            "cattle": _real_fr(8.0, feature_name="host_density_cattle_grid_cell", sample_identity="GLW4PIXELS:cattle1"),
            "buffalo": _real_fr(2.0, feature_name="host_density_buffalo_grid_cell", sample_identity="GLW4PIXELS:buffalo_DIFFERENT"),
        },
    }
    raw2 = compute_host_density_total(cell2)
    assert raw.host_density_total_observation_id != raw2.host_density_total_observation_id


def test_fallback_to_query_centroid_when_no_sample_identity():
    fr = {"feature_name": "host_density_cattle_grid_cell", "value": 8.0, "units": _UNITS, "status": "REAL", "dataset_name": "GLW4", "dataset_version": "2015", "sample_identity": None}
    identity, source = resolve_static_observation_identity(fr, cell={"centroid_lat": 15.0, "centroid_lon": 101.0})
    assert source == QUERY_CENTROID_FALLBACK
    assert "lat" in identity and "lon" in identity
