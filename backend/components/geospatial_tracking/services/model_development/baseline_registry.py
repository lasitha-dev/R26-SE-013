"""Checkpoint 7A Parts 24-27: pre-registered baseline model families and
kernel candidates — a REGISTRY only. Nothing in this module fits a
coefficient, evaluates a score against real data, or compares model
performance (Part 24, 28) — that begins only in Checkpoint 7B.

**EQUAL_SOURCE_BASELINE (Part 25)**: B0/B1/B2 implicitly give every
eligible source equal structural contribution — labeled exactly
`EQUAL_SOURCE_BASELINE`, never `source_strength_factor = 1.0 REAL`.
The scientifically defined source-strength factor remains
`NOT_YET_SCIENTIFICALLY_DEFINED` (`services.factors.source_strength`),
unchanged by this registry's existence.

**Environment/water/wind status unchanged (Part 26)**:
`environmental_suitability_factor`/`water_context_factor` remain
`NOT_YET_SCIENTIFICALLY_DEFINED`; the wind-speed effect remains
`NOT_YET_SELECTED`. No baseline candidate here uses any of them.

**Kernel candidates (Part 27)**: reuses `services.hazard.contracts.KernelFamily`
(EXPONENTIAL/GAUSSIAN) unchanged — `distance_scale_km` remains
`UNFROZEN_DEVELOPMENT_PARAMETER` (`services.hazard.kernels`), never
selected here, never called "spread radius."
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from ..hazard.contracts import KernelFamily

EQUAL_SOURCE_BASELINE = "EQUAL_SOURCE_BASELINE"
RELATIVE_SPATIAL_SCORE = "RELATIVE_SPATIAL_SCORE"  # never "infection probability" / "final PISTES"


class BaselineFamily(str, Enum):
    B0_DISTANCE_ONLY = "B0_DISTANCE_ONLY"
    B1_HOST_DISTANCE_LOG1P = "B1_HOST_DISTANCE_LOG1P"
    B2_HOST_DISTANCE_ECDF = "B2_HOST_DISTANCE_ECDF"


@dataclass(frozen=True)
class BaselineCandidate:
    family: str
    description: str
    host_factor_candidate: str | None  # None | "LOG1P_ROBUST_REFERENCE_SCALE" | "EMPIRICAL_CDF_REFERENCE"
    source_weighting: str
    uses_environmental_suitability_factor: bool
    uses_water_context_factor: bool
    emits_infection_probability: bool
    output_label: str

    def as_dict(self) -> dict:
        return {
            "family": self.family, "description": self.description, "host_factor_candidate": self.host_factor_candidate,
            "source_weighting": self.source_weighting,
            "uses_environmental_suitability_factor": self.uses_environmental_suitability_factor,
            "uses_water_context_factor": self.uses_water_context_factor,
            "emits_infection_probability": self.emits_infection_probability, "output_label": self.output_label,
        }


BASELINE_CANDIDATE_REGISTRY_VERSION = "7A.1"

BASELINE_CANDIDATES: tuple = (
    BaselineCandidate(
        family=BaselineFamily.B0_DISTANCE_ONLY.value,
        description="score_i = sum_j K(distance_j_i) -- distance-kernel-only; no host/environment/water/source-strength factor.",
        host_factor_candidate=None, source_weighting=EQUAL_SOURCE_BASELINE,
        uses_environmental_suitability_factor=False, uses_water_context_factor=False,
        emits_infection_probability=False, output_label=RELATIVE_SPATIAL_SCORE,
    ),
    BaselineCandidate(
        family=BaselineFamily.B1_HOST_DISTANCE_LOG1P.value,
        description="score_i = Host_LOG1P_i * sum_j K(distance_j_i).",
        host_factor_candidate="LOG1P_ROBUST_REFERENCE_SCALE", source_weighting=EQUAL_SOURCE_BASELINE,
        uses_environmental_suitability_factor=False, uses_water_context_factor=False,
        emits_infection_probability=False, output_label=RELATIVE_SPATIAL_SCORE,
    ),
    BaselineCandidate(
        family=BaselineFamily.B2_HOST_DISTANCE_ECDF.value,
        description="score_i = Host_ECDF_i * sum_j K(distance_j_i).",
        host_factor_candidate="EMPIRICAL_CDF_REFERENCE", source_weighting=EQUAL_SOURCE_BASELINE,
        uses_environmental_suitability_factor=False, uses_water_context_factor=False,
        emits_infection_probability=False, output_label=RELATIVE_SPATIAL_SCORE,
    ),
)


def baseline_registry_dict() -> dict:
    return {"version": BASELINE_CANDIDATE_REGISTRY_VERSION, "candidates": [c.as_dict() for c in BASELINE_CANDIDATES]}


def baseline_registry_hash() -> str:
    canonical = json.dumps(baseline_registry_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


KERNEL_CANDIDATE_REGISTRY_VERSION = "7A.1"
KERNEL_CANDIDATE_FAMILIES: tuple = tuple(f.value for f in KernelFamily)
KERNEL_DISTANCE_SCALE_STATUS = "UNFROZEN_DEVELOPMENT_PARAMETER"


def kernel_registry_dict() -> dict:
    return {
        "version": KERNEL_CANDIDATE_REGISTRY_VERSION, "families": list(KERNEL_CANDIDATE_FAMILIES),
        "distance_scale_km_status": KERNEL_DISTANCE_SCALE_STATUS,
    }


def kernel_registry_hash() -> str:
    canonical = json.dumps(kernel_registry_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
