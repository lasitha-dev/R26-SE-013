"""Checkpoint 7A.6 Part 34: grid-freeze tests — GRIDFREEZE-01..05."""

from __future__ import annotations

import dataclasses

from components.geospatial_tracking.services.geospatial.scientific_grid import (
    CELL_SIZE_STATUS_FROZEN_ENGINEERING_RESOLUTION,
    DOMAIN_DISTANCE_STATUS_FROZEN_OPERATIONAL_ENVELOPE,
    DOMAIN_MODE_SOURCE_BUFFER_UNION,
    ScientificGridConfig,
    build_scientific_grid,
    build_scientific_grid_snapshot,
    build_source_buffer_union_domain,
)
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.model_development.local_evaluation_scope import (
    PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
    PRIMARY_LOCAL_EVALUATION_DISTANCE_STATUS,
    SCIENTIFIC_GRID_CELL_SIZE_KM,
    SCIENTIFIC_GRID_CELL_SIZE_STATUS,
    SENSITIVITY_LOCAL_EVALUATION_DISTANCE_KM,
)


def _sources(coords):
    return [EligibleSourcePoint(source_id=f"S{i}", latitude=lat, longitude=lon) for i, (lat, lon) in enumerate(coords)]


def _frozen_primary_config() -> ScientificGridConfig:
    return ScientificGridConfig(
        cell_size_km=SCIENTIFIC_GRID_CELL_SIZE_KM, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION,
        domain_distance_km=PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
        domain_distance_status=DOMAIN_DISTANCE_STATUS_FROZEN_OPERATIONAL_ENVELOPE,
        cell_size_status=CELL_SIZE_STATUS_FROZEN_ENGINEERING_RESOLUTION,
    )


def test_gridfreeze_01_primary_config_is_25km_domain_5km_cells():
    assert PRIMARY_LOCAL_EVALUATION_DISTANCE_KM == 25.0
    assert SCIENTIFIC_GRID_CELL_SIZE_KM == 5.0
    config = _frozen_primary_config()
    assert config.domain_distance_km == 25.0
    assert config.cell_size_km == 5.0


def test_gridfreeze_02_25_labeled_operational_envelope_never_spread_radius():
    assert PRIMARY_LOCAL_EVALUATION_DISTANCE_STATUS == "FROZEN_OPERATIONAL_LOCAL_EVALUATION_ENVELOPE"
    config = _frozen_primary_config()
    assert config.domain_distance_status == "FROZEN_OPERATIONAL_LOCAL_EVALUATION_ENVELOPE"
    for forbidden in ("SPREAD_RADIUS", "TRANSMISSION_RADIUS", "KERNEL_SCALE"):
        assert forbidden not in config.domain_distance_status


def test_gridfreeze_03_5km_labeled_engineering_resolution_never_data_accuracy():
    assert SCIENTIFIC_GRID_CELL_SIZE_STATUS == "FROZEN_ENGINEERING_RESOLUTION"
    config = _frozen_primary_config()
    assert config.cell_size_status == "FROZEN_ENGINEERING_RESOLUTION"
    for forbidden in ("DATA_ACCURACY", "PREDICTION_ACCURACY", "BIOLOGICAL_ACCURACY"):
        assert forbidden not in config.cell_size_status


def test_gridfreeze_04_sensitivity_registration_cannot_silently_replace_primary():
    assert SENSITIVITY_LOCAL_EVALUATION_DISTANCE_KM == 50.0
    assert SENSITIVITY_LOCAL_EVALUATION_DISTANCE_KM != PRIMARY_LOCAL_EVALUATION_DISTANCE_KM
    config = _frozen_primary_config()
    assert config.domain_distance_km == PRIMARY_LOCAL_EVALUATION_DISTANCE_KM  # never silently the sensitivity value


def test_gridfreeze_05_changed_scope_distance_changes_protocol_identity():
    primary_config = _frozen_primary_config()
    sensitivity_config = dataclasses.replace(primary_config, domain_distance_km=SENSITIVITY_LOCAL_EVALUATION_DISTANCE_KM, domain_distance_status="UNFROZEN_DOMAIN_CANDIDATE")
    assert primary_config.scientific_grid_config_hash() != sensitivity_config.scientific_grid_config_hash()

    sources = _sources([(15.0, 101.0)])
    domain_primary = build_source_buffer_union_domain(sources, domain_distance_km=PRIMARY_LOCAL_EVALUATION_DISTANCE_KM)
    domain_sensitivity = build_source_buffer_union_domain(sources, domain_distance_km=SENSITIVITY_LOCAL_EVALUATION_DISTANCE_KM)
    cells_primary = build_scientific_grid(domain_primary, config=primary_config, id_prefix="T")
    cells_sensitivity = build_scientific_grid(domain_sensitivity, config=sensitivity_config, id_prefix="T")
    snap_primary = build_scientific_grid_snapshot(forecast_origin_id="O", t0="2021-01-01", active_source_ids=["S0"], domain=domain_primary, config=primary_config, cells=cells_primary)
    snap_sensitivity = build_scientific_grid_snapshot(forecast_origin_id="O", t0="2021-01-01", active_source_ids=["S0"], domain=domain_sensitivity, config=sensitivity_config, cells=cells_sensitivity)
    assert snap_primary.grid_snapshot_id != snap_sensitivity.grid_snapshot_id
