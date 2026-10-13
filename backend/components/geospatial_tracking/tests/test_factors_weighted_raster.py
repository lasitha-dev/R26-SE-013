"""Checkpoint 6D.6 Part 16: weighted effective raster-sample identity
tests — WEIGHTED-REF-01..07."""

from __future__ import annotations

from components.geospatial_tracking.services.geospatial.host_density.fao_glw import contributing_pixel_sample_support

_KW = dict(dataset_name="GLW4", dataset_version="2015", species="cattle", source_asset_id="asset.tif")


def test_weighted_ref_01_single_pixel_full_weight_same_identity_different_cells():
    # cell fully inside one big pixel, at two different fine-grid
    # locations -- normalized weight is 1.0 in both cases.
    pixel_records = [((99.0, 14.0, 101.0, 16.0), 100.0, 10.0, False)]
    cell_a = (99.5, 14.5, 99.51, 14.51)
    cell_b = (100.4, 15.4, 100.41, 15.41)
    digest_a, n_a = contributing_pixel_sample_support(cell_a, pixel_records, **_KW)
    digest_b, n_b = contributing_pixel_sample_support(cell_b, pixel_records, **_KW)
    assert digest_a == digest_b
    assert n_a == n_b == 1


def test_weighted_ref_02_same_two_pixels_same_weights_same_identity():
    pixel_records = [((99.0, 14.0, 100.0, 15.0), 100.0, 10.0, False), ((100.0, 14.0, 101.0, 15.0), 50.0, 10.0, False)]
    # a cell straddling both pixels equally
    cell = (99.5, 14.4, 100.5, 14.6)
    digest_1, n_1 = contributing_pixel_sample_support(cell, pixel_records, **_KW)
    digest_2, n_2 = contributing_pixel_sample_support(cell, list(pixel_records), **_KW)  # recomputed, same inputs
    assert digest_1 == digest_2
    assert n_1 == n_2 == 2


def test_weighted_ref_03_same_pixel_set_different_weights_different_identity():
    pixel_records = [((99.0, 14.0, 100.0, 15.0), 100.0, 10.0, False), ((100.0, 14.0, 101.0, 15.0), 50.0, 10.0, False)]
    # cell mostly inside pixel A (weight ~0.9/0.1)
    cell_mostly_a = (99.1, 14.4, 100.1, 14.6)
    # cell mostly inside pixel B (weight ~0.1/0.9) -- same two pixels touched, different overlap split
    cell_mostly_b = (99.9, 14.4, 100.9, 14.6)
    digest_a, _ = contributing_pixel_sample_support(cell_mostly_a, pixel_records, **_KW)
    digest_b, _ = contributing_pixel_sample_support(cell_mostly_b, pixel_records, **_KW)
    assert digest_a != digest_b


def test_weighted_ref_04_same_weights_pixels_different_source_asset_different_identity():
    pixel_records = [((99.0, 14.0, 100.0, 15.0), 100.0, 10.0, False)]
    cell = (99.4, 14.4, 99.6, 14.6)
    digest_1, _ = contributing_pixel_sample_support(cell, pixel_records, dataset_name="GLW4", dataset_version="2015", species="cattle", source_asset_id="asset_A.tif")
    digest_2, _ = contributing_pixel_sample_support(cell, pixel_records, dataset_name="GLW4", dataset_version="2015", species="cattle", source_asset_id="asset_B.tif")
    assert digest_1 != digest_2


def test_weighted_ref_05_same_weights_pixels_asset_different_dataset_version_different_identity():
    pixel_records = [((99.0, 14.0, 100.0, 15.0), 100.0, 10.0, False)]
    cell = (99.4, 14.4, 99.6, 14.6)
    digest_2015, _ = contributing_pixel_sample_support(cell, pixel_records, dataset_name="GLW4", dataset_version="2015", species="cattle", source_asset_id="asset.tif")
    digest_2020, _ = contributing_pixel_sample_support(cell, pixel_records, dataset_name="GLW4", dataset_version="2020", species="cattle", source_asset_id="asset.tif")
    assert digest_2015 != digest_2020


def test_weighted_ref_06_nodata_support_change_changes_identity():
    cell = (99.4, 14.4, 99.6, 14.6)
    with_extra_pixel = [((99.0, 14.0, 100.0, 15.0), 100.0, 10.0, False), ((99.0, 14.0, 100.0, 15.0), 999.0, 10.0, True)]  # second is nodata, same bounds -- excluded
    without_extra_pixel = [((99.0, 14.0, 100.0, 15.0), 100.0, 10.0, False)]
    digest_with, n_with = contributing_pixel_sample_support(cell, with_extra_pixel, **_KW)
    digest_without, n_without = contributing_pixel_sample_support(cell, without_extra_pixel, **_KW)
    # nodata pixel excluded entirely -> identical effective support
    assert digest_with == digest_without
    assert n_with == n_without == 1

    # now make a genuinely contributing second pixel (not nodata) -- support changes
    with_real_second_pixel = [((99.0, 14.0, 100.0, 15.0), 100.0, 10.0, False), ((99.0, 14.5, 100.0, 15.5), 50.0, 10.0, False)]
    digest_changed, n_changed = contributing_pixel_sample_support(cell, with_real_second_pixel, **_KW)
    assert digest_changed != digest_without
    assert n_changed == 2


def test_weighted_ref_07_input_ordering_does_not_affect_identity():
    cell = (99.5, 14.4, 100.5, 14.6)
    pixel_records_forward = [((99.0, 14.0, 100.0, 15.0), 100.0, 10.0, False), ((100.0, 14.0, 101.0, 15.0), 50.0, 10.0, False)]
    pixel_records_reversed = list(reversed(pixel_records_forward))
    digest_forward, _ = contributing_pixel_sample_support(cell, pixel_records_forward, **_KW)
    digest_reversed, _ = contributing_pixel_sample_support(cell, pixel_records_reversed, **_KW)
    assert digest_forward == digest_reversed


def test_no_contribution_returns_none():
    cell = (200.0, 50.0, 200.1, 50.1)  # far away, no overlap
    pixel_records = [((99.0, 14.0, 100.0, 15.0), 100.0, 10.0, False)]
    digest, n = contributing_pixel_sample_support(cell, pixel_records, **_KW)
    assert digest is None
    assert n == 0
