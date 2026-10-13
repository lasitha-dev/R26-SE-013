"""Checkpoint 6C.5 Part 25: hazard input-signature/snapshot identity
tests — HAZ-ID-01..09."""

from __future__ import annotations

import time

from components.geospatial_tracking.services.hazard.contracts import (
    CellHazardFactors,
    FactorStatus,
    FactorValue,
    HazardMixConfig,
    SourceGeometry,
    SourceHazardFactors,
    WindVector,
)
from components.geospatial_tracking.services.hazard.meteorology import CellMeteorology
from components.geospatial_tracking.services.hazard.protocol import HazardConfig
from components.geospatial_tracking.services.hazard.snapshot import build_hazard_snapshot, compute_hazard_input_signature_hash

_FIXTURE = FactorStatus.SOFTWARE_FIXTURE_ONLY.value


def _fv(v: float) -> FactorValue:
    return FactorValue(v, _FIXTURE)


def _cell_factors(host=0.8, cell_id="CELL1") -> CellHazardFactors:
    return CellHazardFactors(cell_id, host_factor=_fv(host), environmental_suitability_factor=_fv(0.6), water_context_factor=_fv(0.5))


def _config() -> HazardConfig:
    return HazardConfig(
        local_kernel_family="EXPONENTIAL", local_kernel_distance_scale_km=10.0,
        anisotropic_pathway_enabled=True, anisotropy_mode="MODULATING", anisotropy_kappa=1.0,
        wind_kernel_family="EXPONENTIAL", wind_kernel_distance_scale_km=10.0,
        mix=HazardMixConfig(local_weight=1.0, anisotropic_weight=1.0),
    )


def _signature_kwargs(*, host=0.8, strength=1.0, wind_u=2.0, distance_km=5.0, cell_ids=("CELL1",)):
    geometry_by_cell = {
        cid: {"A": SourceGeometry("A", cid, distance_km=distance_km, t_hat_east=1.0, t_hat_north=0.0)} for cid in cell_ids
    }
    cell_factors_by_cell = {cid: _cell_factors(host=host, cell_id=cid) for cid in cell_ids}
    source_factors_by_source = {"A": SourceHazardFactors("A", source_strength_factor=_fv(strength))}
    wind_by_cell = {cid: CellMeteorology(cid, wind_vector=WindVector(wind_u, 0.0), wind_speed_factor=_fv(1.0)) for cid in cell_ids}
    return dict(
        expected_grid_cell_ids=list(cell_ids), active_source_ids=["A"],
        cell_factors_by_cell=cell_factors_by_cell, source_factors_by_source=source_factors_by_source,
        geometry_by_cell=geometry_by_cell, wind_by_cell=wind_by_cell,
    )


def test_haz_id_01_same_inputs_same_signature():
    sig1 = compute_hazard_input_signature_hash(**_signature_kwargs())
    sig2 = compute_hazard_input_signature_hash(**_signature_kwargs())
    assert sig1 == sig2


def test_haz_id_02_different_cell_host_factor_different_signature():
    sig1 = compute_hazard_input_signature_hash(**_signature_kwargs(host=0.8))
    sig2 = compute_hazard_input_signature_hash(**_signature_kwargs(host=0.5))
    assert sig1 != sig2


def test_haz_id_03_different_source_strength_different_signature():
    sig1 = compute_hazard_input_signature_hash(**_signature_kwargs(strength=1.0))
    sig2 = compute_hazard_input_signature_hash(**_signature_kwargs(strength=0.5))
    assert sig1 != sig2


def test_haz_id_04_different_wind_vector_different_signature():
    sig1 = compute_hazard_input_signature_hash(**_signature_kwargs(wind_u=2.0))
    sig2 = compute_hazard_input_signature_hash(**_signature_kwargs(wind_u=5.0))
    assert sig1 != sig2


def test_haz_id_05_different_geometry_different_signature():
    sig1 = compute_hazard_input_signature_hash(**_signature_kwargs(distance_km=5.0))
    sig2 = compute_hazard_input_signature_hash(**_signature_kwargs(distance_km=8.0))
    assert sig1 != sig2


def test_haz_id_06_different_expected_grid_cell_set_different_signature():
    sig1 = compute_hazard_input_signature_hash(**_signature_kwargs(cell_ids=("CELL1",)))
    sig2 = compute_hazard_input_signature_hash(**_signature_kwargs(cell_ids=("CELL1", "CELL2")))
    assert sig1 != sig2


def _full_snapshot_kwargs(**overrides):
    kwargs = _signature_kwargs(**{k: v for k, v in overrides.items() if k in ("host", "strength", "wind_u", "distance_km", "cell_ids")})
    return dict(
        forecast_origin_id="O1", t0="2021-01-01", feature_snapshot_id="SNAPSHOT:abc",
        config=_config(), **kwargs,
    )


def test_haz_id_07_changed_signature_changes_snapshot_id():
    snap1 = build_hazard_snapshot(**_full_snapshot_kwargs(host=0.8))
    snap2 = build_hazard_snapshot(**_full_snapshot_kwargs(host=0.5))
    assert snap1.hazard_input_signature_hash != snap2.hazard_input_signature_hash
    assert snap1.hazard_snapshot_id != snap2.hazard_snapshot_id


def test_haz_id_08_generated_at_does_not_affect_either_identity_hash():
    snap1 = build_hazard_snapshot(**_full_snapshot_kwargs())
    time.sleep(0.01)
    snap2 = build_hazard_snapshot(**_full_snapshot_kwargs())
    assert snap1.generated_at != snap2.generated_at
    assert snap1.hazard_input_signature_hash == snap2.hazard_input_signature_hash
    assert snap1.hazard_snapshot_id == snap2.hazard_snapshot_id


def test_haz_id_09_dictionary_ordering_does_not_affect_identity():
    kwargs = _signature_kwargs(cell_ids=("CELL1", "CELL2"))
    sig_forward = compute_hazard_input_signature_hash(**kwargs)

    reordered_kwargs = dict(kwargs)
    reordered_kwargs["cell_factors_by_cell"] = dict(reversed(list(kwargs["cell_factors_by_cell"].items())))
    reordered_kwargs["geometry_by_cell"] = dict(reversed(list(kwargs["geometry_by_cell"].items())))
    reordered_kwargs["wind_by_cell"] = dict(reversed(list(kwargs["wind_by_cell"].items())))
    sig_reordered = compute_hazard_input_signature_hash(**reordered_kwargs)

    assert sig_forward == sig_reordered


def test_same_config_different_input_signature_still_changes_snapshot_id():
    # a same-config, different-wind-vector run must still change the
    # overall HazardSnapshot ID via hazard_input_signature_hash even
    # though hazard_config_hash itself is unaffected by wind values.
    snap1 = build_hazard_snapshot(**_full_snapshot_kwargs(wind_u=2.0))
    snap2 = build_hazard_snapshot(**_full_snapshot_kwargs(wind_u=9.0))
    assert snap1.hazard_config_hash == snap2.hazard_config_hash
    assert snap1.hazard_input_signature_hash != snap2.hazard_input_signature_hash
    assert snap1.hazard_snapshot_id != snap2.hazard_snapshot_id
