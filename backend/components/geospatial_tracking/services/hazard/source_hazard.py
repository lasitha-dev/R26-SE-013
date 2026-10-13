"""Checkpoint 6C Parts 5-6, 16-19 / Checkpoint 6C.5 Parts 1-5: source-
specific pre-link hazard, with CELL-vs-SOURCE-indexed factors.

For source `j` and cell `i`:

    L_j_i = Host_i * Environmental_i
            * SourceStrength_j * K_local(distance_j_i)

    W_j_i = WaterContext_i * Host_i * Environmental_i
            * SourceStrength_j * anisotropy_factor_j_i * wind_speed_factor
            * K_wind(distance_j_i)

    H_j_i = a * L_j_i + b * W_j_i        (a, b from HazardMixConfig)

`Host_i`/`Environmental_i`/`WaterContext_i` come from `CellHazardFactors`
(one object per cell, shared identically by every source contribution
to that cell — CELL-indexed, Checkpoint 6C.5 Part 1-3).
`SourceStrength_j` comes from `SourceHazardFactors` (SOURCE-indexed,
Part 4). `distance_j_i`/`t_hat_east_j_i`/`t_hat_north_j_i` come from
`SourceGeometry` (PAIR-indexed, unchanged). Every intermediate
component is preserved on the returned `SourceHazardContribution` —
never only one opaque number.

**Index consistency (Part 13)**: this function never trusts dictionary
placement alone — it verifies `geometry.grid_cell_id ==
cell_factors.grid_cell_id` and `geometry.source_id ==
source_factors.source_id` itself, raising immediately on any mismatch.

**Source-specific geometry is mandatory (Part 5, 6C)**: this module
always consumes a per-cell `SourceGeometry`, never a "nearest source"
shortcut.

**ST-DBSCAN never gates a hazard source (Part 6, 6C)**: nothing in this
module's signature accepts a cluster role, `is_noise`, `is_core`, or
any ST-DBSCAN concept at all.

**Missingness (Part 28-29, 6C)**: if any REQUIRED `FactorValue` for an
ENABLED pathway is not `.usable`, that pathway's status becomes
`SOURCE_HAZARD_INCOMPLETE` and its value is `None` — never silently 0
or 1. If the anisotropic pathway is disabled by
`HazardConfig.anisotropic_pathway_enabled=False`, it contributes
exactly `0.0` with `status=DISABLED_BY_CONFIG`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .anisotropy import compute_anisotropy_factor, compute_meteorological_alignment
from .contracts import (
    COMPLETE,
    DISABLED_BY_CONFIG,
    SOURCE_HAZARD_INCOMPLETE,
    CellHazardFactors,
    SourceGeometry,
    SourceHazardFactors,
    WindVector,
)
from .kernels import evaluate_kernel
from .protocol import HazardConfig


@dataclass(frozen=True)
class SourceHazardContribution:
    source_id: str
    grid_cell_id: str
    distance_km: float

    local_kernel: dict
    local_pathway_components: dict
    local_pathway_value: float | None

    meteorological_alignment: float | None
    anisotropy_factor: float | None
    anisotropic_pathway_components: dict
    anisotropic_pathway_value: float | None

    source_hazard: float | None
    status: str  # COMPLETE | SOURCE_HAZARD_INCOMPLETE
    missing_requirements: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "grid_cell_id": self.grid_cell_id,
            "distance_km": self.distance_km,
            "local_kernel": self.local_kernel,
            "local_pathway_components": self.local_pathway_components,
            "local_pathway_value": self.local_pathway_value,
            "meteorological_alignment": self.meteorological_alignment,
            "anisotropy_factor": self.anisotropy_factor,
            "anisotropic_pathway_components": self.anisotropic_pathway_components,
            "anisotropic_pathway_value": self.anisotropic_pathway_value,
            "source_hazard": self.source_hazard,
            "status": self.status,
            "missing_requirements": self.missing_requirements,
            "notes": self.notes,
        }


def _local_pathway(*, geometry: SourceGeometry, cell_factors: CellHazardFactors, source_factors: SourceHazardFactors, config: HazardConfig):
    missing = []
    for name, fv in (
        ("host_factor", cell_factors.host_factor),
        ("environmental_suitability_factor", cell_factors.environmental_suitability_factor),
        ("source_strength_factor", source_factors.source_strength_factor),
    ):
        if not fv.usable:
            missing.append(f"local:{name}({fv.status})")
    if missing:
        return {}, None, missing, {"family": config.local_kernel_family, "distance_scale_km": config.local_kernel_distance_scale_km}

    k = evaluate_kernel(geometry.distance_km, family=config.local_kernel_family, distance_scale_km=config.local_kernel_distance_scale_km)
    value = cell_factors.host_factor.value * cell_factors.environmental_suitability_factor.value * source_factors.source_strength_factor.value * k
    components = {
        "host_factor": cell_factors.host_factor.value,
        "environmental_suitability_factor": cell_factors.environmental_suitability_factor.value,
        "source_strength_factor": source_factors.source_strength_factor.value,
        "local_kernel_value": k,
    }
    kernel_info = {"family": config.local_kernel_family, "distance_scale_km": config.local_kernel_distance_scale_km, "value": k}
    return components, value, missing, kernel_info


def _anisotropic_pathway(
    *,
    geometry: SourceGeometry,
    cell_factors: CellHazardFactors,
    source_factors: SourceHazardFactors,
    wind: WindVector | None,
    wind_speed_factor,
    config: HazardConfig,
):
    if not config.anisotropic_pathway_enabled:
        return {}, 0.0, [], None, None, DISABLED_BY_CONFIG

    missing = []
    if wind is None:
        missing.append("anisotropic:wind_vector(MISSING)")
    if wind_speed_factor is None:
        missing.append("anisotropic:wind_speed_factor(MISSING)")
    factor_checks = [
        ("water_context_factor", cell_factors.water_context_factor),
        ("host_factor", cell_factors.host_factor),
        ("environmental_suitability_factor", cell_factors.environmental_suitability_factor),
        ("source_strength_factor", source_factors.source_strength_factor),
    ]
    if wind_speed_factor is not None:
        factor_checks.append(("wind_speed_factor", wind_speed_factor))
    for name, fv in factor_checks:
        if not fv.usable:
            missing.append(f"anisotropic:{name}({fv.status})")
    if missing:
        return {}, None, missing, None, None, SOURCE_HAZARD_INCOMPLETE

    alignment_result = compute_meteorological_alignment(t_hat_east=geometry.t_hat_east, t_hat_north=geometry.t_hat_north, wind=wind)
    aniso_result = compute_anisotropy_factor(alignment_result, kappa=config.anisotropy_kappa, mode=config.anisotropy_mode)
    k_wind = evaluate_kernel(geometry.distance_km, family=config.wind_kernel_family, distance_scale_km=config.wind_kernel_distance_scale_km)

    value = (
        cell_factors.water_context_factor.value
        * cell_factors.host_factor.value
        * cell_factors.environmental_suitability_factor.value
        * source_factors.source_strength_factor.value
        * aniso_result.anisotropy_factor
        * wind_speed_factor.value
        * k_wind
    )
    components = {
        "water_context_factor": cell_factors.water_context_factor.value,
        "host_factor": cell_factors.host_factor.value,
        "environmental_suitability_factor": cell_factors.environmental_suitability_factor.value,
        "source_strength_factor": source_factors.source_strength_factor.value,
        "anisotropy_factor": aniso_result.anisotropy_factor,
        "wind_speed_factor": wind_speed_factor.value,
        "wind_kernel_value": k_wind,
    }
    return components, value, missing, alignment_result, aniso_result, COMPLETE


def compute_source_hazard(
    *,
    geometry: SourceGeometry,
    cell_factors: CellHazardFactors,
    source_factors: SourceHazardFactors,
    config: HazardConfig,
    wind: WindVector | None = None,
    wind_speed_factor=None,
) -> SourceHazardContribution:
    """`wind`/`wind_speed_factor` are ignored entirely when
    `config.anisotropic_pathway_enabled` is `False` — passing `None` in
    that case is the normal, expected call shape.

    Checkpoint 6C.5 Part 13: raises `ValueError` immediately if
    `geometry.grid_cell_id != cell_factors.grid_cell_id` or
    `geometry.source_id != source_factors.source_id` — this function
    never trusts dictionary placement alone."""
    if geometry.grid_cell_id != cell_factors.grid_cell_id:
        raise ValueError(
            f"geometry.grid_cell_id ({geometry.grid_cell_id!r}) != cell_factors.grid_cell_id "
            f"({cell_factors.grid_cell_id!r}) — index mismatch, never trusted by placement alone"
        )
    if geometry.source_id != source_factors.source_id:
        raise ValueError(
            f"geometry.source_id ({geometry.source_id!r}) != source_factors.source_id "
            f"({source_factors.source_id!r}) — index mismatch, never trusted by placement alone"
        )

    local_components, local_value, local_missing, local_kernel_info = _local_pathway(
        geometry=geometry, cell_factors=cell_factors, source_factors=source_factors, config=config
    )
    (
        aniso_components,
        aniso_value,
        aniso_missing,
        alignment_result,
        aniso_result,
        aniso_status,
    ) = _anisotropic_pathway(
        geometry=geometry, cell_factors=cell_factors, source_factors=source_factors,
        wind=wind, wind_speed_factor=wind_speed_factor, config=config,
    )

    all_missing = local_missing + aniso_missing
    if all_missing:
        return SourceHazardContribution(
            source_id=geometry.source_id,
            grid_cell_id=geometry.grid_cell_id,
            distance_km=geometry.distance_km,
            local_kernel=local_kernel_info or {},
            local_pathway_components=local_components,
            local_pathway_value=local_value,
            meteorological_alignment=alignment_result.alignment if alignment_result else None,
            anisotropy_factor=aniso_result.anisotropy_factor if aniso_result else None,
            anisotropic_pathway_components=aniso_components,
            anisotropic_pathway_value=aniso_value,
            source_hazard=None,
            status=SOURCE_HAZARD_INCOMPLETE,
            missing_requirements=all_missing,
            notes=[],
        )

    h = config.mix.local_weight * local_value + config.mix.anisotropic_weight * (aniso_value or 0.0)
    if math.isnan(h) or math.isinf(h) or h < 0:
        raise ValueError(f"source_hazard evaluated to a non-finite/negative value ({h!r}) — never silently repaired")

    return SourceHazardContribution(
        source_id=geometry.source_id,
        grid_cell_id=geometry.grid_cell_id,
        distance_km=geometry.distance_km,
        local_kernel=local_kernel_info or {},
        local_pathway_components=local_components,
        local_pathway_value=local_value,
        meteorological_alignment=alignment_result.alignment if alignment_result else None,
        anisotropy_factor=aniso_result.anisotropy_factor if aniso_result else None,
        anisotropic_pathway_components=aniso_components,
        anisotropic_pathway_value=aniso_value,
        source_hazard=h,
        status=COMPLETE,
        missing_requirements=[],
        notes=[aniso_status] if aniso_status == DISABLED_BY_CONFIG else [],
    )
