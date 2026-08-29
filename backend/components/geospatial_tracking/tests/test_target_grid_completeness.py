"""Checkpoint 7A.6.1 Part 33-34: target-grid-completeness tests
(TARGETGRID-01..05) and all-source-semantics tests (ALLSRC-7A61-01..03)."""

from __future__ import annotations

from types import SimpleNamespace

from components.geospatial_tracking.services.geospatial.scientific_domain import (
    GRID_CELL_ASSIGNED,
    GRID_REPRESENTATION_BOUNDARY_MISMATCH,
    ScientificDomainComponent,
    ScientificEvaluationDomain,
    assign_target_to_scientific_evaluation_domain,
    build_scientific_evaluation_domain,
)
from components.geospatial_tracking.services.geospatial.scientific_grid import (
    DOMAIN_MODE_SOURCE_BUFFER_UNION,
    ScientificGridConfig,
)
from components.geospatial_tracking.services.geospatial.source_geometry import (
    EligibleSourcePoint,
    build_geometry_for_grid,
)
from components.geospatial_tracking.services.model_development.local_evaluation_scope import (
    WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE,
    classify_target_primary_scope,
)

PRIMARY_KM = 25.0


def _sources(coords):
    return [EligibleSourcePoint(source_id=f"S{i}", latitude=lat, longitude=lon) for i, (lat, lon) in enumerate(coords)]


def _config(cell_km=5.0):
    return ScientificGridConfig(cell_size_km=cell_km, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=PRIMARY_KM)


def _target(lat, lon):
    return SimpleNamespace(forecast_origin_id="O", target_id="O::T1", target_event_id="T1", lead_days=3, latitude=lat, longitude=lon)


# -- TARGETGRID --

def test_targetgrid_01_every_synthetic_within_target_gets_a_grid_cell():
    sources = _sources([(15.0, 101.0)])
    evaluation_domain = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    target = _target(15.01, 101.01)
    cell_id, status = assign_target_to_scientific_evaluation_domain(target=target, evaluation_domain=evaluation_domain)
    assert cell_id is not None
    assert status == GRID_CELL_ASSIGNED


def test_targetgrid_02_outside_target_is_not_forced_into_nearest_cell():
    sources = _sources([(15.0, 101.0)])
    evaluation_domain = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    far_target = _target(40.0, 140.0)
    cell_id, status = assign_target_to_scientific_evaluation_domain(target=far_target, evaluation_domain=evaluation_domain)
    assert cell_id is None
    assert status == GRID_REPRESENTATION_BOUNDARY_MISMATCH


def test_targetgrid_03_geodesic_within_status_survives_grid_representation_failure():
    sources = _sources([(15.0, 101.0)])
    # fabricate an evaluation_domain whose component is unsafe (no cells)
    from components.geospatial_tracking.services.geospatial.crs import analysis_crs_for
    from components.geospatial_tracking.services.geospatial.scientific_grid import PROJECTION_CONTEXT_UNSAFE, ProjectionSafetyAssessment
    crs_choice = analysis_crs_for(15.0, 101.0)
    unsafe_assessment = ProjectionSafetyAssessment(status=PROJECTION_CONTEXT_UNSAFE, source_geographic_span_deg=0.0, max_pairwise_geodesic_distance_km=0.0, utm_zones_touched=(1,), analysis_crs=crs_choice.analysis_crs, buffer_radius_km=25.0, max_relative_distance_distortion=0.5, distortion_tolerance=0.01, tolerance_version="x")
    unsafe_component = ScientificDomainComponent(component_id="SCICOMP:fake", source_ids=("S0",), center_lat=15.0, center_lon=101.0, crs_choice=crs_choice, projection_safety=unsafe_assessment, max_buffer_radial_relative_error=0.5, radial_distortion_tolerance=0.01, is_safe=False, buffer_method="x", domain=None, cells=())
    evaluation_domain = ScientificEvaluationDomain(
        forecast_origin_id="O", t0="2021-01-01", all_eligible_source_ids=("S0",), components=(unsafe_component,),
        scientific_domain_protocol_hash="x", scientific_evaluation_domain_id="x",
    )
    target = _target(15.01, 101.01)  # geodesically ~1.5km -- WITHIN
    result = classify_target_primary_scope(target=target, sources=sources, evaluation_domain=evaluation_domain)
    assert result.scope_status == WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE
    assert result.target_grid_cell_id is None
    assert result.grid_representation_status == GRID_REPRESENTATION_BOUNDARY_MISMATCH


def test_targetgrid_04_grid_boundary_tie_break_remains_deterministic():
    sources = _sources([(15.0, 101.0)])
    evaluation_domain = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    target = _target(15.0, 101.0)  # dead-center -- deterministic regardless of internal cell ordering
    cell_id_1, _ = assign_target_to_scientific_evaluation_domain(target=target, evaluation_domain=evaluation_domain)
    cell_id_2, _ = assign_target_to_scientific_evaluation_domain(target=target, evaluation_domain=evaluation_domain)
    assert cell_id_1 == cell_id_2


def test_targetgrid_05_within_target_without_cell_is_detectable_for_a_pipeline_gate():
    # the checkpoint's real pass gate requires
    # n_within_scope_targets_without_grid_cell == 0 -- verify the
    # underlying signal (grid_representation_status) that a real audit
    # would use to compute that count is present and correct.
    sources = _sources([(15.0, 101.0)])
    evaluation_domain = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    within_target = _target(15.01, 101.01)
    result = classify_target_primary_scope(target=within_target, sources=sources, evaluation_domain=evaluation_domain)
    assert result.scope_status == WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE
    assert result.grid_representation_status == GRID_CELL_ASSIGNED
    assert result.target_grid_cell_id is not None


# -- ALLSRC-7A61 --

def test_allsrc_7a61_01_cell_in_component_a_has_geometry_for_source_in_component_b():
    sources = _sources([(15.0, 101.0), (25.0, 110.0)])
    evaluation_domain = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    component_a_cells = list(evaluation_domain.components[0].cells)
    assert component_a_cells
    geometry = build_geometry_for_grid(component_a_cells, sources)  # ALL origin sources, not just component A's own
    for cell in component_a_cells:
        assert set(geometry[cell.grid_cell_id].keys()) == {"S0", "S1"}


def test_allsrc_7a61_02_component_id_never_appears_as_hazard_multiplier_field():
    from components.geospatial_tracking.services.geospatial.source_geometry import SourceToCellVector
    field_names = {f.lower() for f in SourceToCellVector.__dataclass_fields__}
    forbidden = {"component_id", "component_multiplier", "component_weight"}
    assert not (field_names & forbidden)


def test_allsrc_7a61_03_geometry_count_per_cell_equals_full_eligible_source_count():
    sources = _sources([(15.0, 101.0), (25.0, 110.0), (15.05, 101.05)])
    evaluation_domain = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    all_cells = evaluation_domain.all_cells()
    assert all_cells
    geometry = build_geometry_for_grid(all_cells, sources)
    for cell in all_cells:
        assert len(geometry[cell.grid_cell_id]) == len(sources) == 3
