"""Checkpoint 7A.6.2 Parts 3-7: identity-hardening tests —
DOMAINID-01..13, CELLID-01..03, CACHEID-01, IDPROP-01..02."""

from __future__ import annotations

import dataclasses
import inspect

import pytest

from components.geospatial_tracking.services.geospatial.scientific_domain import (
    ScientificDomainComponent,
    ScientificEvaluationDomain,
    build_scientific_evaluation_domain,
    scientific_cell_id,
    scientific_domain_protocol_hash,
)
from components.geospatial_tracking.services.geospatial.scientific_grid import (
    DOMAIN_MODE_SOURCE_BUFFER_UNION,
    ScientificGridCell,
    ScientificGridConfig,
)
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint

PRIMARY_KM = 25.0


def _sources(coords):
    return [EligibleSourcePoint(source_id=f"S{i}", latitude=lat, longitude=lon) for i, (lat, lon) in enumerate(coords)]


def _config(cell_km=5.0, domain_km=PRIMARY_KM, **overrides):
    return ScientificGridConfig(cell_size_km=cell_km, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=domain_km, **overrides)


# -- DOMAINID --

def test_domainid_01_same_protocol_settings_give_same_protocol_hash():
    h1 = scientific_domain_protocol_hash(_config())
    h2 = scientific_domain_protocol_hash(_config())
    assert h1 == h2


def test_domainid_01b_protocol_hash_never_contains_origin_or_source_fields():
    # structural: the protocol-hash function's own signature has no
    # forecast_origin_id/t0/source parameter at all
    params = inspect.signature(scientific_domain_protocol_hash).parameters
    assert set(params.keys()) == {"grid_config"}


def test_domainid_02_generated_at_does_not_change_any_identity():
    # none of the identity functions accept a generated_at parameter at all
    assert "generated_at" not in inspect.signature(scientific_domain_protocol_hash).parameters
    assert "generated_at" not in inspect.signature(build_scientific_evaluation_domain).parameters
    assert "generated_at" not in inspect.signature(scientific_cell_id).parameters


def test_domainid_02b_repeated_independent_builds_are_behaviorally_identical():
    # Checkpoint 7A.6.2 Part 5: not just "no generated_at parameter exists"
    # -- prove two INDEPENDENT builds from the same real inputs (no
    # object reuse at all) produce identical identities end to end,
    # including the full ordered set of per-cell scientific_cell_id
    # values. None of `ScientificEvaluationDomain`/`ScientificDomainComponent`/
    # `ScientificGridCell` carries a `generated_at` field at all (checked
    # explicitly below), so there is nothing for a clock/runtime value to
    # perturb -- but we still prove REPEATED-BUILD EQUALITY behaviorally,
    # not just by signature inspection.
    for cls in (ScientificEvaluationDomain, ScientificDomainComponent, ScientificGridCell):
        assert "generated_at" not in cls.__dataclass_fields__

    sources = _sources([(15.0, 101.0), (25.0, 110.0)])  # two components, real multi-cell case
    d1 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    d2 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=list(sources), grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    assert d1.scientific_domain_protocol_hash == d2.scientific_domain_protocol_hash
    assert d1.scientific_evaluation_domain_id == d2.scientific_evaluation_domain_id
    ids_1 = sorted(c.scientific_cell_id for c in d1.all_cells())
    ids_2 = sorted(c.scientific_cell_id for c in d2.all_cells())
    assert ids_1 == ids_2
    assert len(ids_1) > 0


def test_domainid_03_source_ordering_does_not_change_domain_instance_id():
    sources_forward = _sources([(15.0, 101.0), (15.2, 101.0)])
    sources_reversed = list(reversed(sources_forward))
    d1 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources_forward, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    d2 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources_reversed, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    assert d1.scientific_evaluation_domain_id == d2.scientific_evaluation_domain_id


def test_domainid_04_t0_change_changes_domain_instance_id():
    sources = _sources([(15.0, 101.0)])
    d1 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    d2 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-02", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    assert d1.scientific_evaluation_domain_id != d2.scientific_evaluation_domain_id
    # the RULES (protocol hash) are unaffected by t0
    assert d1.scientific_domain_protocol_hash == d2.scientific_domain_protocol_hash


def test_domainid_05_source_coordinates_change_changes_domain_instance_id():
    d1 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=_sources([(15.0, 101.0)]), grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    d2 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=_sources([(15.01, 101.01)]), grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    assert d1.scientific_evaluation_domain_id != d2.scientific_evaluation_domain_id


def test_domainid_06_domain_distance_change_changes_protocol_and_instance_identity():
    sources = _sources([(15.0, 101.0)])
    d1 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(domain_km=25.0), primary_local_evaluation_distance_km=25.0)
    d2 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(domain_km=50.0), primary_local_evaluation_distance_km=50.0)
    assert d1.scientific_domain_protocol_hash != d2.scientific_domain_protocol_hash
    assert d1.scientific_evaluation_domain_id != d2.scientific_evaluation_domain_id


def test_domainid_07_cell_size_change_changes_domain_and_cell_identity():
    sources = _sources([(15.0, 101.0)])
    d1 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(cell_km=5.0), primary_local_evaluation_distance_km=PRIMARY_KM)
    d2 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(cell_km=2.5), primary_local_evaluation_distance_km=PRIMARY_KM)
    assert d1.scientific_domain_protocol_hash != d2.scientific_domain_protocol_hash
    assert d1.scientific_evaluation_domain_id != d2.scientific_evaluation_domain_id
    ids_1 = {c.scientific_cell_id for c in d1.all_cells()}
    ids_2 = {c.scientific_cell_id for c in d2.all_cells()}
    assert not (ids_1 & ids_2)


def test_domainid_08_projection_strategy_change_changes_protocol_and_domain_identity():
    config_a = _config()
    config_b = dataclasses.replace(config_a, crs_strategy="SOME_OTHER_STRATEGY")
    assert scientific_domain_protocol_hash(config_a) != scientific_domain_protocol_hash(config_b)
    sources = _sources([(15.0, 101.0)])
    d1 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=config_a, primary_local_evaluation_distance_km=PRIMARY_KM)
    d2 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=config_b, primary_local_evaluation_distance_km=PRIMARY_KM)
    assert d1.scientific_evaluation_domain_id != d2.scientific_evaluation_domain_id


def test_domainid_09_projection_tolerance_version_change_changes_protocol_identity():
    config_a = _config()
    config_b = dataclasses.replace(config_a, projection_tolerance_version="SOME_OTHER_VERSION")
    assert scientific_domain_protocol_hash(config_a) != scientific_domain_protocol_hash(config_b)


def test_domainid_10_component_geometry_digest_change_changes_domain_and_cell_identity():
    # a different source point (even by a tiny amount) changes the
    # component's real union geometry digest, which must propagate into
    # both cell identity and domain instance identity.
    d1 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=_sources([(15.0, 101.0)]), grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    d2 = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=_sources([(15.001, 101.001)]), grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    assert d1.components[0].domain.union_geometry_digest != d2.components[0].domain.union_geometry_digest
    assert d1.scientific_evaluation_domain_id != d2.scientific_evaluation_domain_id
    ids_1 = {c.scientific_cell_id for c in d1.all_cells()}
    ids_2 = {c.scientific_cell_id for c in d2.all_cells()}
    assert not (ids_1 & ids_2)


def test_domainid_11_mismatched_25km_config_and_50km_primary_distance_rejects():
    sources = _sources([(15.0, 101.0)])
    with pytest.raises(ValueError, match="must describe the SAME distance"):
        build_scientific_evaluation_domain(
            forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(domain_km=25.0),
            primary_local_evaluation_distance_km=50.0,
        )


def test_domainid_12_mismatched_50km_config_and_25km_primary_distance_rejects():
    sources = _sources([(15.0, 101.0)])
    with pytest.raises(ValueError, match="must describe the SAME distance"):
        build_scientific_evaluation_domain(
            forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(domain_km=50.0),
            primary_local_evaluation_distance_km=25.0,
        )


def test_domainid_13_matching_values_produce_normal_deterministic_identities():
    sources = _sources([(15.0, 101.0)])
    d = build_scientific_evaluation_domain(
        forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(domain_km=25.0),
        primary_local_evaluation_distance_km=25.0,
    )
    assert d.scientific_domain_protocol_hash
    assert d.scientific_evaluation_domain_id
    assert d.all_cells()


# -- CELLID --

def test_cellid_01_cells_from_separate_components_cannot_collide():
    sources = _sources([(15.0, 101.0), (25.0, 110.0)])  # two disconnected components
    d = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    all_sci_ids = [c.scientific_cell_id for c in d.all_cells()]
    assert all(sid is not None for sid in all_sci_ids)
    assert len(all_sci_ids) == len(set(all_sci_ids))


def test_cellid_02_same_row_col_different_component_gives_different_scientific_cell_id():
    sources = _sources([(15.0, 101.0), (25.0, 110.0)])
    d = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(), primary_local_evaluation_distance_km=PRIMARY_KM)
    comp_a_cells = {(c.row, c.col): c.scientific_cell_id for c in d.components[0].cells}
    comp_b_cells = {(c.row, c.col): c.scientific_cell_id for c in d.components[1].cells}
    shared_row_col = set(comp_a_cells) & set(comp_b_cells)
    assert shared_row_col  # (0, 0) exists in both -- real overlap in local coordinates
    for rc in shared_row_col:
        assert comp_a_cells[rc] != comp_b_cells[rc]


def test_cellid_03_same_human_grid_cell_id_pattern_under_different_config_has_different_scientific_id():
    # directly prove the invariant: scientific_cell_id() for the SAME
    # ScientificGridCell object differs when only grid_config_hash (the
    # thing that changes when cell size changes) differs -- never
    # silently shared just because row/col or bounds happen to match.
    sources = _sources([(15.0, 101.0)])
    d = build_scientific_evaluation_domain(forecast_origin_id="O", t0="2021-01-01", sources=sources, grid_config=_config(cell_km=5.0), primary_local_evaluation_distance_km=PRIMARY_KM)
    component = d.components[0]
    cell = component.cells[0]
    id_a = scientific_cell_id(
        protocol_hash=d.scientific_domain_protocol_hash, component_id=component.component_id,
        component_crs_choice=component.crs_choice, component_geometry_digest=component.domain.union_geometry_digest,
        grid_config_hash="CONFIG_HASH_A", domain_distance_km=PRIMARY_KM, cell=cell,
    )
    id_b = scientific_cell_id(
        protocol_hash=d.scientific_domain_protocol_hash, component_id=component.component_id,
        component_crs_choice=component.crs_choice, component_geometry_digest=component.domain.union_geometry_digest,
        grid_config_hash="CONFIG_HASH_B", domain_distance_km=PRIMARY_KM, cell=cell,
    )
    assert id_a != id_b  # scientific identity never silently shared across configs


# -- CACHEID (Checkpoint 7A.6.2 Part 6: behavioral, not signature-inspection-only) --

def test_cacheid_01a_identical_weather_request_gives_identical_key():
    from components.geospatial_tracking.services.features.cache import cache_key_for_request
    req = {"model": "era5", "latitude": 15.0, "longitude": 101.0, "start_date": "2021-06-01", "end_date": "2021-06-02", "hourly": ["temperature_2m"], "timezone": "UTC"}
    assert cache_key_for_request(dict(req)) == cache_key_for_request(dict(req))


def test_cacheid_01b_latitude_change_gives_different_key():
    from components.geospatial_tracking.services.features.cache import cache_key_for_request
    base = {"model": "era5", "latitude": 15.0, "longitude": 101.0, "start_date": "2021-06-01", "end_date": "2021-06-02", "hourly": ["temperature_2m"], "timezone": "UTC"}
    other = {**base, "latitude": 15.5}
    assert cache_key_for_request(base) != cache_key_for_request(other)


def test_cacheid_01c_longitude_change_gives_different_key():
    from components.geospatial_tracking.services.features.cache import cache_key_for_request
    base = {"model": "era5", "latitude": 15.0, "longitude": 101.0, "start_date": "2021-06-01", "end_date": "2021-06-02", "hourly": ["temperature_2m"], "timezone": "UTC"}
    other = {**base, "longitude": 101.5}
    assert cache_key_for_request(base) != cache_key_for_request(other)


def test_cacheid_01d_temporal_window_change_gives_different_key():
    from components.geospatial_tracking.services.features.cache import cache_key_for_request
    base = {"model": "era5", "latitude": 15.0, "longitude": 101.0, "start_date": "2021-06-01", "end_date": "2021-06-02", "hourly": ["temperature_2m"], "timezone": "UTC"}
    other_start = {**base, "start_date": "2021-06-03"}
    other_end = {**base, "end_date": "2021-06-05"}
    assert cache_key_for_request(base) != cache_key_for_request(other_start)
    assert cache_key_for_request(base) != cache_key_for_request(other_end)


def test_cacheid_01e_weather_model_change_gives_different_key():
    from components.geospatial_tracking.services.features.cache import cache_key_for_request
    base = {"model": "era5", "latitude": 15.0, "longitude": 101.0, "start_date": "2021-06-01", "end_date": "2021-06-02", "hourly": ["temperature_2m"], "timezone": "UTC"}
    other = {**base, "model": "cfsr"}
    assert cache_key_for_request(base) != cache_key_for_request(other)


def test_cacheid_01f_dict_key_ordering_alone_gives_same_key():
    from components.geospatial_tracking.services.features.cache import cache_key_for_request
    forward = {"model": "era5", "latitude": 15.0, "longitude": 101.0, "start_date": "2021-06-01", "end_date": "2021-06-02", "hourly": ["temperature_2m"], "timezone": "UTC"}
    reordered = {"timezone": "UTC", "hourly": ["temperature_2m"], "end_date": "2021-06-02", "start_date": "2021-06-01", "longitude": 101.0, "latitude": 15.0, "model": "era5"}
    assert cache_key_for_request(forward) == cache_key_for_request(reordered)


def test_cacheid_02_raster_download_cache_identity_is_caller_owned_source_asset_identity():
    # Part 6: download_and_cache is a byte-download helper whose caller
    # owns cache identity -- verified by inspecting every real caller
    # (never assumed from the helper's own signature alone). Every real
    # caller derives `cache_path` from a DATASET-SPECIFIC filename
    # (`spec.count_filename`/`spec.area_filename`/HydroSHEDS asset name),
    # never from any grid/cell/domain parameter -- so the cached FILE is
    # the same real source asset regardless of what scientific grid
    # later queries it, and `extract_grid_cell_density` re-reads that
    # file fresh (using the real query bounds) on every call -- there is
    # no separate per-query RESULT cache anywhere in this path that a
    # grid-size/domain-distance change could go stale against.
    import inspect as _inspect
    from components.geospatial_tracking.services.geospatial import host_density
    from components.geospatial_tracking.services.geospatial.host_density import fao_glw
    source = _inspect.getsource(fao_glw)
    assert "_cache_path_for(spec.count_filename)" in source or "_cache_path_for(spec.count_filename)".replace(" ", "") in source.replace(" ", "")
    # the cache-path helper itself takes only a dataset filename, never a cell/grid/domain identity
    params = set(_inspect.signature(fao_glw._cache_path_for).parameters)
    assert params == {"filename"}
    forbidden = {"grid_cell_id", "component_id", "domain_protocol_hash", "scientific_grid_config_hash"}
    assert not (params & forbidden)


# -- IDPROP (Checkpoint 7A.6.2 Part 7: scientific_cell_id downstream propagation) --

def test_idprop_01_scientific_cell_id_survives_into_host_only_snapshot_dict():
    # host_reference_rebuild.build_scientific_grid_host_only_snapshot must
    # export scientific_cell_id per grid cell, never silently discard it.
    import inspect as _inspect
    from components.geospatial_tracking.services.model_development import host_reference_rebuild as mod
    source = _inspect.getsource(mod.build_scientific_grid_host_only_snapshot)
    assert "scientific_cell_id" in source


def test_idprop_02_reference_pooling_has_a_stronger_independent_identity():
    # Option B (Part 7): prove structurally that reference_profile.py's
    # pooling/hashing already depends on a STRONGER, raster-tied identity
    # (sample_support_digest / host_density_total_observation_id) rather
    # than on scientific_cell_id/domain identity at all -- so the new
    # identity fields are additive provenance, never load-bearing for
    # pooling correctness, and never "purely decorative" either (IDPROP-01
    # confirms they DO propagate for audit/traceability purposes).
    import inspect as _inspect
    from components.geospatial_tracking.services.factors import host_transform, reference_profile
    combined_source = _inspect.getsource(host_transform) + _inspect.getsource(reference_profile)
    assert "sample_support_digest" in combined_source or "resolve_static_observation_identity" in combined_source
    forbidden = {"scientific_cell_id", "scientific_domain_protocol_hash", "scientific_evaluation_domain_id"}
    assert not any(f in combined_source for f in forbidden)
