"""Checkpoint 6D Part 11: `FactorTransformConfig` — the development-only
transformation parameter contract.

Every scaling/clipping parameter here is `UNFROZEN_DEVELOPMENT_CANDIDATE`
— never `FROZEN_REFERENCE`. `config_hash()` never includes `generated_at`.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from .contracts import (
    ALLOWED_TRANSFORM_PARAMETER_STATUSES,
    UNFROZEN_DEVELOPMENT_CANDIDATE,
    EcdfTieConvention,
    HostTransformFamily,
    ReferenceCompatibilityMode,
)

TRANSFORM_CONFIG_VERSION = "6D.2"

_KNOWN_HOST_FAMILIES = {f.value for f in HostTransformFamily}
_KNOWN_ECDF_TIE_CONVENTIONS = {c.value for c in EcdfTieConvention}
_KNOWN_COMPATIBILITY_MODES = {m.value for m in ReferenceCompatibilityMode}


@dataclass(frozen=True)
class FactorTransformConfig:
    log1p_reference_lower_quantile: float = 0.05
    log1p_reference_upper_quantile: float = 0.95
    host_transform_candidates: tuple = (
        HostTransformFamily.LOG1P_ROBUST_REFERENCE_SCALE.value,
        HostTransformFamily.EMPIRICAL_CDF_REFERENCE.value,
    )
    # Checkpoint 6D.5 Part 14: the ECDF tie convention is a scientific
    # identity element, not an implementation detail -- it lives in this
    # config and therefore in transform_config_hash.
    ecdf_tie_convention: str = EcdfTieConvention.LOWER_RANK.value
    # Checkpoint 6D.5 Part 7: the primary compatibility-enforcement mode.
    reference_compatibility_mode: str = ReferenceCompatibilityMode.STRICT_COMPATIBLE.value
    parameter_status: str = UNFROZEN_DEVELOPMENT_CANDIDATE
    transform_config_version: str = TRANSFORM_CONFIG_VERSION

    def __post_init__(self) -> None:
        for name, q in (("log1p_reference_lower_quantile", self.log1p_reference_lower_quantile), ("log1p_reference_upper_quantile", self.log1p_reference_upper_quantile)):
            if not (isinstance(q, (int, float)) and math.isfinite(q)):
                raise ValueError(f"{name} must be finite, got {q!r}")
            if not (0.0 <= q <= 1.0):
                raise ValueError(f"{name} must be within [0, 1], got {q!r}")
        if self.log1p_reference_lower_quantile >= self.log1p_reference_upper_quantile:
            raise ValueError(
                f"log1p_reference_lower_quantile ({self.log1p_reference_lower_quantile}) must be < "
                f"log1p_reference_upper_quantile ({self.log1p_reference_upper_quantile})"
            )
        unknown = set(self.host_transform_candidates) - _KNOWN_HOST_FAMILIES
        if unknown:
            raise ValueError(f"unknown host_transform_candidates {sorted(unknown)}")
        if self.ecdf_tie_convention not in _KNOWN_ECDF_TIE_CONVENTIONS:
            raise ValueError(f"unknown ecdf_tie_convention {self.ecdf_tie_convention!r}")
        if self.reference_compatibility_mode not in _KNOWN_COMPATIBILITY_MODES:
            raise ValueError(f"unknown reference_compatibility_mode {self.reference_compatibility_mode!r}")
        if self.parameter_status not in ALLOWED_TRANSFORM_PARAMETER_STATUSES:
            raise ValueError(
                f"FactorTransformConfig.parameter_status must be one of {sorted(ALLOWED_TRANSFORM_PARAMETER_STATUSES)} "
                f"— FROZEN_REFERENCE is not permitted in Checkpoint 6D, got {self.parameter_status!r}"
            )

    def config_dict(self) -> dict:
        return {
            "transform_config_version": self.transform_config_version,
            "log1p_reference_lower_quantile": self.log1p_reference_lower_quantile,
            "log1p_reference_upper_quantile": self.log1p_reference_upper_quantile,
            "host_transform_candidates": list(self.host_transform_candidates),
            "ecdf_tie_convention": self.ecdf_tie_convention,
            "reference_compatibility_mode": self.reference_compatibility_mode,
            "parameter_status": self.parameter_status,
        }

    def config_hash(self) -> str:
        canonical = json.dumps(self.config_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
