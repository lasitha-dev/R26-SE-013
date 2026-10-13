"""Checkpoint 7A.5 Parts 33-34: true-domain grid tests (TRUEGRID-01..08)
and projection-safety tests (CRS7A5-01..05)."""

from __future__ import annotations

import shapely.geometry

from components.geospatial_tracking.services.geospatial.scientific_grid import (
    BUFFER_METHOD_PROJECTED_METRIC_UNION,
    DOMAIN_MODE_SOURCE_BUFFER_UNION,
    PROJECTION_CONTEXT_SAFE,
    PROJECTION_CONTEXT_UNSAFE,
    PROJECTION_DISTORTION_REL_TOL,
    PROJECTION_TOLERANCE_VERSION,
    ScientificGridConfig,
    assess_projection_safety,
    build_scientific_grid,
    build_scientific_grid_snapshot,
    build_source_buffer_union_domain,
    union_geometry_digest,
)
from components.geospatial_tracking.services.geospatial.crs import analysis_crs_for
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint


def _sources(coords) -> list[EligibleSourcePoint]:
    return [EligibleSourcePoint(source_id=f"S{i}", latitude=lat, longitude=lon) for i, (lat, lon) in enumerate(coords)]


def _config(cell_size_km=5.0, domain_distance_km=25.0) -> ScientificGridConfig:
    return ScientificGridConfig(cell_size_km=cell_size_km, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=domain_distance_km)


def test_truegrid_01_no_returned_cell_has_zero_intersection():
    domain = build_source_buffer_union_domain(_sources([(15.0, 101.0)]), domain_distance_km=25.0)
    cells = build_scientific_grid(domain, config=_config(), id_prefix="T")
    assert cells
    assert all(c.domain_overlap_area_km2 > 0.0 for c in cells)
    assert all(c.intersects_true_domain is True for c in cells)


def test_truegrid_02_disconnected_source_buffers_leave_no_cells_in_the_gap():
    # two sources ~500km apart, domain_distance_km=25 -- two clearly
    # disconnected circular buffers with a huge empty gap between them.
    domain = build_source_buffer_union_domain(_sources([(15.0, 101.0), (19.5, 101.0)]), domain_distance_km=25.0)
    assert domain.n_components == 2
    cells = build_scientific_grid(domain, config=_config(), id_prefix="T")
    # every returned cell must be near one of the two source clusters,
    # never in the empty band between them (roughly lat 15.3-19.2)
    for c in cells:
        assert c.centroid_lat < 15.5 or c.centroid_lat > 19.0, f"unexpected gap cell at lat={c.centroid_lat}"


def test_truegrid_03_sum_of_intersection_areas_reproduces_union_area():
    domain = build_source_buffer_union_domain(_sources([(15.0, 101.0), (19.5, 101.0)]), domain_distance_km=25.0)
    cells = build_scientific_grid(domain, config=_config(cell_size_km=1.0), id_prefix="T")
    total_overlap = sum(c.domain_overlap_area_km2 for c in cells)
    rel_diff = abs(total_overlap - domain.union_area_km2) / domain.union_area_km2
    assert rel_diff < 0.01  # documented software geometry tolerance -- fine cells should closely reproduce the true union area


def test_truegrid_04_old_bounding_box_only_cells_are_excluded():
    domain = build_source_buffer_union_domain(_sources([(15.0, 101.0)]), domain_distance_km=25.0)
    cells = build_scientific_grid(domain, config=_config(), id_prefix="T")
    total_cell_area = sum(c.area_km2 for c in cells)
    # the old (7A) bounding-box tiling would have covered bounding_box_area_km2 -- strictly more than the circular union's own area
    assert domain.bounding_box_area_km2() > domain.union_area_km2
    # every surviving cell has SOME overlap -- corner "gap" cells present in the old bbox tiling are gone
    assert all(c.domain_overlap_fraction > 0.0 for c in cells)


def test_truegrid_05_domain_overlap_fraction_deterministic():
    domain1 = build_source_buffer_union_domain(_sources([(15.0, 101.0)]), domain_distance_km=25.0)
    domain2 = build_source_buffer_union_domain(_sources([(15.0, 101.0)]), domain_distance_km=25.0)
    cells1 = {c.grid_cell_id: c.domain_overlap_fraction for c in build_scientific_grid(domain1, config=_config(), id_prefix="T")}
    cells2 = {c.grid_cell_id: c.domain_overlap_fraction for c in build_scientific_grid(domain2, config=_config(), id_prefix="T")}
    assert cells1 == cells2


def test_truegrid_06_true_union_geometry_participates_in_grid_identity():
    sources = _sources([(15.0, 101.0)])
    domain_a = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    domain_b = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    config = _config()
    cells_a = build_scientific_grid(domain_a, config=config, id_prefix="T")
    cells_b = build_scientific_grid(domain_b, config=config, id_prefix="T")
    snap_a = build_scientific_grid_snapshot(forecast_origin_id="O", t0="2021-01-01", active_source_ids=["S0"], domain=domain_a, config=config, cells=cells_a)
    snap_b = build_scientific_grid_snapshot(forecast_origin_id="O", t0="2021-01-01", active_source_ids=["S0"], domain=domain_b, config=config, cells=cells_b)
    assert snap_a.union_geometry_digest == snap_b.union_geometry_digest
    assert snap_a.grid_snapshot_id == snap_b.grid_snapshot_id

    # a materially different domain distance changes the union geometry digest
    domain_c = build_source_buffer_union_domain(sources, domain_distance_km=50.0)
    assert domain_c.union_geometry_digest != domain_a.union_geometry_digest


def test_truegrid_07_multipolygon_component_ordering_does_not_change_identity():
    poly_a = shapely.geometry.box(0, 0, 10, 10)
    poly_b = shapely.geometry.box(1000, 1000, 1010, 1010)
    union_forward = shapely.geometry.MultiPolygon([poly_a, poly_b])
    union_reversed = shapely.geometry.MultiPolygon([poly_b, poly_a])
    assert union_geometry_digest(union_forward) == union_geometry_digest(union_reversed)


def test_truegrid_08_target_inside_true_domain_has_an_assignable_scientific_cell():
    from components.geospatial_tracking.services.model_development.target_assignment import assign_target_to_scientific_grid
    from types import SimpleNamespace

    sources = _sources([(15.0, 101.0)])
    domain = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    cells = build_scientific_grid(domain, config=_config(), id_prefix="T")
    target = SimpleNamespace(forecast_origin_id="O", target_id="O::T1", target_event_id="T1", lead_days=2, latitude=15.0, longitude=101.0)
    assignment = assign_target_to_scientific_grid(target=target, cells=cells, domain=domain, sources=sources, crs_choice=domain.crs_choice)
    assert assignment.target_grid_cell_id is not None
    assert assignment.inside_evaluation_domain is True


# -- CRS7A5-01..05 --

def test_crs7a5_01_projected_buffer_is_never_mislabeled_geodesic():
    domain = build_source_buffer_union_domain(_sources([(15.0, 101.0)]), domain_distance_km=25.0)
    assert domain.buffer_method == BUFFER_METHOD_PROJECTED_METRIC_UNION
    assert "GEODESIC" not in domain.buffer_method


def test_crs7a5_02_local_compact_single_zone_context_passes_projection_safety():
    sources = _sources([(15.0, 101.0), (15.05, 101.05)])
    crs_choice = analysis_crs_for(15.0, 101.0)
    assessment = assess_projection_safety(sources, crs_choice=crs_choice, domain_distance_km=25.0)
    assert assessment.status == PROJECTION_CONTEXT_SAFE
    assert assessment.max_relative_distance_distortion <= PROJECTION_DISTORTION_REL_TOL


def test_crs7a5_03_artificial_wide_multi_zone_context_cannot_silently_pass():
    # two sources spanning ~4000km east-west, well beyond a single UTM
    # zone's safe planar approximation -- must be flagged UNSAFE, never
    # silently treated as fine.
    sources = _sources([(15.0, 80.0), (15.0, 140.0)])
    crs_choice = analysis_crs_for(15.0, 110.0)
    assessment = assess_projection_safety(sources, crs_choice=crs_choice, domain_distance_km=25.0)
    assert assessment.status == PROJECTION_CONTEXT_UNSAFE
    assert assessment.max_relative_distance_distortion > PROJECTION_DISTORTION_REL_TOL

    # and the grid builder must refuse to silently continue
    import pytest
    domain = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    assert domain.projection_safety.status == PROJECTION_CONTEXT_UNSAFE
    with pytest.raises(ValueError, match="PROJECTION_CONTEXT_UNSAFE"):
        build_scientific_grid(domain, config=_config(), id_prefix="T")


def test_crs7a5_04_projection_strategy_participates_in_scientific_grid_identity():
    config = _config()
    assert config.crs_strategy == "AOI_LOCAL_UTM"
    assert "crs_strategy" in config.config_dict()
    hash_default = config.scientific_grid_config_hash()
    import dataclasses
    config_other_strategy = dataclasses.replace(config, crs_strategy="SOME_OTHER_STRATEGY")
    assert config_other_strategy.scientific_grid_config_hash() != hash_default


def test_crs7a5_05_projection_tolerance_participates_in_protocol_identity():
    config = _config()
    assert config.projection_tolerance_version == PROJECTION_TOLERANCE_VERSION
    hash_default = config.scientific_grid_config_hash()
    import dataclasses
    config_other_tolerance = dataclasses.replace(config, projection_tolerance_version="SOME_OTHER_VERSION")
    assert config_other_tolerance.scientific_grid_config_hash() != hash_default
