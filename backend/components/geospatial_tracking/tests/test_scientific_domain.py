"""Checkpoint 7A.6.1 Parts 31-32: componentization tests (COMP-01..07)
and multi-CRS grid tests (MULTICRS-01..09)."""

from __future__ import annotations

import inspect

from components.geospatial_tracking.services.geospatial.crs import analysis_crs_for
from components.geospatial_tracking.services.geospatial.scientific_domain import (
    COMPONENT_EDGE_DISTANCE_KM_MULTIPLE,
    GRID_CELL_ASSIGNED,
    PROJECTION_COMPONENT_UNSAFE_AFTER_GEODESIC_COMPONENTIZATION,
    ScientificDomainComponent,
    ScientificEvaluationDomain,
    assign_target_to_scientific_evaluation_domain,
    build_geodesic_source_components,
    build_scientific_evaluation_domain,
    component_edge_distance_km,
    max_buffer_radial_relative_error,
)
from components.geospatial_tracking.services.geospatial.scientific_grid import (
    DOMAIN_MODE_SOURCE_BUFFER_UNION,
    PROJECTION_CONTEXT_SAFE,
    PROJECTION_DISTORTION_REL_TOL,
    ScientificGridConfig,
)
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint

PRIMARY_KM = 25.0


def _sources(coords):
    return [EligibleSourcePoint(source_id=f"S{i}", latitude=lat, longitude=lon) for i, (lat, lon) in enumerate(coords)]


def _config(cell_km=5.0):
    return ScientificGridConfig(cell_size_km=cell_km, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=PRIMARY_KM)


# -- COMP --

def test_comp_01_sources_within_50km_share_a_component():
    sources = _sources([(15.0, 101.0), (15.2, 101.0)])  # ~22km apart -- well within 50km
    groups = build_geodesic_source_components(sources, edge_distance_km=component_edge_distance_km(PRIMARY_KM))
    assert len(groups) == 1
    assert set(groups[0]) == {"S0", "S1"}


def test_comp_02_sources_beyond_50km_with_no_path_are_separate_components():
    sources = _sources([(15.0, 101.0), (25.0, 110.0)])  # >>50km apart, nothing connecting them
    groups = build_geodesic_source_components(sources, edge_distance_km=component_edge_distance_km(PRIMARY_KM))
    assert len(groups) == 2


def test_comp_03_chained_connectivity_forms_one_component_even_if_endpoints_far_apart():
    # A-B <=50km, B-C <=50km, but A-C > 50km directly -- must still be ONE component
    sources = _sources([(15.00, 101.00), (15.40, 101.00), (15.80, 101.00)])  # each consecutive pair ~44km, A-C ~89km
    from components.geospatial_tracking.services.geospatial.distance import distance_km
    d_ab = distance_km(15.00, 101.00, 15.40, 101.00)
    d_bc = distance_km(15.40, 101.00, 15.80, 101.00)
    d_ac = distance_km(15.00, 101.00, 15.80, 101.00)
    assert d_ab <= 50.0 and d_bc <= 50.0 and d_ac > 50.0
    groups = build_geodesic_source_components(sources, edge_distance_km=50.0)
    assert len(groups) == 1
    assert set(groups[0]) == {"S0", "S1", "S2"}


def test_comp_04_source_ordering_does_not_change_component_ids():
    sources_forward = _sources([(15.0, 101.0), (15.2, 101.0)])
    sources_reversed = list(reversed(sources_forward))
    domain_forward = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources_forward, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    domain_reversed = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources_reversed, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    ids_forward = sorted(c.component_id for c in domain_forward.components)
    ids_reversed = sorted(c.component_id for c in domain_reversed.components)
    assert ids_forward == ids_reversed
    assert domain_forward.scientific_evaluation_domain_id == domain_reversed.scientific_evaluation_domain_id


def test_comp_05_component_ids_differ_when_source_membership_changes():
    sources_a = _sources([(15.0, 101.0), (15.2, 101.0)])
    sources_b = _sources([(15.0, 101.0)])
    domain_a = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources_a, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    domain_b = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources_b, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    ids_a = {c.component_id for c in domain_a.components}
    ids_b = {c.component_id for c in domain_b.components}
    assert ids_a != ids_b


def test_comp_06_componentization_has_no_stdbscanconfig_parameter():
    import components.geospatial_tracking.services.geospatial.scientific_domain as mod
    for name, fn in inspect.getmembers(mod, inspect.isfunction):
        if fn.__module__ != mod.__name__:
            continue
        for p in inspect.signature(fn).parameters.values():
            assert "STDBSCANConfig" not in str(p.annotation)
        assert "st_config" not in inspect.signature(fn).parameters


def test_comp_07_component_terminology_has_no_causal_transmission_claim():
    import components.geospatial_tracking.services.geospatial.scientific_domain as mod
    source = inspect.getsource(mod)
    forbidden = ("transmission_cluster", "infection_chain", "causal_outbreak_group", "transmission_chain")
    lowered = source.lower()
    for f in forbidden:
        # module explicitly explains these are NOT what components are --
        # check no field/constant is literally named this way (structural)
        assert f"= \"{f}" not in lowered and f"'{f}" not in lowered
    for name, cls in inspect.getmembers(mod, inspect.isclass):
        if hasattr(cls, "__dataclass_fields__"):
            field_names = {f.lower() for f in cls.__dataclass_fields__}
            assert not (field_names & {"transmission_cluster_id", "infection_chain_id", "causal_group_id"})


# -- MULTICRS --

def test_multicrs_01_far_apart_disconnected_sources_use_separate_local_crs():
    sources = _sources([(15.0, 101.0), (45.0, -70.0)])  # Thailand vs. eastern North America -- wildly different UTM zones
    domain = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    assert len(domain.components) == 2
    crs_a = domain.components[0].crs_choice.analysis_crs
    crs_b = domain.components[1].crs_choice.analysis_crs
    assert crs_a != crs_b


def test_multicrs_02_no_parent_global_utm_required():
    field_names = {f.lower() for f in ScientificEvaluationDomain.__dataclass_fields__}
    assert "analysis_crs" not in field_names and "bounds_utm" not in field_names and "crs_choice" not in field_names


def test_multicrs_03_cell_carries_component_crs_provenance():
    sources = _sources([(15.0, 101.0)])
    domain = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    cells = domain.all_cells()
    assert cells
    for cell in cells:
        assert cell.analysis_crs == domain.components[0].crs_choice.analysis_crs


def test_multicrs_04_cell_ids_cannot_collide_across_components():
    sources = _sources([(15.0, 101.0), (25.0, 110.0)])  # two disconnected components
    domain = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    all_ids = [c.grid_cell_id for c in domain.all_cells()]
    assert len(all_ids) == len(set(all_ids))
    prefixes = {cid.split(":")[0] for cid in all_ids}
    assert len(prefixes) == 2  # each component's cells carry a distinct id prefix


def test_multicrs_05_no_empty_inter_component_gap_cells():
    sources = _sources([(15.0, 101.0), (19.5, 101.0)])  # far enough that buffers don't touch, close enough to be a real test
    domain = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    for cell in domain.all_cells():
        assert cell.centroid_lat < 15.5 or cell.centroid_lat > 19.0  # never in the gap band


def test_multicrs_06_every_returned_cell_has_positive_domain_overlap():
    sources = _sources([(15.0, 101.0)])
    domain = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    cells = domain.all_cells()
    assert cells
    assert all(c.domain_overlap_area_km2 > 0.0 for c in cells)


def test_multicrs_07_unsafe_component_hard_blocks_rather_than_silently_skipped():
    # a component with n_unsafe_components() > 0 must be VISIBLE, not
    # omitted. A component can only be geodesically connected via a
    # CHAIN of <=50km hops (never a single 6000km jump, which would
    # simply be two separate components) -- so a real unsafe component
    # requires a long chain spanning enough UTM zones to genuinely
    # distort a single shared CRS. Generate one along the equator.
    chain_coords = [(0.0, -20.0 + i * 0.4) for i in range(140)]  # ~44km hops, spans ~56 degrees longitude (~9-10 UTM zones)
    sources = _sources(chain_coords)
    domain = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    assert len(domain.components) == 1  # one long connected chain
    component = domain.components[0]
    assert component.is_safe is False
    assert component.cells == ()  # no distorted grid was silently built
    assert domain.n_unsafe_components() == 1  # visible, not hidden


def test_multicrs_08_real_safe_components_satisfy_source_source_distortion_tolerance():
    sources = _sources([(15.0, 101.0), (15.1, 101.1)])
    domain = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    for c in domain.components:
        if c.is_safe:
            assert c.projection_safety.status == PROJECTION_CONTEXT_SAFE
            assert c.projection_safety.max_relative_distance_distortion <= PROJECTION_DISTORTION_REL_TOL


def test_multicrs_09_real_safe_components_satisfy_radial_distortion_tolerance():
    sources = _sources([(15.0, 101.0)])
    domain = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    for c in domain.components:
        if c.is_safe:
            assert c.max_buffer_radial_relative_error <= PROJECTION_DISTORTION_REL_TOL


# -- component edge distance / radial helper sanity --

def test_component_edge_distance_is_double_the_envelope():
    assert component_edge_distance_km(25.0) == 50.0
    assert COMPONENT_EDGE_DISTANCE_KM_MULTIPLE == 2.0


def test_max_buffer_radial_relative_error_is_small_for_a_real_local_source():
    crs_choice = analysis_crs_for(15.0, 101.0)
    sources = _sources([(15.0, 101.0)])
    err = max_buffer_radial_relative_error(sources, crs_choice=crs_choice, domain_distance_km=25.0)
    assert err < PROJECTION_DISTORTION_REL_TOL
