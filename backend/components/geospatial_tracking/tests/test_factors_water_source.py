"""Checkpoint 6D Part 36: water/source-strength tests — WATER-01..02,
SOURCE-01..04."""

from __future__ import annotations

import inspect

from components.geospatial_tracking.services.factors.contracts import NOT_YET_SCIENTIFICALLY_DEFINED
from components.geospatial_tracking.services.factors.source_strength import build_source_strength_status
from components.geospatial_tracking.services.factors.water_context import build_water_context_status


def test_water_01_distance_not_automatically_converted_to_risk_factor():
    cell = {"hydrology": {"feature_name": "distance_to_nearest_river_km", "value": 0.5, "units": "km", "status": "REAL", "dataset_version": "v1.0"}}
    result = build_water_context_status(cell=cell, feature_snapshot_id="SNAPSHOT:abc")
    # raw distance preserved in provenance...
    assert result.raw_values == (0.5,)
    # ...but never turned into a numeric transformed risk value
    assert result.transformed_value is None


def test_water_02_water_context_factor_not_yet_scientifically_defined():
    cell = {"hydrology": {"feature_name": "distance_to_nearest_river_km", "value": 0.5, "units": "km", "status": "REAL", "dataset_version": "v1.0"}}
    result = build_water_context_status(cell=cell, feature_snapshot_id="SNAPSHOT:abc")
    assert result.candidate_status == NOT_YET_SCIENTIFICALLY_DEFINED


def test_source_01_source_strength_not_derived_from_cases():
    params = set(inspect.signature(build_source_strength_status).parameters)
    assert not any(term in p.lower() for p in params for term in ("case", "death", "affected_animals"))


def test_source_02_source_strength_not_derived_from_dqs():
    params = set(inspect.signature(build_source_strength_status).parameters)
    assert not any("dqs" in p.lower() for p in params)


def test_source_03_source_strength_not_derived_from_st_cluster_role():
    params = set(inspect.signature(build_source_strength_status).parameters)
    assert not any(term in p.lower() for p in params for term in ("cluster_role", "cluster_size", "is_noise", "is_core"))


def test_source_04_real_source_strength_factor_not_yet_scientifically_defined():
    result = build_source_strength_status(source_id="WAHIS_PDF:Event_1.pdf:001")
    assert result.candidate_status == NOT_YET_SCIENTIFICALLY_DEFINED
    assert result.transformed_value is None
