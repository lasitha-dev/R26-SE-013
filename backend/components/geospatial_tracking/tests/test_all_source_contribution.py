"""Checkpoint 7A.6 Part 33: all-eligible-sources-still-contribute tests
— ALLSRC-7A6-01..03."""

from __future__ import annotations

from components.geospatial_tracking.services.geospatial.scientific_grid import (
    DOMAIN_MODE_SOURCE_BUFFER_UNION,
    ScientificGridConfig,
    build_scientific_grid,
    build_source_buffer_union_domain,
)
from components.geospatial_tracking.services.geospatial.source_geometry import (
    EligibleSourcePoint,
    SourceToCellVector,
    build_geometry_for_grid,
)


def test_allsrc_7a6_01_disconnected_components_do_not_partition_hazard_source_eligibility():
    # two widely separated sources -> two disconnected domain components
    sources = [
        EligibleSourcePoint(source_id="S_NEAR", latitude=15.0, longitude=101.0),
        EligibleSourcePoint(source_id="S_FAR", latitude=25.0, longitude=110.0),
    ]
    domain = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    assert domain.n_components == 2
    config = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    cells = build_scientific_grid(domain, config=config, id_prefix="T")
    assert {c.component_index for c in cells} == {0, 1}  # cells genuinely exist in both components

    # ALL sources (not component-filtered) are passed for hazard geometry
    geometry = build_geometry_for_grid(cells, sources)
    for cell in cells:
        assert set(geometry[cell.grid_cell_id].keys()) == {"S_NEAR", "S_FAR"}


def test_allsrc_7a6_02_cell_in_component_a_receives_geometry_for_source_in_component_b():
    sources = [
        EligibleSourcePoint(source_id="S_A", latitude=15.0, longitude=101.0),
        EligibleSourcePoint(source_id="S_B", latitude=25.0, longitude=110.0),
    ]
    domain = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    config = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    cells = build_scientific_grid(domain, config=config, id_prefix="T")
    component_a_cells = [c for c in cells if c.component_index == 0]
    assert component_a_cells
    geometry = build_geometry_for_grid(component_a_cells, sources)
    for cell in component_a_cells:
        assert "S_B" in geometry[cell.grid_cell_id]  # the DISTANT source's geometry is still present -- never zeroed by component membership
        vec = geometry[cell.grid_cell_id]["S_B"]
        assert vec.distance_km > 500.0  # genuinely far, but present -- the kernel (not this module) may later make it numerically small


def test_allsrc_7a6_03_no_component_membership_field_can_zero_a_source_contribution():
    forbidden = {"component_index", "component_id", "in_component", "excluded_by_component"}
    field_names = {f.lower() for f in SourceToCellVector.__dataclass_fields__}
    assert not (field_names & forbidden)
    source_field_names = {f.lower() for f in EligibleSourcePoint.__dataclass_fields__}
    assert not (source_field_names & forbidden)
