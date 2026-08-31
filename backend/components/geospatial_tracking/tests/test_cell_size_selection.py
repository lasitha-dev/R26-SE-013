"""Checkpoint 7A.5 Part 36: cell-size engineering-selection tests —
CELL7A5-01..04."""

from __future__ import annotations

import inspect

from components.geospatial_tracking.services.geospatial.scientific_grid import (
    DOMAIN_MODE_SOURCE_BUFFER_UNION,
    ScientificGridConfig,
    build_scientific_grid,
    build_scientific_grid_snapshot,
    build_source_buffer_union_domain,
)
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.model_development import cell_size_selection as css
from components.geospatial_tracking.services.model_development.cell_size_selection import (
    CELL_SIZE_BLOCKED,
    CellSizeEngineeringAudit,
    build_cell_size_engineering_audit,
    select_frozen_cell_size,
)


def _sources(coords):
    return [EligibleSourcePoint(source_id=f"S{i}", latitude=lat, longitude=lon) for i, (lat, lon) in enumerate(coords)]


def test_cell7a5_01_selection_uses_engineering_diagnostics_only():
    audit = CellSizeEngineeringAudit(cell_size_km=5.0, n_contexts=1, all_polygons_valid=True, all_areas_positive=True, all_sources_represented=True, max_cells_per_context=10, mean_cells_per_context=10.0, within_feasibility_budget=True)
    distance, status = select_frozen_cell_size([audit])
    assert distance == 5.0
    assert status == "FROZEN_ENGINEERING_RESOLUTION"


def test_cell7a5_02_no_prediction_metric_parameter_exists():
    forbidden = {"score", "risk", "probability", "prediction", "capture", "auc"}
    for name, fn in inspect.getmembers(css, inspect.isfunction):
        if fn.__module__ != css.__name__:
            continue
        params = {p.lower() for p in inspect.signature(fn).parameters}
        assert not (params & forbidden), f"{name} has forbidden parameter(s) {params & forbidden}"
    for name, cls in inspect.getmembers(css, inspect.isclass):
        import dataclasses
        if dataclasses.is_dataclass(cls):
            field_names = {f.lower() for f in cls.__dataclass_fields__}
            assert not (field_names & forbidden), f"{cls.__name__} has forbidden field(s) {field_names & forbidden}"


def test_cell7a5_03_coarsest_candidate_satisfying_constraints_is_selected():
    audit_25 = CellSizeEngineeringAudit(cell_size_km=2.5, n_contexts=1, all_polygons_valid=True, all_areas_positive=True, all_sources_represented=True, max_cells_per_context=100, mean_cells_per_context=100.0, within_feasibility_budget=True)
    audit_50 = CellSizeEngineeringAudit(cell_size_km=5.0, n_contexts=1, all_polygons_valid=True, all_areas_positive=True, all_sources_represented=True, max_cells_per_context=25, mean_cells_per_context=25.0, within_feasibility_budget=True)
    distance, status = select_frozen_cell_size([audit_25, audit_50])
    assert distance == 5.0  # coarsest of the two qualifying candidates


def test_cell7a5_03b_blocked_when_no_candidate_qualifies():
    audit_25 = CellSizeEngineeringAudit(cell_size_km=2.5, n_contexts=1, all_polygons_valid=True, all_areas_positive=True, all_sources_represented=True, max_cells_per_context=999999, mean_cells_per_context=999999.0, within_feasibility_budget=False)
    audit_50 = CellSizeEngineeringAudit(cell_size_km=5.0, n_contexts=1, all_polygons_valid=False, all_areas_positive=True, all_sources_represented=True, max_cells_per_context=25, mean_cells_per_context=25.0, within_feasibility_budget=True)
    distance, status = select_frozen_cell_size([audit_25, audit_50])
    assert distance is None
    assert status == CELL_SIZE_BLOCKED


def test_cell7a5_04_changing_frozen_cell_size_changes_grid_identity():
    sources = _sources([(15.0, 101.0)])
    domain = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    config_a = ScientificGridConfig(cell_size_km=2.5, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    config_b = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    cells_a = build_scientific_grid(domain, config=config_a, id_prefix="T")
    cells_b = build_scientific_grid(domain, config=config_b, id_prefix="T")
    snap_a = build_scientific_grid_snapshot(forecast_origin_id="O", t0="2021-01-01", active_source_ids=["S0"], domain=domain, config=config_a, cells=cells_a)
    snap_b = build_scientific_grid_snapshot(forecast_origin_id="O", t0="2021-01-01", active_source_ids=["S0"], domain=domain, config=config_b, cells=cells_b)
    assert snap_a.grid_snapshot_id != snap_b.grid_snapshot_id
    assert config_a.scientific_grid_config_hash() != config_b.scientific_grid_config_hash()


def test_engineering_audit_builder_real_geometry():
    sources = _sources([(15.0, 101.0)])
    domain = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    config = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    cells = build_scientific_grid(domain, config=config, id_prefix="T")
    audit = build_cell_size_engineering_audit(cell_size_km=5.0, contexts_and_cells=[(domain, sources, cells)])
    assert audit.all_polygons_valid is True
    assert audit.all_areas_positive is True
    assert audit.all_sources_represented is True
    assert audit.max_cells_per_context == len(cells)
