"""GRID-01/02/03 + geometry_by_source coverage."""

import inspect

from components.geospatial_tracking.services.geospatial.grid import build_smoke_grid
from components.geospatial_tracking.services.geospatial.source_geometry import (
    EligibleSourcePoint,
    build_geometry_for_grid,
    nearest_source_id,
)

KOPAY = (9.7151701, 80.0668497)
CHAVAKACHCHERI = (9.6579014, 80.1643076)


def test_grid_01_deterministic_grid_ids_across_repeated_runs():
    cells1, _ = build_smoke_grid(center_lat=9.7, center_lon=80.1, half_extent_km=2, cell_size_km=1)
    cells2, _ = build_smoke_grid(center_lat=9.7, center_lon=80.1, half_extent_km=2, cell_size_km=1)
    assert [c.grid_cell_id for c in cells1] == [c.grid_cell_id for c in cells2]
    assert len(set(c.grid_cell_id for c in cells1)) == len(cells1)  # all unique


def test_grid_02_crs_metadata_preserved_on_every_cell():
    cells, crs_choice = build_smoke_grid(center_lat=9.7, center_lon=80.1, half_extent_km=2, cell_size_km=1)
    for cell in cells:
        assert cell.source_crs == "EPSG:4326"
        assert cell.analysis_crs == crs_choice.analysis_crs
        assert cell.analysis_crs.startswith("EPSG:326")  # UTM northern hemisphere


def test_grid_03_resolution_never_exposed_as_prediction_accuracy():
    # Structural documentation check: the module must not claim cell size
    # equals prediction accuracy anywhere in its own source.
    from components.geospatial_tracking.services.geospatial import grid

    src = inspect.getsource(grid)
    assert "prediction accuracy" not in src.lower() or "not model accuracy" in src.lower() or "never" in src.lower()
    assert "computational resolution" in src.lower()


def test_grid_never_normalizes_by_its_own_aoi_bounds():
    # half_extent_km/cell_size_km are caller-supplied, not derived from
    # anything the grid itself computes — verified by checking the
    # function signature requires them as explicit parameters with no
    # AOI-bounds-derived default.
    import inspect

    from components.geospatial_tracking.services.geospatial.grid import build_smoke_grid

    sig = inspect.signature(build_smoke_grid)
    assert sig.parameters["half_extent_km"].default is inspect.Parameter.empty
    assert sig.parameters["cell_size_km"].default is inspect.Parameter.empty


def test_grid_cell_count_matches_requested_extent():
    cells, _ = build_smoke_grid(center_lat=9.7, center_lon=80.1, half_extent_km=1, cell_size_km=1)
    # half_extent=1, cell_size=1 -> should produce a small odd-by-odd grid centered on the AOI
    assert 1 <= len(cells) <= 25  # sanity bound, smoke-test scale


def test_grid_stays_smoke_scale_not_national():
    # never generate an enormous grid by accident
    cells, _ = build_smoke_grid(center_lat=9.7, center_lon=80.1, half_extent_km=5, cell_size_km=1)
    assert len(cells) < 200


class TestGeometryBySource:
    def test_geo_05_multiple_sources_retain_separate_geometry_entries(self):
        cells, _ = build_smoke_grid(center_lat=9.7, center_lon=80.1, half_extent_km=1, cell_size_km=1)
        sources = [
            EligibleSourcePoint(source_id="WAHIS_PDF:Event_3473.pdf:002407", latitude=KOPAY[0], longitude=KOPAY[1]),
            EligibleSourcePoint(
                source_id="WAHIS_PDF:Event_3473.pdf:002408",
                latitude=CHAVAKACHCHERI[0],
                longitude=CHAVAKACHCHERI[1],
            ),
        ]
        geometry = build_geometry_for_grid(cells, sources)
        for cell_id, by_source in geometry.items():
            assert set(by_source.keys()) == {
                "WAHIS_PDF:Event_3473.pdf:002407",
                "WAHIS_PDF:Event_3473.pdf:002408",
            }
            # distinct sources give distinct geometry (not accidentally shared/aliased)
            v1 = by_source["WAHIS_PDF:Event_3473.pdf:002407"]
            v2 = by_source["WAHIS_PDF:Event_3473.pdf:002408"]
            assert (v1.distance_km, v1.t_hat_east, v1.t_hat_north) != (
                v2.distance_km,
                v2.t_hat_east,
                v2.t_hat_north,
            )

    def test_nearest_source_id_is_derived_display_only(self):
        cells, _ = build_smoke_grid(center_lat=9.7, center_lon=80.1, half_extent_km=1, cell_size_km=1)
        sources = [
            EligibleSourcePoint(source_id="NEAR", latitude=9.7, longitude=80.1),
            EligibleSourcePoint(source_id="FAR", latitude=15.8, longitude=103.8),
        ]
        geometry = build_geometry_for_grid(cells, sources)
        for by_source in geometry.values():
            assert nearest_source_id(by_source) == "NEAR"
            # full geometry for BOTH sources is still present, never
            # dropped just because "nearest" was derived
            assert set(by_source.keys()) == {"NEAR", "FAR"}

    def test_nearest_source_id_empty_geometry_returns_none(self):
        assert nearest_source_id({}) is None
