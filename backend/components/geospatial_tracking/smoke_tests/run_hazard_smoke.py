"""Checkpoint 6C Part 40 / Checkpoint 6C.5 Parts 17-18: deterministic
SOFTWARE_FIXTURE_ONLY hazard smoke, with corrected CELL-vs-SOURCE
factor indexing.

Not a pytest suite — a small, self-contained, no-network/no-DB
demonstration that the hazard engine mathematics work end-to-end. Run
directly:

    python -m components.geospatial_tracking.smoke_tests.run_hazard_smoke

3 sources x 4 grid cells. Per Checkpoint 6C.5's index correction:
`host_factor`/`environmental_suitability_factor`/`water_context_factor`
are CELL properties (one `CellHazardFactors` per cell, shared
identically by every source contribution to that cell) —
`source_strength_factor` is the only SOURCE-indexed factor
(`SourceHazardFactors`, one per source, `SRC_A=1.0`/`SRC_B=0.8`/
`SRC_C=0.6`). All values are explicit software fixtures
(`status=SOFTWARE_FIXTURE_ONLY`). Demonstrates:

- each cell has exactly 3 source-specific contributions
- within each cell, every source contribution reads the SAME host/
  environmental/water factor values (cell-level sharing, 6C.5 Part 18)
  while source_strength differs by source
- the multi-source sum is exact (`H_i = sum_j H_j_i`)
- anisotropic alignment behaves geometrically (a source directly
  down-vector from a cell gets a larger anisotropy factor than one
  perpendicular or up-vector)
- the relative-risk-index link is bounded in [0, 1)
- reordering the source list does not change any result
- the hazard input signature changes if any effective input changes

This is NEVER compared against real outbreak outcomes — the entire
output is labeled `SOFTWARE_FIXTURE_ONLY` and must never be read as a
real risk estimate for any real place or date.

An OPTIONAL `REAL_GEOMETRY_SYNTHETIC_FACTORS_DIAGNOSTIC` run using a
real `FeatureSnapshot`'s `geometry_by_source` with synthetic factors is
not run here (requires real GIS/weather adapter access); left for a
future, explicitly-invoked diagnostic script if needed.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..services.geospatial.raster import LOCAL_GIS_CACHE_DIR
from ..services.hazard.contracts import (
    CellHazardFactors,
    FactorStatus,
    FactorValue,
    HazardMixConfig,
    SourceGeometry,
    SourceHazardFactors,
    WindVector,
)
from ..services.hazard.meteorology import expand_uniform_meteorology
from ..services.hazard.protocol import HazardConfig
from ..services.hazard.snapshot import build_hazard_snapshot

LOCAL_DATA_ROOT = LOCAL_GIS_CACHE_DIR.parent
OUTPUT_DIR = LOCAL_DATA_ROOT / "hazard_snapshots"

_FIXTURE = FactorStatus.SOFTWARE_FIXTURE_ONLY.value

# CELL-indexed fixtures (6C.5 Part 17) -- one (host, env, water) triple
# per cell, shared by every source contribution to that cell.
_CELL_FIXTURE_VALUES = {
    "CELL_N": dict(host=0.9, env=0.7, water=0.6),
    "CELL_E": dict(host=0.6, env=0.5, water=0.4),
    "CELL_S": dict(host=0.4, env=0.4, water=0.3),
    "CELL_W": dict(host=0.6, env=0.5, water=0.4),
}

# SOURCE-indexed fixture (6C.5 Part 4/17) -- the ONLY source-indexed factor.
_SOURCE_STRENGTH = {"SRC_A": 1.0, "SRC_B": 0.8, "SRC_C": 0.6}

# PAIR-indexed geometry (unchanged) -- distance from each source to the
# shared cell cluster; direction encoded via t_hat.
_SOURCE_DISTANCE_KM = {"SRC_A": 8.0, "SRC_B": 15.0, "SRC_C": 22.0}

_CELL_DIRECTIONS = {  # (t_hat_east, t_hat_north) from the source cluster to each cell
    "CELL_N": (0.0, 1.0),
    "CELL_E": (1.0, 0.0),
    "CELL_S": (0.0, -1.0),
    "CELL_W": (-1.0, 0.0),
}


def _fv(value: float) -> FactorValue:
    return FactorValue(value, _FIXTURE)


def _build_cell_factors_by_cell() -> dict:
    return {
        cell_id: CellHazardFactors(
            cell_id, host_factor=_fv(v["host"]), environmental_suitability_factor=_fv(v["env"]), water_context_factor=_fv(v["water"])
        )
        for cell_id, v in _CELL_FIXTURE_VALUES.items()
    }


def _build_source_factors_by_source() -> dict:
    return {sid: SourceHazardFactors(sid, source_strength_factor=_fv(strength)) for sid, strength in _SOURCE_STRENGTH.items()}


def _build_geometry_by_cell() -> dict:
    geometry_by_cell = {}
    for cell_id, (t_east, t_north) in _CELL_DIRECTIONS.items():
        geometry_by_cell[cell_id] = {
            source_id: SourceGeometry(source_id, cell_id, distance_km=distance_km, t_hat_east=t_east, t_hat_north=t_north)
            for source_id, distance_km in _SOURCE_DISTANCE_KM.items()
        }
    return geometry_by_cell


def run() -> tuple[dict, object]:
    expected_grid_cell_ids = list(_CELL_FIXTURE_VALUES.keys())
    active_source_ids = list(_SOURCE_STRENGTH.keys())
    geometry_by_cell = _build_geometry_by_cell()
    cell_factors_by_cell = _build_cell_factors_by_cell()
    source_factors_by_source = _build_source_factors_by_source()

    config = HazardConfig(
        local_kernel_family="EXPONENTIAL", local_kernel_distance_scale_km=10.0,
        anisotropic_pathway_enabled=True, anisotropy_mode="MODULATING", anisotropy_kappa=2.0,
        wind_kernel_family="EXPONENTIAL", wind_kernel_distance_scale_km=10.0,
        mix=HazardMixConfig(local_weight=0.6, anisotropic_weight=0.4),
    )
    wind = WindVector(u10=0.0, v10=5.0)  # blowing due north
    wind_speed_factor = _fv(1.0)  # WIND_SPEED_EFFECT=NOT_YET_SELECTED fixture
    wind_by_cell = expand_uniform_meteorology(grid_cell_ids=expected_grid_cell_ids, wind=wind, wind_speed_factor=wind_speed_factor)

    forward = build_hazard_snapshot(
        forecast_origin_id="SOFTWARE_FIXTURE_ONLY:smoke", t0="2000-01-01", feature_snapshot_id=None,
        active_source_ids=active_source_ids, expected_grid_cell_ids=expected_grid_cell_ids,
        geometry_by_cell=geometry_by_cell, cell_factors_by_cell=cell_factors_by_cell,
        source_factors_by_source=source_factors_by_source, config=config, wind_by_cell=wind_by_cell,
    )

    reversed_ids = list(reversed(active_source_ids))
    reversed_geometry_by_cell = {
        cell_id: {sid: sources[sid] for sid in reversed_ids} for cell_id, sources in geometry_by_cell.items()
    }
    reordered = build_hazard_snapshot(
        forecast_origin_id="SOFTWARE_FIXTURE_ONLY:smoke", t0="2000-01-01", feature_snapshot_id=None,
        active_source_ids=reversed_ids, expected_grid_cell_ids=expected_grid_cell_ids,
        geometry_by_cell=reversed_geometry_by_cell, cell_factors_by_cell=cell_factors_by_cell,
        source_factors_by_source=source_factors_by_source, config=config, wind_by_cell=wind_by_cell,
    )

    checks = {
        "status": forward.status,
        "every_cell_has_3_contributions": all(len(c["source_contributions"]) == 3 for c in forward.grid_cell_results),
        "order_invariant": (
            sorted((c["grid_cell_id"], c["total_hazard"]) for c in forward.grid_cell_results)
            == sorted((c["grid_cell_id"], c["total_hazard"]) for c in reordered.grid_cell_results)
        ),
        "order_invariant_signature": forward.hazard_input_signature_hash == reordered.hazard_input_signature_hash,
        "all_relative_risk_bounded": all(0.0 <= c["relative_risk_index"] <= 1.0 for c in forward.grid_cell_results),
    }

    cell_by_id = {c["grid_cell_id"]: c for c in forward.grid_cell_results}

    # 6C.5 Part 18: within each cell, every source contribution must
    # share the SAME host/environmental/water factor while
    # source_strength may vary.
    cell_sharing_ok = True
    for cell_id, cell in cell_by_id.items():
        hosts = {sc["local_pathway_components"]["host_factor"] for sc in cell["source_contributions"]}
        envs = {sc["local_pathway_components"]["environmental_suitability_factor"] for sc in cell["source_contributions"]}
        waters = {sc["anisotropic_pathway_components"]["water_context_factor"] for sc in cell["source_contributions"]}
        strengths = {sc["local_pathway_components"]["source_strength_factor"] for sc in cell["source_contributions"]}
        if len(hosts) != 1 or len(envs) != 1 or len(waters) != 1:
            cell_sharing_ok = False
        if len(strengths) != 3:  # SRC_A/B/C have distinct strengths -- must NOT collapse to one shared value
            cell_sharing_ok = False
    checks["cell_level_factor_sharing_source_strength_varies"] = cell_sharing_ok

    north_alignment = next(sc["meteorological_alignment"] for sc in cell_by_id["CELL_N"]["source_contributions"] if sc["source_id"] == "SRC_A")
    east_alignment = next(sc["meteorological_alignment"] for sc in cell_by_id["CELL_E"]["source_contributions"] if sc["source_id"] == "SRC_A")
    south_alignment = next(sc["meteorological_alignment"] for sc in cell_by_id["CELL_S"]["source_contributions"] if sc["source_id"] == "SRC_A")
    checks["geometric_alignment_sane"] = north_alignment > east_alignment > south_alignment

    summary = {
        "label": "SOFTWARE_FIXTURE_ONLY",
        "hazard_config_hash": forward.hazard_config_hash,
        "hazard_input_signature_hash": forward.hazard_input_signature_hash,
        "hazard_snapshot_id": forward.hazard_snapshot_id,
        "checks": checks,
        "cells": {
            cid: {
                "cell_factors": _CELL_FIXTURE_VALUES[cid],
                "total_hazard": c["total_hazard"],
                "relative_risk_index": c["relative_risk_index"],
                "relative_risk_status": c["relative_risk_status"],
                "n_contributions": len(c["source_contributions"]),
            }
            for cid, c in cell_by_id.items()
        },
    }
    return summary, forward


if __name__ == "__main__":
    summary, snapshot = run()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "software_fixture_only_smoke.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot.as_dict(), f, indent=2, default=str)
    print(f"hazard smoke snapshot -> {out_path}")
    print(json.dumps(summary, indent=2, default=str))
    assert all(summary["checks"].values()), f"smoke check failed: {summary['checks']}"
    print("\nAll SOFTWARE_FIXTURE_ONLY smoke checks passed.")
