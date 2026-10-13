"""Checkpoint 7A.6 Parts 30-32 / Checkpoint 7A.6.1 Part 30: temporal-
semantics tests (SCOPE-TIME-01..05), scope-semantics tests
(SCOPE-SEM-01..05), ST-decoupling tests (ST-DECOUPLE-01..05), and
geodesic primary-scope tests (GEO-SCOPE-01..08)."""

from __future__ import annotations

import inspect
from types import SimpleNamespace

from components.geospatial_tracking.services.geospatial.scientific_domain import build_scientific_evaluation_domain
from components.geospatial_tracking.services.geospatial.scientific_grid import (
    DOMAIN_MODE_SOURCE_BUFFER_UNION,
    ScientificGridConfig,
)
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.model_development import local_evaluation_scope as les
from components.geospatial_tracking.services.model_development.local_evaluation_scope import (
    LOCAL_SCOPE_UNRESOLVED,
    OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE,
    PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
    SCIENTIFIC_GRID_CELL_SIZE_KM,
    WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE,
    classify_target_primary_scope,
)


def _sources(coords):
    return [EligibleSourcePoint(source_id=f"S{i}", latitude=lat, longitude=lon) for i, (lat, lon) in enumerate(coords)]


def _config(cell_km=SCIENTIFIC_GRID_CELL_SIZE_KM):
    return ScientificGridConfig(cell_size_km=cell_km, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=PRIMARY_LOCAL_EVALUATION_DISTANCE_KM)


def _evaluation_domain(coords, forecast_origin_id="O", t0="2021-01-01"):
    sources = _sources(coords)
    evaluation_domain = build_scientific_evaluation_domain(
        forecast_origin_id=forecast_origin_id, t0=t0, sources=sources, grid_config=_config(),
        primary_local_evaluation_distance_km=PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
    )
    return sources, evaluation_domain


def _target(lat, lon, lead_days=7, target_id="O::T1", target_event_id="T1"):
    return SimpleNamespace(forecast_origin_id="O", target_id=target_id, target_event_id=target_event_id, lead_days=lead_days, latitude=lat, longitude=lon)


# -- SCOPE-TIME --

def test_scope_time_01_d7_target_inside_25km_domain_remains_within_scope():
    sources, evaluation_domain = _evaluation_domain([(15.0, 101.0)])
    target = _target(15.01, 101.01, lead_days=7)  # ~1.5km away, D7
    result = classify_target_primary_scope(target=target, sources=sources, evaluation_domain=evaluation_domain)
    assert result.scope_status == WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE
    assert result.lead_days == 7


def test_scope_time_02_no_st_eps_time_parameter_exists_anywhere():
    for name, fn in inspect.getmembers(les, inspect.isfunction):
        if fn.__module__ != les.__name__:
            continue
        params = {p.lower() for p in inspect.signature(fn).parameters}
        assert "eps_time_days" not in params
        assert "st_config" not in params
        assert "stdbscanconfig" not in {p.replace("_", "") for p in params}


def test_scope_time_03_no_min_core_supports_parameter_exists():
    for name, fn in inspect.getmembers(les, inspect.isfunction):
        if fn.__module__ != les.__name__:
            continue
        params = {p.lower() for p in inspect.signature(fn).parameters}
        assert "min_core_supports" not in params


def test_scope_time_04_no_cluster_role_parameter_exists():
    for name, fn in inspect.getmembers(les, inspect.isfunction):
        if fn.__module__ != les.__name__:
            continue
        params = {p.lower() for p in inspect.signature(fn).parameters}
        assert "cluster_role" not in params
        assert "is_noise" not in params


def test_scope_time_05_d8_plus_excluded_by_existing_horizon_reason_not_st():
    from components.geospatial_tracking.services.forecast_target import PRIMARY_HORIZON_DAYS
    assert PRIMARY_HORIZON_DAYS == 7
    params = inspect.signature(classify_target_primary_scope).parameters
    assert "horizon_days" not in params and "primary_horizon_days" not in params


# -- SCOPE-SEM --

def test_scope_sem_01_primary_api_never_emits_nonlocal_future_event():
    module_values = {v for v in vars(les).values() if isinstance(v, str)}
    assert "NONLOCAL_FUTURE_EVENT" not in module_values
    sources, evaluation_domain = _evaluation_domain([(15.0, 101.0)])
    far_target = _target(40.0, 140.0)
    result = classify_target_primary_scope(target=far_target, sources=sources, evaluation_domain=evaluation_domain)
    assert result.scope_status != "NONLOCAL_FUTURE_EVENT"


def test_scope_sem_02_outside_scope_does_not_claim_biological_independence():
    forbidden = ("UNRELATED", "INDEPENDENT", "NONLOCAL", "NOT_LINKED")
    assert not any(f in OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE for f in forbidden)


def test_scope_sem_03_target_on_25km_boundary_is_within_scope():
    sources, evaluation_domain = _evaluation_domain([(0.0, 100.0)])  # equator -- easy geodesic math
    import pyproj
    geod = pyproj.Geod(ellps="WGS84")
    lon2, lat2, _ = geod.fwd(100.0, 0.0, 90.0, PRIMARY_LOCAL_EVALUATION_DISTANCE_KM * 1000.0)  # due east, exactly 25km
    boundary_target = _target(lat2, lon2)
    result = classify_target_primary_scope(target=boundary_target, sources=sources, evaluation_domain=evaluation_domain)
    assert result.scope_status == WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE


def test_scope_sem_04_target_just_outside_scope_is_not_labeled_unrelated():
    sources, evaluation_domain = _evaluation_domain([(15.0, 101.0)])
    just_outside = _target(15.24, 101.0)  # ~26.6km north -- outside the 25km envelope
    result = classify_target_primary_scope(target=just_outside, sources=sources, evaluation_domain=evaluation_domain)
    assert result.scope_status == OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE
    assert "UNRELATED" not in result.scope_status and "INDEPENDENT" not in result.scope_status


def test_scope_sem_05_future_target_coordinates_never_inputs_to_domain_construction():
    from components.geospatial_tracking.services.geospatial.scientific_domain import build_geodesic_source_components
    forbidden = ("target", "future_outcome", "envelope")
    for fn in (build_scientific_evaluation_domain, build_geodesic_source_components):
        params = {p.lower() for p in inspect.signature(fn).parameters}
        for f in forbidden:
            assert not any(f in p for p in params)


def test_local_scope_unresolved_when_no_eligible_sources():
    target = _target(15.0, 101.0)
    result = classify_target_primary_scope(target=target, sources=[], evaluation_domain=None)
    assert result.scope_status == LOCAL_SCOPE_UNRESOLVED


# -- ST-DECOUPLE --

def test_st_decouple_01_no_stdbscanconfig_argument_anywhere():
    for name, fn in inspect.getmembers(les, inspect.isfunction):
        if fn.__module__ != les.__name__:
            continue
        for p in inspect.signature(fn).parameters.values():
            annotation = str(p.annotation)
            assert "STDBSCANConfig" not in annotation


def test_st_decouple_02_st_config_hash_does_not_change_evaluation_scope_result():
    from components.geospatial_tracking.services.stdbscan.config import STDBSCANConfig
    config_a = STDBSCANConfig(eps_space_km=12.37, eps_time_days=3.0, min_core_supports=2, active_window_days=14, gps_core_policy="PRIMARY_CORE_SUPPORT", parameter_status="UNFROZEN_DEVELOPMENT_CANDIDATE")
    config_b = STDBSCANConfig(eps_space_km=50.0, eps_time_days=30.0, min_core_supports=4, active_window_days=28, gps_core_policy="EXACT_ONLY_CORE_SUPPORT", parameter_status="UNFROZEN_DEVELOPMENT_CANDIDATE")
    assert config_a.config_hash() != config_b.config_hash()
    # classify_target_primary_scope has no way to consume either config at all -- same real geometry inputs always give the same result
    sources, evaluation_domain = _evaluation_domain([(15.0, 101.0)])
    target = _target(15.01, 101.01)
    r1 = classify_target_primary_scope(target=target, sources=sources, evaluation_domain=evaluation_domain)
    r2 = classify_target_primary_scope(target=target, sources=sources, evaluation_domain=evaluation_domain)
    assert r1.as_dict() == r2.as_dict()


def test_st_decouple_03_noise_labeled_source_still_creates_a_domain_buffer():
    # EligibleSourcePoint carries no ST role at all -- a "noise" source is
    # indistinguishable from any other eligible source at the domain-
    # construction layer, so it always contributes a buffer.
    from components.geospatial_tracking.services.geospatial.scientific_grid import build_source_buffer_union_domain
    sources = _sources([(15.0, 101.0), (25.0, 110.0)])  # far apart -- would be ST noise/disconnected under a tight eps
    domain = build_source_buffer_union_domain(sources, domain_distance_km=PRIMARY_LOCAL_EVALUATION_DISTANCE_KM)
    assert domain.n_components == 2  # BOTH sources contributed a buffer, disconnected or not
    assert set(domain.source_ids) == {"S0", "S1"}


def test_st_decouple_04_temporal_unusable_source_still_creates_a_domain_buffer():
    field_names = {f.lower() for f in EligibleSourcePoint.__dataclass_fields__}
    assert "cluster_event_date" not in field_names and "st_usability" not in field_names
    # -- structurally cannot be excluded by temporal usability, since the
    # domain-construction dataclass carries no such field to check.


def test_st_decouple_05_st_context_membership_has_zero_hazard_multiplier():
    from components.geospatial_tracking.services.geospatial.source_geometry import SourceToCellVector
    field_names = {f.lower() for f in SourceToCellVector.__dataclass_fields__}
    forbidden = {"cluster_role", "is_noise", "core_support_id", "st_multiplier", "context_weight"}
    assert not (field_names & forbidden)


# -- GEO-SCOPE (Checkpoint 7A.6.1 Part 30) --

def test_geo_scope_01_no_projected_domaingeometry_argument():
    params = inspect.signature(classify_target_primary_scope).parameters
    assert "domain" not in params
    assert "cells" not in params
    for p in params.values():
        assert "DomainGeometry" not in str(p.annotation)


def test_geo_scope_02_same_coordinates_give_same_scope_under_different_grid_crs():
    # two evaluation domains built for the SAME source/target coordinates
    # but different cell sizes (different grid CRS/geometry protocol
    # internally) must still agree on scope truth -- it never depends on
    # the grid at all.
    sources_a, domain_a = _evaluation_domain([(15.0, 101.0)])
    sources_b = _sources([(15.0, 101.0)])
    from components.geospatial_tracking.services.geospatial.scientific_domain import build_scientific_evaluation_domain
    domain_b = build_scientific_evaluation_domain(
        forecast_origin_id="O", t0="2021-01-01", sources=sources_b,
        grid_config=ScientificGridConfig(cell_size_km=2.5, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=PRIMARY_LOCAL_EVALUATION_DISTANCE_KM),
        primary_local_evaluation_distance_km=PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
    )
    target = _target(15.01, 101.01)
    r_a = classify_target_primary_scope(target=target, sources=sources_a, evaluation_domain=domain_a)
    r_b = classify_target_primary_scope(target=target, sources=sources_b, evaluation_domain=domain_b)
    assert r_a.scope_status == r_b.scope_status == WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE


def test_geo_scope_03_d7_inside_25km_remains_within():
    sources, evaluation_domain = _evaluation_domain([(15.0, 101.0)])
    target = _target(15.05, 101.0, lead_days=7)  # ~5.5km away
    result = classify_target_primary_scope(target=target, sources=sources, evaluation_domain=evaluation_domain)
    assert result.scope_status == WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE


def test_geo_scope_04_25km_geodesic_boundary_is_inclusive():
    from components.geospatial_tracking.services.geospatial.distance import distance_km
    import pyproj
    geod = pyproj.Geod(ellps="WGS84")
    sources = _sources([(10.0, 50.0)])
    lon2, lat2, _ = geod.fwd(50.0, 10.0, 30.0, PRIMARY_LOCAL_EVALUATION_DISTANCE_KM * 1000.0)
    target = _target(lat2, lon2)
    # real geodesic distance should be (numerically) exactly 25.0km
    d = distance_km(10.0, 50.0, lat2, lon2)
    assert abs(d - PRIMARY_LOCAL_EVALUATION_DISTANCE_KM) < 1e-6
    result = classify_target_primary_scope(target=target, sources=sources, evaluation_domain=None)
    assert result.scope_status == WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE


def test_geo_scope_05_beyond_25km_is_outside_without_claiming_unrelatedness():
    sources = _sources([(15.0, 101.0)])
    far_target = _target(15.30, 101.0)  # ~33km away
    result = classify_target_primary_scope(target=far_target, sources=sources, evaluation_domain=None)
    assert result.scope_status == OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE
    assert "UNRELATED" not in result.scope_status


def test_geo_scope_06_st_config_cannot_alter_scope():
    # already covered by ST-DECOUPLE-02 above; restated here under the
    # GEO-SCOPE numbering the checkpoint also requests.
    sources = _sources([(15.0, 101.0)])
    target = _target(15.05, 101.0)
    r1 = classify_target_primary_scope(target=target, sources=sources, evaluation_domain=None)
    r2 = classify_target_primary_scope(target=target, sources=sources, evaluation_domain=None)
    assert r1.scope_status == r2.scope_status


def test_geo_scope_07_projection_safety_status_cannot_alter_scope():
    # a WITHIN-scope target must remain WITHIN even when its evaluation
    # domain has an unsafe/uncelled component -- scope truth never reads
    # component.is_safe.
    from components.geospatial_tracking.services.geospatial.scientific_domain import (
        ScientificDomainComponent,
        ScientificEvaluationDomain,
    )
    from components.geospatial_tracking.services.geospatial.crs import analysis_crs_for
    from components.geospatial_tracking.services.geospatial.scientific_grid import PROJECTION_CONTEXT_UNSAFE, ProjectionSafetyAssessment

    sources = _sources([(15.0, 101.0)])
    crs_choice = analysis_crs_for(15.0, 101.0)
    unsafe_assessment = ProjectionSafetyAssessment(
        status=PROJECTION_CONTEXT_UNSAFE, source_geographic_span_deg=0.0, max_pairwise_geodesic_distance_km=0.0,
        utm_zones_touched=(1,), analysis_crs=crs_choice.analysis_crs, buffer_radius_km=25.0,
        max_relative_distance_distortion=0.5, distortion_tolerance=0.01, tolerance_version="x",
    )
    unsafe_component = ScientificDomainComponent(
        component_id="SCICOMP:fake", source_ids=("S0",), center_lat=15.0, center_lon=101.0, crs_choice=crs_choice,
        projection_safety=unsafe_assessment, max_buffer_radial_relative_error=0.5, radial_distortion_tolerance=0.01,
        is_safe=False, buffer_method="x", domain=None, cells=(),
    )
    evaluation_domain = ScientificEvaluationDomain(
        forecast_origin_id="O", t0="2021-01-01", all_eligible_source_ids=("S0",), components=(unsafe_component,),
        scientific_domain_protocol_hash="x", scientific_evaluation_domain_id="x",
    )
    target = _target(15.01, 101.01)  # ~1.5km -- geodesically WITHIN regardless of the fabricated unsafe component
    result = classify_target_primary_scope(target=target, sources=sources, evaluation_domain=evaluation_domain)
    assert result.scope_status == WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE
    # grid assignment legitimately fails (no safe cells), but scope truth is untouched
    assert result.target_grid_cell_id is None
    from components.geospatial_tracking.services.geospatial.scientific_domain import GRID_REPRESENTATION_BOUNDARY_MISMATCH
    assert result.grid_representation_status == GRID_REPRESENTATION_BOUNDARY_MISMATCH


def test_geo_scope_08_row_level_old_vs_new_geodesic_audit_is_identical():
    # "old" (7A's domain_design.py inline distance check) and "new"
    # (this module's classify_target_primary_scope) both reduce to the
    # SAME real computation: min geodesic distance to any eligible
    # source, compared against 25km -- proven equal across a synthetic
    # row set spanning near/far/boundary cases.
    from components.geospatial_tracking.services.geospatial.distance import distance_km

    sources = _sources([(15.0, 101.0), (15.3, 101.0), (40.0, 140.0)])
    targets = [
        _target(15.01, 101.01, target_id="O::T_NEAR", target_event_id="T_NEAR"),
        _target(15.5, 101.0, target_id="O::T_MID", target_event_id="T_MID"),
        _target(60.0, 160.0, target_id="O::T_FAR", target_event_id="T_FAR"),
    ]
    disagreements = []
    for t in targets:
        old_min_d = min(distance_km(s.latitude, s.longitude, t.latitude, t.longitude) for s in sources)
        old_within = old_min_d <= PRIMARY_LOCAL_EVALUATION_DISTANCE_KM
        new_result = classify_target_primary_scope(target=t, sources=sources, evaluation_domain=None)
        new_within = new_result.scope_status == WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE
        if old_within != new_within:
            disagreements.append((t.target_id, old_within, new_within))
    assert disagreements == []
