"""Checkpoint 6D Parts 22-24: `FactorSnapshot` — the top-level
development-only transformation output, and its deterministic identity.

**Architectural firewall (Part 22, NO-REAL-HAZARD)**: this module
produces a `FactorSnapshot`. It does **NOT** produce a real
`HazardSnapshot`, and it never constructs `services.hazard` objects
with a `REAL`-status usable value — `services.hazard.contracts.HazardFactors`/
`CellHazardFactors`/`SourceHazardFactors`/`FactorValue` structurally
refuse anything but `SOFTWARE_FIXTURE_ONLY`, and this module never
attempts to bypass that. A future adapter may connect a frozen,
validated transformation to the hazard engine only after a separate
selection/freeze checkpoint explicitly authorizes it.

**Identity (Part 24)**: `factor_snapshot_id` deterministically covers
`feature_snapshot_id`, `factor_transform_config_hash`,
`reference_profile_hash`, every effective transformed component value/
status (cell factor candidates, environmental component vectors,
source factor statuses, meteorology-by-cell including spatial
provenance, water-context status), the expected grid-cell set, and
active-source identity — never `generated_at`. Same inputs -> same ID;
any changed raw feature value, reference profile, transform config, or
meteorology spatial provenance changes the ID.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .environmental_components import build_environmental_component_vector
from .host_transform import build_host_factor_candidates
from .meteorology_adapter import build_meteorology_by_cell
from .source_strength import build_source_strength_status
from .water_context import build_water_context_status

LABEL_DEVELOPMENT_DIAGNOSTIC = "DEVELOPMENT_FACTOR_TRANSFORMATION_DIAGNOSTIC"


def _canonical_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_factor_snapshot_id(
    *,
    feature_snapshot_id: str | None,
    transform_config_hash: str,
    reference_profile_hash: str,
    cell_factor_candidates: dict,
    environmental_component_vectors: dict,
    source_factor_status: dict,
    meteorology_by_cell: dict,
    water_context_status: dict,
    expected_grid_cell_ids: list,
    active_source_ids: list,
) -> str:
    payload = {
        "feature_snapshot_id": feature_snapshot_id,
        "transform_config_hash": transform_config_hash,
        "reference_profile_hash": reference_profile_hash,
        "cell_factor_candidates": {
            cid: {name: prov.as_dict() for name, prov in sorted(candidates.items())}
            for cid, candidates in sorted(cell_factor_candidates.items())
        },
        "environmental_component_vectors": {cid: vec.as_dict() for cid, vec in sorted(environmental_component_vectors.items())},
        "source_factor_status": {sid: prov.as_dict() for sid, prov in sorted(source_factor_status.items())},
        "meteorology_by_cell": {cid: obs.as_dict() for cid, obs in sorted(meteorology_by_cell.items())},
        "water_context_status": {cid: prov.as_dict() for cid, prov in sorted(water_context_status.items())},
        "expected_grid_cell_ids": sorted(expected_grid_cell_ids),
        "active_source_ids": sorted(active_source_ids),
    }
    digest = _canonical_hash(payload)
    return f"FACTOR:{digest[:24]}"


@dataclass
class FactorSnapshot:
    factor_snapshot_id: str
    feature_snapshot_id: str | None
    forecast_origin_id: str
    t0: str
    expected_grid_cell_ids: list = field(default_factory=list)

    cell_factor_candidates: dict = field(default_factory=dict)  # grid_cell_id -> {candidate_name: dict}
    environmental_component_vectors: dict = field(default_factory=dict)  # grid_cell_id -> dict
    source_factor_status: dict = field(default_factory=dict)  # source_id -> dict
    meteorology_by_cell: dict = field(default_factory=dict)  # grid_cell_id -> dict
    water_context_status: dict = field(default_factory=dict)  # grid_cell_id -> dict

    factor_transform_config_hash: str = ""
    reference_profile_hash: str = ""
    input_feature_signature: str = ""
    status: str = ""
    blockers: list = field(default_factory=list)
    label: str = LABEL_DEVELOPMENT_DIAGNOSTIC
    generated_at: str = ""

    def as_dict(self) -> dict:
        return {
            "factor_snapshot_id": self.factor_snapshot_id,
            "feature_snapshot_id": self.feature_snapshot_id,
            "forecast_origin_id": self.forecast_origin_id,
            "t0": self.t0,
            "expected_grid_cell_ids": self.expected_grid_cell_ids,
            "cell_factor_candidates": self.cell_factor_candidates,
            "environmental_component_vectors": self.environmental_component_vectors,
            "source_factor_status": self.source_factor_status,
            "meteorology_by_cell": self.meteorology_by_cell,
            "water_context_status": self.water_context_status,
            "factor_transform_config_hash": self.factor_transform_config_hash,
            "reference_profile_hash": self.reference_profile_hash,
            "input_feature_signature": self.input_feature_signature,
            "status": self.status,
            "blockers": self.blockers,
            "label": self.label,
            "generated_at": self.generated_at,
        }


def build_factor_snapshot(
    *,
    feature_snapshot: dict,
    forecast_origin_id: str,
    t0: str,
    expected_grid_cell_ids: list,
    active_source_ids: list,
    reference_profile,
    transform_config,
) -> FactorSnapshot:
    """Pure given `feature_snapshot` (a `FeatureSnapshot.as_dict()`-shaped
    dict) and the already-built `reference_profile`/`transform_config` —
    no DB/network access itself."""
    feature_snapshot_id = feature_snapshot.get("snapshot_id")
    blockers: list = []

    cells_by_id = {c["grid_cell_id"]: c for c in feature_snapshot.get("grid_cells", []) or []}

    cell_factor_candidates: dict = {}
    environmental_component_vectors: dict = {}
    water_context_status: dict = {}
    for cell_id in expected_grid_cell_ids:
        cell = cells_by_id.get(cell_id)
        if cell is None:
            blockers.append(f"grid cell {cell_id} not present in FeatureSnapshot -- no factor candidates could be computed")
            continue
        cell_factor_candidates[cell_id] = build_host_factor_candidates(
            cell=cell, feature_snapshot_id=feature_snapshot_id, reference_profile=reference_profile, transform_config=transform_config,
        )
        environmental_component_vectors[cell_id] = build_environmental_component_vector(cell=cell, snapshot=feature_snapshot, feature_snapshot_id=feature_snapshot_id)
        water_context_status[cell_id] = build_water_context_status(cell=cell, feature_snapshot_id=feature_snapshot_id)

    meteorology_by_cell = build_meteorology_by_cell(feature_snapshot, expected_grid_cell_ids=[c for c in expected_grid_cell_ids if c in cells_by_id])
    source_factor_status = {source_id: build_source_strength_status(source_id=source_id) for source_id in active_source_ids}

    transform_config_hash = transform_config.config_hash()
    reference_profile_hash = reference_profile.reference_profile_hash()

    input_feature_signature = _canonical_hash({
        "feature_snapshot_id": feature_snapshot_id,
        "cells": {
            cid: {"host_density": cells_by_id[cid].get("host_density"), "landcover": cells_by_id[cid].get("landcover"), "hydrology": cells_by_id[cid].get("hydrology")}
            for cid in expected_grid_cell_ids if cid in cells_by_id
        },
        "weather_results": (feature_snapshot.get("weather") or {}).get("results"),
    })

    factor_snapshot_id = compute_factor_snapshot_id(
        feature_snapshot_id=feature_snapshot_id, transform_config_hash=transform_config_hash, reference_profile_hash=reference_profile_hash,
        cell_factor_candidates=cell_factor_candidates, environmental_component_vectors=environmental_component_vectors,
        source_factor_status=source_factor_status, meteorology_by_cell=meteorology_by_cell, water_context_status=water_context_status,
        expected_grid_cell_ids=expected_grid_cell_ids, active_source_ids=active_source_ids,
    )

    status = "DIAGNOSTIC_COMPLETE" if not blockers else "DIAGNOSTIC_INCOMPLETE"

    return FactorSnapshot(
        factor_snapshot_id=factor_snapshot_id,
        feature_snapshot_id=feature_snapshot_id,
        forecast_origin_id=forecast_origin_id,
        t0=t0,
        expected_grid_cell_ids=sorted(expected_grid_cell_ids),
        cell_factor_candidates={cid: {name: prov.as_dict() for name, prov in candidates.items()} for cid, candidates in cell_factor_candidates.items()},
        environmental_component_vectors={cid: vec.as_dict() for cid, vec in environmental_component_vectors.items()},
        source_factor_status={sid: prov.as_dict() for sid, prov in source_factor_status.items()},
        meteorology_by_cell={cid: obs.as_dict() for cid, obs in meteorology_by_cell.items()},
        water_context_status={cid: prov.as_dict() for cid, prov in water_context_status.items()},
        factor_transform_config_hash=transform_config_hash,
        reference_profile_hash=reference_profile_hash,
        input_feature_signature=input_feature_signature,
        status=status,
        blockers=blockers,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
