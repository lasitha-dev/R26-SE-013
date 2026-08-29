"""Checkpoint 6C Part 30: hazard-engine protocol metadata.

`HazardConfig.config_hash()` covers every scientific/mathematical
choice that could change the numeric hazard output — local kernel
family/scale, whether the anisotropic pathway is enabled, anisotropy
mode/strength, wind kernel family/scale, pathway mixing coefficients,
factor-contract version, relative-risk-link version — and NEVER
`generated_at`. Same config -> same hash; any changed scientific
parameter -> changed hash.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .contracts import (
    ALLOWED_HAZARD_PARAMETER_STATUSES,
    AnisotropyMode,
    HazardMixConfig,
    KernelFamily,
    WATER_PATHWAY_NOT_YET_SELECTED,
    WIND_SPEED_EFFECT_NOT_YET_SELECTED,
    reject_non_finite,
)

HAZARD_PROTOCOL_VERSION = "6C.1"
FACTOR_CONTRACT_VERSION = "6C.1"
RELATIVE_RISK_LINK_VERSION = "6C.1"  # R = 1 - exp(-H), no prior term

_KNOWN_KERNEL_FAMILIES = {f.value for f in KernelFamily}
_KNOWN_ANISOTROPY_MODES = {m.value for m in AnisotropyMode}


@dataclass(frozen=True)
class HazardConfig:
    local_kernel_family: str
    local_kernel_distance_scale_km: float

    anisotropic_pathway_enabled: bool
    anisotropy_mode: str
    anisotropy_kappa: float
    wind_kernel_family: str
    wind_kernel_distance_scale_km: float

    mix: HazardMixConfig

    parameter_status: str = "UNFROZEN_DEVELOPMENT_CANDIDATE"
    wind_speed_effect_status: str = WIND_SPEED_EFFECT_NOT_YET_SELECTED
    water_pathway_status: str = WATER_PATHWAY_NOT_YET_SELECTED
    hazard_protocol_version: str = HAZARD_PROTOCOL_VERSION
    factor_contract_version: str = FACTOR_CONTRACT_VERSION
    relative_risk_link_version: str = RELATIVE_RISK_LINK_VERSION

    def __post_init__(self) -> None:
        if self.local_kernel_family not in _KNOWN_KERNEL_FAMILIES:
            raise ValueError(f"unknown local_kernel_family {self.local_kernel_family!r}")
        reject_non_finite("local_kernel_distance_scale_km", self.local_kernel_distance_scale_km)
        if self.local_kernel_distance_scale_km <= 0:
            raise ValueError("local_kernel_distance_scale_km must be > 0")

        if self.wind_kernel_family not in _KNOWN_KERNEL_FAMILIES:
            raise ValueError(f"unknown wind_kernel_family {self.wind_kernel_family!r}")
        reject_non_finite("wind_kernel_distance_scale_km", self.wind_kernel_distance_scale_km)
        if self.wind_kernel_distance_scale_km <= 0:
            raise ValueError("wind_kernel_distance_scale_km must be > 0")

        if self.anisotropy_mode not in _KNOWN_ANISOTROPY_MODES:
            raise ValueError(f"unknown anisotropy_mode {self.anisotropy_mode!r}")
        reject_non_finite("anisotropy_kappa", self.anisotropy_kappa)
        if self.anisotropy_kappa < 0:
            raise ValueError("anisotropy_kappa (anisotropy strength) must be >= 0")

        if not isinstance(self.mix, HazardMixConfig):
            raise TypeError("mix must be a HazardMixConfig")

        if self.parameter_status not in ALLOWED_HAZARD_PARAMETER_STATUSES:
            raise ValueError(
                f"HazardConfig.parameter_status must be one of {sorted(ALLOWED_HAZARD_PARAMETER_STATUSES)} — "
                f"FROZEN_REFERENCE is not permitted in Checkpoint 6C, got {self.parameter_status!r}"
            )

    def config_dict(self) -> dict:
        return {
            "hazard_protocol_version": self.hazard_protocol_version,
            "local_kernel_family": self.local_kernel_family,
            "local_kernel_distance_scale_km": self.local_kernel_distance_scale_km,
            "anisotropic_pathway_enabled": self.anisotropic_pathway_enabled,
            "anisotropy_mode": self.anisotropy_mode,
            "anisotropy_kappa": self.anisotropy_kappa,
            "wind_kernel_family": self.wind_kernel_family,
            "wind_kernel_distance_scale_km": self.wind_kernel_distance_scale_km,
            "mix": self.mix.as_dict(),
            "parameter_status": self.parameter_status,
            "wind_speed_effect_status": self.wind_speed_effect_status,
            "water_pathway_status": self.water_pathway_status,
            "factor_contract_version": self.factor_contract_version,
            "relative_risk_link_version": self.relative_risk_link_version,
        }

    def config_hash(self) -> str:
        canonical = json.dumps(self.config_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
