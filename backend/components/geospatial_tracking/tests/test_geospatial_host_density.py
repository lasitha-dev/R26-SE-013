"""HOST-01/02/03."""

import numpy as np

from components.geospatial_tracking.services.geospatial.host_density.fao_glw import (
    GLW_SPECIES,
    REFERENCE_YEAR,
    UNITS,
    compute_cell_density_from_pixel_overlaps,
    compute_zonal_density,
    extract_density,
    extract_grid_cell_density,
    overlap_fraction,
)


def test_host_01_reference_year_is_2015_not_2020():
    # GLW4's real reference year, verified from the dataset's own metadata
    assert REFERENCE_YEAR == "2015"


def test_host_01_supports_cattle_and_buffalo():
    assert "cattle" in GLW_SPECIES
    assert "buffalo" in GLW_SPECIES
    assert GLW_SPECIES["cattle"].doi == "10.7910/DVN/LHBICE"
    assert GLW_SPECIES["buffalo"].doi == "10.7910/DVN/I1WCAB"


def test_host_01_units_are_density_not_headcount():
    assert UNITS == "animals_per_km2"


def test_host_02_density_is_total_count_over_total_real_area():
    # 4 pixels: counts 10,10,10,10 each covering 2 km2 -> density = 40/8 = 5.0
    counts = np.array([[10, 10, 10, 10]], dtype=np.float32)
    areas = np.array([[2.0, 2.0, 2.0, 2.0]], dtype=np.float32)
    density = compute_zonal_density(counts, None, areas, None)
    assert abs(density - 5.0) < 1e-6


def test_host_02_nodata_pixels_excluded_from_both_sums():
    # 2 valid pixels (count=10, area=2 each -> density would be 5.0) plus
    # 2 nodata pixels that must not distort the sum.
    counts = np.array([[10, 10, -1, -1]], dtype=np.float32)
    areas = np.array([[2.0, 2.0, 2.0, 2.0]], dtype=np.float32)
    density = compute_zonal_density(counts, -1, areas, None)
    assert abs(density - 5.0) < 1e-6


def test_host_02_source_raster_is_count_not_density_documented():
    import inspect

    from components.geospatial_tracking.services.geospatial.host_density import fao_glw

    src = inspect.getsource(fao_glw)
    assert "animal numbers per pixel" in src or "COUNT per pixel" in src


def test_host_03_zero_total_area_is_none_not_zero():
    counts = np.array([[10.0, 10.0]], dtype=np.float32)
    areas = np.array([[0.0, 0.0]], dtype=np.float32)
    assert compute_zonal_density(counts, None, areas, None) is None


def test_host_03_all_nodata_returns_none_not_fabricated():
    counts = np.full((3, 3), -1, dtype=np.float32)
    areas = np.full((3, 3), 5.0, dtype=np.float32)
    assert compute_zonal_density(counts, -1, areas, None) is None


def test_host_03_unsupported_species_is_blocked_not_fabricated():
    result = extract_density(
        center_lat=9.66, center_lon=80.16, half_extent_km=5.0, species="goat"
    )
    assert result.status == "BLOCKED"
    assert result.value is None


def test_host_03_zonal_density_is_deterministic():
    counts = np.array([[1.0, 2.0, 3.0, 4.0]], dtype=np.float32)
    areas = np.array([[1.0, 1.0, 1.0, 1.0]], dtype=np.float32)
    d1 = compute_zonal_density(counts, None, areas, None)
    d2 = compute_zonal_density(counts, None, areas, None)
    assert d1 == d2


def test_host_reg_01_count_raster_cannot_be_directly_emitted_as_density():
    # regression guard (Checkpoint 5.5 Part 12): a real GLW4 count-per-pixel
    # value (e.g. ~3785, the implausible figure produced by the original
    # Checkpoint 5 bug) must NOT pass through unchanged as animals_per_km2
    # when a real, non-trivial area raster is present.
    implausible_raw_count = np.array([[3785.0]], dtype=np.float32)
    real_pixel_area_km2 = np.array([[342.25]], dtype=np.float32)  # ~18.5km x 18.5km GLW4 pixel
    density = compute_zonal_density(implausible_raw_count, None, real_pixel_area_km2, None)
    assert density is not None
    assert abs(density - implausible_raw_count[0, 0]) > 1.0  # never the raw count itself
    assert density < 100  # plausible real-world cattle-density order of magnitude


def test_host_reg_02_density_uses_count_over_real_area_not_count_alone():
    counts = np.array([[100.0, 100.0]], dtype=np.float32)
    areas = np.array([[10.0, 10.0]], dtype=np.float32)
    density = compute_zonal_density(counts, None, areas, None)
    # sum(count)/sum(area) = 200/20 = 10.0, never sum(count) = 200.0 alone
    assert abs(density - 10.0) < 1e-6


class TestOverlapFraction:
    def test_full_overlap_is_1(self):
        pixel = (80.0, 9.0, 80.1, 9.1)
        assert abs(overlap_fraction(pixel, pixel) - 1.0) < 1e-9

    def test_no_overlap_is_0(self):
        pixel = (80.0, 9.0, 80.1, 9.1)
        far_cell = (81.0, 10.0, 81.1, 10.1)
        assert overlap_fraction(pixel, far_cell) == 0.0

    def test_half_overlap_is_half(self):
        pixel = (0.0, 0.0, 1.0, 1.0)
        cell = (0.5, 0.0, 1.5, 1.0)  # covers the right half of the pixel
        assert abs(overlap_fraction(pixel, cell) - 0.5) < 1e-9


class TestGridCellHostDensity:
    """HOST-GRID-01..07 (Checkpoint 5.6 Parts 9-11)."""

    def test_host_grid_01_single_pixel_known_count_area_gives_exact_density(self):
        # cell fully inside the one pixel -> overlap_fraction = 1.0 for
        # that pixel, 0 for everything else
        pixel_bounds = (80.0, 9.0, 80.1, 9.1)
        cell_bounds = (80.02, 9.02, 80.08, 9.08)  # comfortably inside the pixel
        records = [(pixel_bounds, 500.0, 100.0, False)]  # count=500, area=100km2 -> density=5.0
        density = compute_cell_density_from_pixel_overlaps(cell_bounds, records)
        assert abs(density - 5.0) < 1e-9

    def test_host_grid_02_cell_fully_inside_one_pixel_ignores_cell_size(self):
        pixel_bounds = (80.0, 9.0, 80.1, 9.1)
        records = [(pixel_bounds, 500.0, 100.0, False)]
        small_cell = (80.04, 9.04, 80.06, 9.06)
        large_cell = (80.01, 9.01, 80.09, 9.09)
        density_small = compute_cell_density_from_pixel_overlaps(small_cell, records)
        density_large = compute_cell_density_from_pixel_overlaps(large_cell, records)
        # both fully inside the same single pixel -> identical density,
        # no arbitrary radius-dependent averaging
        assert abs(density_small - density_large) < 1e-9
        assert abs(density_small - 5.0) < 1e-9

    def test_host_grid_03_cell_overlapping_two_pixels_uses_overlap_weighting(self):
        # two adjacent pixels, same area, different densities
        pixel_a = (0.0, 0.0, 1.0, 1.0)  # count=10, area=10 -> density=1.0
        pixel_b = (1.0, 0.0, 2.0, 1.0)  # count=90, area=10 -> density=9.0
        # cell straddles both, 50/50
        cell = (0.5, 0.0, 1.5, 1.0)
        records = [(pixel_a, 10.0, 10.0, False), (pixel_b, 90.0, 10.0, False)]
        density = compute_cell_density_from_pixel_overlaps(cell, records)
        # weighted_count = 0.5*10 + 0.5*90 = 50; weighted_area = 0.5*10 + 0.5*10 = 10
        # density = 50/10 = 5.0 -- between the two pure densities (1.0 and 9.0), not equal to either
        assert abs(density - 5.0) < 1e-9

    def test_host_grid_04_unrelated_boundary_does_not_change_cell_density(self):
        pixel_bounds = (80.0, 9.0, 80.1, 9.1)
        cell_bounds = (80.02, 9.02, 80.08, 9.08)
        records_minimal = [(pixel_bounds, 500.0, 100.0, False)]
        records_with_unrelated_far_pixel = [
            (pixel_bounds, 500.0, 100.0, False),
            ((85.0, 12.0, 85.1, 12.1), 99999.0, 1.0, False),  # far away, no overlap with cell
        ]
        d1 = compute_cell_density_from_pixel_overlaps(cell_bounds, records_minimal)
        d2 = compute_cell_density_from_pixel_overlaps(cell_bounds, records_with_unrelated_far_pixel)
        assert abs(d1 - d2) < 1e-9

    def test_host_grid_05_no_aoi_max_normalization(self):
        # two independent cells with different raw densities -- neither
        # is rescaled against the other's maximum
        pixel_bounds = (80.0, 9.0, 80.1, 9.1)
        cell_a = (80.02, 9.02, 80.04, 9.04)
        cell_b = (80.06, 9.06, 80.08, 9.08)
        records = [(pixel_bounds, 500.0, 100.0, False)]
        density_a = compute_cell_density_from_pixel_overlaps(cell_a, records)
        density_b = compute_cell_density_from_pixel_overlaps(cell_b, records)
        # both fully inside the same pixel -> both equal the pixel's raw
        # density, neither is normalized to a 0-1 range or rescaled
        assert abs(density_a - 5.0) < 1e-9
        assert abs(density_b - 5.0) < 1e-9
        assert density_a > 1.0  # not squashed into a normalized [0,1] range

    def test_host_grid_06_nodata_overlap_not_silently_zero(self):
        pixel_bounds = (80.0, 9.0, 80.1, 9.1)
        cell_bounds = (80.02, 9.02, 80.08, 9.08)
        records = [(pixel_bounds, 500.0, 100.0, True)]  # is_nodata=True
        density = compute_cell_density_from_pixel_overlaps(cell_bounds, records)
        assert density is None  # never 0.0

    def test_host_grid_07_reference_year_2015_visible_in_extraction_code(self):
        import inspect

        from components.geospatial_tracking.services.geospatial.host_density import fao_glw

        src = inspect.getsource(fao_glw.extract_grid_cell_density)
        assert "REFERENCE_YEAR" in src
        assert REFERENCE_YEAR == "2015"

    def test_host_grid_unsupported_species_is_blocked(self):
        class _FakeCell:
            grid_cell_id = "TEST:0000:0000"
            centroid_lat = 9.66
            centroid_lon = 80.16
            cell_size_km = 2.5

        result = extract_grid_cell_density(grid_cell=_FakeCell(), species="goat")
        assert result.status == "BLOCKED"
        assert result.value is None
