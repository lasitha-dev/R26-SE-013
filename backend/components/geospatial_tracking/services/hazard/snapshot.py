"""Checkpoint 6C Parts 31-32 / Checkpoint 6C.5 Parts 8-15: `HazardSnapshot`
— the top-level hazard output contract, complete-grid orchestrator, and
input-signature identity.

**Complete grid contract (6C.5 Part 8-9)**: the orchestrator iterates
`expected_grid_cell_ids`, NOT merely `geometry_by_cell.keys()` — a cell
entirely absent from `geometry_by_cell`/`cell_factors_by_cell` still
produces exactly one `CellHazardResult`, marked
`CELL_HAZARD_INCOMPLETE` with an explicit missing-requirement, never
silently omitted. For every expected cell and every eligible active
source, the orchestrator verifies geometry, source factors, cell
factors, and (when the anisotropic pathway is enabled) cell
meteorology all exist — nothing is silently dropped, and nothing
crashes with an uncontrolled `KeyError` (Part 10-11).

**Extra-input safety (6C.5 Part 12)**: duplicate `active_source_ids` or
a source appearing in `geometry_by_cell`/`source_factors_by_source` but
NOT in `active_source_ids` both raise a clear `ValueError` at the top
of `build_hazard_snapshot` — never a silent extra contribution.

**Scientific identity (6C.5 Part 14-15)**: `hazard_input_signature_hash`
is a deterministic SHA-256 of every EFFECTIVE mathematical input
(expected grid-cell set, cell factors, source factors, geometry,
meteorology, active source IDs) — never `generated_at`, never
sensitive to dict insertion order. `hazard_snapshot_id` now covers
`feature_snapshot_id` + `hazard_config_hash` + `hazard_input_signature_hash`
+ sorted `active_source_ids` + the expected grid-cell set — changing
ANY effective input changes the ID; `generated_at` never does. An
`STClusterSnapshot` id may be recorded separately
(`st_cluster_snapshot_id`) but has **zero** influence on either hash.

No field on `HazardSnapshot`/`CellHazardResult`/`SourceHazardContribution`
is named `infection_probability`, `spread_direction`, `speed`, or
`confidence`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .accumulator import CellHazardResult, accumulate_cell_hazard
from .contracts import (
    CELL_HAZARD_INCOMPLETE,
    COMPLETE,
    HAZARD_SNAPSHOT_INCOMPLETE,
    SOURCE_HAZARD_INCOMPLETE,
    CellHazardFactors,
    SourceGeometry,
    SourceHazardFactors,
)
from .meteorology import CellMeteorology
from .protocol import HazardConfig
from .source_hazard import SourceHazardContribution, compute_source_hazard


def _factor_value_dict(fv) -> dict | None:
    if fv is None:
        return None
    return {"value": fv.value, "status": fv.status}


def _cell_factors_dict(cf: CellHazardFactors) -> dict:
    return {
        "host_factor": _factor_value_dict(cf.host_factor),
        "environmental_suitability_factor": _factor_value_dict(cf.environmental_suitability_factor),
        "water_context_factor": _factor_value_dict(cf.water_context_factor),
    }


def _source_factors_dict(sf: SourceHazardFactors) -> dict:
    return {"source_strength_factor": _factor_value_dict(sf.source_strength_factor)}


def _geometry_dict(g: SourceGeometry) -> dict:
    return {"distance_km": g.distance_km, "t_hat_east": g.t_hat_east, "t_hat_north": g.t_hat_north}


def _meteorology_dict(cm: CellMeteorology | None) -> dict | None:
    if cm is None:
        return None
    return {
        "wind_vector": {"u10": cm.wind_vector.u10, "v10": cm.wind_vector.v10},
        "wind_speed_factor": _factor_value_dict(cm.wind_speed_factor),
        "spatial_mode": cm.spatial_mode,
    }


def compute_hazard_input_signature_hash(
    *,
    expected_grid_cell_ids: list,
    active_source_ids: list,
    cell_factors_by_cell: dict,
    source_factors_by_source: dict,
    geometry_by_cell: dict,
    wind_by_cell: dict,
) -> str:
    """Checkpoint 6C.5 Part 14: covers every EFFECTIVE mathematical
    input. `json.dumps(..., sort_keys=True)` plus explicitly sorting
    every mapping's own keys before insertion makes this immune to
    dict insertion order (HAZ-ID-09). Never includes `generated_at`."""
    payload = {
        "expected_grid_cell_ids": sorted(expected_grid_cell_ids),
        "active_source_ids": sorted(active_source_ids),
        "cell_factors": {cid: _cell_factors_dict(cf) for cid, cf in sorted(cell_factors_by_cell.items())},
        "source_factors": {sid: _source_factors_dict(sf) for sid, sf in sorted(source_factors_by_source.items())},
        "geometry": {
            cid: {sid: _geometry_dict(g) for sid, g in sorted(sources.items())}
            for cid, sources in sorted(geometry_by_cell.items())
        },
        "meteorology": {cid: _meteorology_dict(cm) for cid, cm in sorted(wind_by_cell.items())},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_hazard_snapshot_id(
    *,
    feature_snapshot_id: str | None,
    active_source_ids: list,
    expected_grid_cell_ids: list,
    hazard_config_hash: str,
    hazard_input_signature_hash: str,
) -> str:
    payload = {
        "feature_snapshot_id": feature_snapshot_id,
        "active_source_ids": sorted(active_source_ids),
        "expected_grid_cell_ids": sorted(expected_grid_cell_ids),
        "hazard_config_hash": hazard_config_hash,
        "hazard_input_signature_hash": hazard_input_signature_hash,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"HAZARD:{digest[:24]}"


@dataclass
class HazardSnapshot:
    forecast_origin_id: str
    t0: str
    feature_snapshot_id: str | None
    active_source_ids: list = field(default_factory=list)
    expected_grid_cell_ids: list = field(default_factory=list)
    grid_cell_results: list = field(default_factory=list)  # CellHazardResult.as_dict()
    hazard_protocol_version: str = ""
    hazard_config_hash: str = ""
    hazard_input_signature_hash: str = ""
    hazard_snapshot_id: str = ""
    st_cluster_snapshot_id: str | None = None  # optional contextual metadata only
    status: str = ""
    generated_at: str = ""

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id,
            "t0": self.t0,
            "feature_snapshot_id": self.feature_snapshot_id,
            "active_source_ids": self.active_source_ids,
            "expected_grid_cell_ids": self.expected_grid_cell_ids,
            "grid_cell_results": self.grid_cell_results,
            "hazard_protocol_version": self.hazard_protocol_version,
            "hazard_config_hash": self.hazard_config_hash,
            "hazard_input_signature_hash": self.hazard_input_signature_hash,
            "hazard_snapshot_id": self.hazard_snapshot_id,
            "st_cluster_snapshot_id": self.st_cluster_snapshot_id,
            "status": self.status,
            "generated_at": self.generated_at,
        }


def _missing_cell_result(grid_cell_id: str) -> CellHazardResult:
    return CellHazardResult(
        grid_cell_id=grid_cell_id,
        source_contributions=[],
        total_hazard=None,
        relative_risk_index=None,
        relative_risk_status=None,
        status=CELL_HAZARD_INCOMPLETE,
        missing_requirements=[f"missing cell factor for cell {grid_cell_id}"],
    )


def build_hazard_snapshot(
    *,
    forecast_origin_id: str,
    t0: str,
    feature_snapshot_id: str | None,
    active_source_ids: list,
    expected_grid_cell_ids: list,
    geometry_by_cell: dict,  # grid_cell_id -> {source_id: SourceGeometry}
    cell_factors_by_cell: dict,  # grid_cell_id -> CellHazardFactors
    source_factors_by_source: dict,  # source_id -> SourceHazardFactors
    config: HazardConfig,
    wind_by_cell: dict | None = None,  # grid_cell_id -> CellMeteorology
    st_cluster_snapshot_id: str | None = None,
) -> HazardSnapshot:
    """Pure orchestration — no DB/API access. See module docstring for
    the complete-grid, extra-input-safety, and identity rules this
    function enforces."""
    wind_by_cell = wind_by_cell or {}

    # -- Checkpoint 6D Part 0A: duplicate expected grid cells rejected --
    if len(expected_grid_cell_ids) != len(set(expected_grid_cell_ids)):
        raise ValueError(f"expected_grid_cell_ids contains duplicates: {expected_grid_cell_ids!r}")
    expected_ids_set = set(expected_grid_cell_ids)

    if len(active_source_ids) != len(set(active_source_ids)):
        raise ValueError(f"active_source_ids contains duplicates: {active_source_ids!r}")
    active_ids_set = set(active_source_ids)

    # -- Checkpoint 6D Part 0B: no extra non-expected grid keys anywhere --
    for label, mapping in (("geometry_by_cell", geometry_by_cell), ("cell_factors_by_cell", cell_factors_by_cell), ("wind_by_cell", wind_by_cell)):
        extra = set(mapping.keys()) - expected_ids_set
        if extra:
            raise ValueError(
                f"{label} contains grid_cell_id(s) not in expected_grid_cell_ids: {sorted(extra)} — unused extra "
                "input must never silently exist or affect scientific identity"
            )

    for grid_cell_id, sources in geometry_by_cell.items():
        for source_id, geometry in sources.items():
            if source_id not in active_ids_set:
                raise ValueError(
                    f"geometry_by_cell[{grid_cell_id!r}] contains source {source_id!r}, which is not in "
                    "active_source_ids — a non-eligible source must never silently contribute"
                )
            if geometry.source_id != source_id:
                raise ValueError(
                    f"geometry_by_cell[{grid_cell_id!r}][{source_id!r}].source_id == {geometry.source_id!r} "
                    "— index mismatch, never trusted by dictionary placement alone"
                )
            if geometry.grid_cell_id != grid_cell_id:
                raise ValueError(
                    f"geometry_by_cell[{grid_cell_id!r}][{source_id!r}].grid_cell_id == {geometry.grid_cell_id!r} "
                    "— index mismatch, never trusted by dictionary placement alone"
                )

    # -- Checkpoint 6D Part 0C: source-factor identity verified at preflight --
    for source_id, sf in source_factors_by_source.items():
        if source_id not in active_ids_set:
            raise ValueError(
                f"source_factors_by_source contains source {source_id!r}, which is not in active_source_ids — "
                "a non-eligible source must never silently contribute"
            )
        if sf.source_id != source_id:
            raise ValueError(
                f"source_factors_by_source[{source_id!r}].source_id == {sf.source_id!r} — index mismatch, "
                "never trusted by dictionary placement alone (never relies only on the later "
                "compute_source_hazard check)"
            )

    for grid_cell_id, cf in cell_factors_by_cell.items():
        if cf.grid_cell_id != grid_cell_id:
            raise ValueError(
                f"cell_factors_by_cell[{grid_cell_id!r}].grid_cell_id == {cf.grid_cell_id!r} — index mismatch, "
                "never trusted by dictionary placement alone"
            )

    # -- Checkpoint 6D Part 0D: meteorology cell identity verified at preflight --
    for grid_cell_id, cm in wind_by_cell.items():
        if cm.grid_cell_id != grid_cell_id:
            raise ValueError(
                f"wind_by_cell[{grid_cell_id!r}].grid_cell_id == {cm.grid_cell_id!r} — index mismatch, "
                "never trusted by dictionary placement alone"
            )

    cell_results: list[CellHazardResult] = []
    for grid_cell_id in sorted(expected_grid_cell_ids):
        cell_factors = cell_factors_by_cell.get(grid_cell_id)
        if cell_factors is None:
            cell_results.append(_missing_cell_result(grid_cell_id))
            continue

        geometries = geometry_by_cell.get(grid_cell_id, {})
        cell_met = wind_by_cell.get(grid_cell_id)
        wind = cell_met.wind_vector if cell_met else None
        wind_speed_factor = cell_met.wind_speed_factor if cell_met else None

        contributions: dict[str, SourceHazardContribution] = {}
        for source_id in sorted(active_ids_set):
            geometry = geometries.get(source_id)
            if geometry is None:
                continue  # accumulate_cell_hazard reports "geometry missing for source X"

            source_factors = source_factors_by_source.get(source_id)
            if source_factors is None:
                contributions[source_id] = SourceHazardContribution(
                    source_id=source_id, grid_cell_id=grid_cell_id, distance_km=geometry.distance_km,
                    local_kernel={}, local_pathway_components={}, local_pathway_value=None,
                    meteorological_alignment=None, anisotropy_factor=None,
                    anisotropic_pathway_components={}, anisotropic_pathway_value=None,
                    source_hazard=None, status=SOURCE_HAZARD_INCOMPLETE,
                    missing_requirements=[f"missing source factor for {source_id}"], notes=[],
                )
                continue

            contributions[source_id] = compute_source_hazard(
                geometry=geometry, cell_factors=cell_factors, source_factors=source_factors,
                config=config, wind=wind, wind_speed_factor=wind_speed_factor,
            )

        cell_results.append(
            accumulate_cell_hazard(grid_cell_id=grid_cell_id, eligible_source_ids=active_source_ids, contributions=contributions)
        )

    overall_status = COMPLETE if all(c.status == COMPLETE for c in cell_results) else HAZARD_SNAPSHOT_INCOMPLETE
    config_hash = config.config_hash()
    input_signature_hash = compute_hazard_input_signature_hash(
        expected_grid_cell_ids=expected_grid_cell_ids, active_source_ids=active_source_ids,
        cell_factors_by_cell=cell_factors_by_cell, source_factors_by_source=source_factors_by_source,
        geometry_by_cell=geometry_by_cell, wind_by_cell=wind_by_cell,
    )
    snapshot_id = compute_hazard_snapshot_id(
        feature_snapshot_id=feature_snapshot_id, active_source_ids=active_source_ids,
        expected_grid_cell_ids=expected_grid_cell_ids, hazard_config_hash=config_hash,
        hazard_input_signature_hash=input_signature_hash,
    )

    return HazardSnapshot(
        forecast_origin_id=forecast_origin_id,
        t0=t0,
        feature_snapshot_id=feature_snapshot_id,
        active_source_ids=sorted(active_source_ids),
        expected_grid_cell_ids=sorted(expected_grid_cell_ids),
        grid_cell_results=[c.as_dict() for c in cell_results],
        hazard_protocol_version=config.hazard_protocol_version,
        hazard_config_hash=config_hash,
        hazard_input_signature_hash=input_signature_hash,
        hazard_snapshot_id=snapshot_id,
        st_cluster_snapshot_id=st_cluster_snapshot_id,
        status=overall_status,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
