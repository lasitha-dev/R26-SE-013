"""Checkpoint 7A Part 31: production scientific-grid tests —
GRID7A-01..10, plus DOMAIN-01 (t0-safety) and DOMAIN-05
(no-biological-label) structural checks."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from components.geospatial_tracking.services.geospatial.scientific_grid import (
    DOMAIN_MODE_SOURCE_BUFFER_UNION,
    ScientificGridConfig,
    build_scientific_grid,
    build_scientific_grid_snapshot,
    build_source_buffer_union_domain,
)
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint, build_geometry_for_grid


def _sources(coords) -> list[EligibleSourcePoint]:
    return [EligibleSourcePoint(source_id=f"S{i}", latitude=lat, longitude=lon) for i, (lat, lon) in enumerate(coords)]


def test_grid7a_01_area_is_metric_not_degree_squared():
    # A naive lat/lon-degree-squared "area" would shrink dramatically at
    # high latitude relative to the equator for the SAME cell_size_km.
    # A real UTM-metric grid must not: both should stay close to
    # cell_size_km^2 regardless of latitude.
    config = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    for lat in (1.0, 55.0):
        domain = build_source_buffer_union_domain(_sources([(lat, 100.0)]), domain_distance_km=25.0)
        cells = build_scientific_grid(domain, config=config, id_prefix="T")
        assert cells
        for c in cells:
            assert abs(c.area_km2 - config.cell_size_km ** 2) / (config.cell_size_km ** 2) < 0.05


def test_grid7a_02_model_development_pipeline_never_imports_build_smoke_grid():
    pkg_dir = Path(__file__).resolve().parents[1] / "services" / "model_development"
    offenders = []
    for py_file in pkg_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.names:
                for alias in node.names:
                    if alias.name == "build_smoke_grid":
                        offenders.append(str(py_file))
    assert not offenders, f"model_development pipeline must never import build_smoke_grid: {offenders}"


def test_grid7a_03_same_config_input_deterministic_grid_id():
    sources = _sources([(15.0, 101.0), (15.2, 101.3)])
    domain1 = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    domain2 = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    config = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    cells1 = build_scientific_grid(domain1, config=config, id_prefix="T")
    cells2 = build_scientific_grid(domain2, config=config, id_prefix="T")
    snap1 = build_scientific_grid_snapshot(forecast_origin_id="ORIGIN:X:2021-01-01", t0="2021-01-01", active_source_ids=["S0", "S1"], domain=domain1, config=config, cells=cells1)
    snap2 = build_scientific_grid_snapshot(forecast_origin_id="ORIGIN:X:2021-01-01", t0="2021-01-01", active_source_ids=["S0", "S1"], domain=domain2, config=config, cells=cells2)
    assert snap1.grid_snapshot_id == snap2.grid_snapshot_id


def test_grid7a_04_changed_cell_size_changes_grid_id():
    sources = _sources([(15.0, 101.0)])
    domain = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    config_a = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    config_b = ScientificGridConfig(cell_size_km=2.5, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    cells_a = build_scientific_grid(domain, config=config_a, id_prefix="T")
    cells_b = build_scientific_grid(domain, config=config_b, id_prefix="T")
    snap_a = build_scientific_grid_snapshot(forecast_origin_id="O", t0="2021-01-01", active_source_ids=["S0"], domain=domain, config=config_a, cells=cells_a)
    snap_b = build_scientific_grid_snapshot(forecast_origin_id="O", t0="2021-01-01", active_source_ids=["S0"], domain=domain, config=config_b, cells=cells_b)
    assert snap_a.grid_snapshot_id != snap_b.grid_snapshot_id


def test_grid7a_05_changed_domain_distance_changes_grid_id():
    sources = _sources([(15.0, 101.0)])
    config_25 = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    config_50 = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=50.0)
    domain_25 = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    domain_50 = build_source_buffer_union_domain(sources, domain_distance_km=50.0)
    cells_25 = build_scientific_grid(domain_25, config=config_25, id_prefix="T")
    cells_50 = build_scientific_grid(domain_50, config=config_50, id_prefix="T")
    snap_25 = build_scientific_grid_snapshot(forecast_origin_id="O", t0="2021-01-01", active_source_ids=["S0"], domain=domain_25, config=config_25, cells=cells_25)
    snap_50 = build_scientific_grid_snapshot(forecast_origin_id="O", t0="2021-01-01", active_source_ids=["S0"], domain=domain_50, config=config_50, cells=cells_50)
    assert snap_25.grid_snapshot_id != snap_50.grid_snapshot_id


def test_grid7a_06_all_grid_polygons_valid():
    sources = _sources([(15.0, 101.0), (16.0, 102.0)])
    domain = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    config = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    cells = build_scientific_grid(domain, config=config, id_prefix="T")
    assert cells
    for c in cells:
        assert c.polygon().is_valid


def test_grid7a_07_all_cell_areas_positive():
    sources = _sources([(15.0, 101.0)])
    domain = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    config = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    cells = build_scientific_grid(domain, config=config, id_prefix="T")
    assert cells
    assert all(c.area_km2 > 0 for c in cells)


def test_grid7a_08_all_eligible_sources_represented_inside_domain():
    sources = _sources([(15.0, 101.0), (15.5, 101.5), (14.5, 100.5)])
    domain = build_source_buffer_union_domain(sources, domain_distance_km=30.0)
    minx, miny, maxx, maxy = domain.bounds_utm
    from components.geospatial_tracking.services.geospatial.crs import build_transformer
    to_utm = build_transformer(domain.crs_choice.source_crs, domain.crs_choice.analysis_crs)
    for s in sources:
        x, y = to_utm.transform(s.longitude, s.latitude)
        assert minx <= x <= maxx
        assert miny <= y <= maxy


def test_grid7a_09_source_specific_geometry_exists_for_every_cell_source_pair():
    sources = _sources([(15.0, 101.0), (15.2, 101.2)])
    domain = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    config = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    cells = build_scientific_grid(domain, config=config, id_prefix="T")
    geometry = build_geometry_for_grid(cells, sources)
    assert len(geometry) == len(cells)
    for cell_id, by_source in geometry.items():
        assert set(by_source.keys()) == {s.source_id for s in sources}


def test_grid7a_10_ordering_does_not_affect_scientific_identity():
    sources = _sources([(15.0, 101.0), (15.2, 101.2)])
    domain = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    config = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    cells = build_scientific_grid(domain, config=config, id_prefix="T")
    snap_forward = build_scientific_grid_snapshot(forecast_origin_id="O", t0="2021-01-01", active_source_ids=["S1", "S0"], domain=domain, config=config, cells=cells)
    snap_reversed = build_scientific_grid_snapshot(forecast_origin_id="O", t0="2021-01-01", active_source_ids=["S0", "S1"], domain=domain, config=config, cells=list(reversed(cells)))
    assert snap_forward.grid_snapshot_id == snap_reversed.grid_snapshot_id


def test_domain01_grid_builder_signatures_never_accept_a_target_parameter():
    # scoped to functions actually DEFINED in this module -- re-exported
    # imports (e.g. crs.build_transformer's own `target_crs` parameter,
    # a coordinate-system concept unrelated to forecast targets) would
    # otherwise false-positive.
    from components.geospatial_tracking.services.geospatial import scientific_grid as mod
    forbidden = ("target", "future_outcome", "envelope")
    for name, fn in inspect.getmembers(mod, inspect.isfunction):
        if fn.__module__ != mod.__name__:
            continue
        params = {p.lower() for p in inspect.signature(fn).parameters}
        for forbidden_term in forbidden:
            assert not any(forbidden_term in p for p in params), f"{name} has a forbidden target-like parameter"


def test_domain05_domain_distance_field_never_labeled_spread_radius():
    # structural, not text-search (module docstrings legitimately EXPLAIN
    # what the field must never be called) -- inspect actual dataclass
    # field names only.
    from components.geospatial_tracking.services.geospatial import scientific_grid as mod
    import dataclasses
    forbidden = {"spread_radius_km", "transmission_boundary_km", "nominal_reach_km", "spread_front_speed"}
    for name, cls in inspect.getmembers(mod, inspect.isclass):
        if dataclasses.is_dataclass(cls):
            field_names = {f.lower() for f in cls.__dataclass_fields__}
            assert not (field_names & forbidden), f"{name} has forbidden field(s) {field_names & forbidden}"
