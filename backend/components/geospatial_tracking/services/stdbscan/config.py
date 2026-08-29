"""Checkpoint 6B Part 8: the ST-DBSCAN configuration contract.

`STDBSCANConfig` is the ONLY place ST-DBSCAN-style clustering parameters
live. Every field is explicit (no implicit defaults for the parameters
that change clustering output), mirroring `source_selector.get_eligible_sources`'
and `services.features.feature_policy.FeaturePolicy`'s established
no-silent-default convention.

**`parameter_status` (Part 8): for Checkpoint 6B, no configuration may
ever be `FROZEN_REFERENCE`.** No held-out prediction performance exists
yet to justify freezing anything — `STDBSCANConfig.__post_init__`
enforces this structurally, not just by convention.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

CONFIG_VERSION = "6B.1"

SOFTWARE_FIXTURE_ONLY = "SOFTWARE_FIXTURE_ONLY"
UNFROZEN_DEVELOPMENT_CANDIDATE = "UNFROZEN_DEVELOPMENT_CANDIDATE"
FROZEN_REFERENCE = "FROZEN_REFERENCE"
_VALID_PARAMETER_STATUSES = {SOFTWARE_FIXTURE_ONLY, UNFROZEN_DEVELOPMENT_CANDIDATE, FROZEN_REFERENCE}


class GpsCorePolicy(str, Enum):
    """Part 10-11: how APPROXIMATE/COARSE/UNKNOWN-precision GPS records
    contribute to core density. `PRIMARY_CORE_SUPPORT` is the primary
    development mode (approximate records sharing a documented
    coordinate-collision group collapse to at most one core-density
    support each); `EXACT_ONLY_CORE_SUPPORT` is a stricter sensitivity
    mode where only EXACT-precision records may ever be core. Neither is
    chosen over the other using held-out prediction performance — both
    are reported side-by-side for development sensitivity (Part 19)."""

    PRIMARY_CORE_SUPPORT = "PRIMARY_CORE_SUPPORT"
    EXACT_ONLY_CORE_SUPPORT = "EXACT_ONLY_CORE_SUPPORT"


@dataclass(frozen=True)
class STDBSCANConfig:
    eps_space_km: float
    eps_time_days: float
    min_core_supports: int
    active_window_days: int
    gps_core_policy: str  # GpsCorePolicy value
    parameter_status: str  # SOFTWARE_FIXTURE_ONLY | UNFROZEN_DEVELOPMENT_CANDIDATE | FROZEN_REFERENCE
    config_version: str = CONFIG_VERSION

    def __post_init__(self) -> None:
        if self.eps_space_km <= 0:
            raise ValueError(f"eps_space_km must be > 0, got {self.eps_space_km}")
        if self.eps_time_days < 0:
            raise ValueError(f"eps_time_days must be >= 0, got {self.eps_time_days}")
        if self.min_core_supports < 1:
            raise ValueError(f"min_core_supports must be >= 1, got {self.min_core_supports}")
        if self.active_window_days < 0:
            raise ValueError(f"active_window_days must be >= 0, got {self.active_window_days}")
        if self.gps_core_policy not in {p.value for p in GpsCorePolicy}:
            raise ValueError(f"unknown gps_core_policy {self.gps_core_policy!r}")
        if self.parameter_status not in _VALID_PARAMETER_STATUSES:
            raise ValueError(f"unknown parameter_status {self.parameter_status!r}")
        if self.parameter_status == FROZEN_REFERENCE:
            # Checkpoint 6B Part 8: no configuration may be frozen from
            # held-out prediction performance in this checkpoint -- no
            # such performance exists yet (no risk model exists at all).
            raise ValueError(
                "FROZEN_REFERENCE is not permitted in Checkpoint 6B — no held-out prediction performance "
                "exists yet to justify freezing any ST-DBSCAN parameter"
            )

    def config_dict(self) -> dict:
        return {
            "config_version": self.config_version,
            "eps_space_km": self.eps_space_km,
            "eps_time_days": self.eps_time_days,
            "min_core_supports": self.min_core_supports,
            "active_window_days": self.active_window_days,
            "gps_core_policy": self.gps_core_policy,
            "parameter_status": self.parameter_status,
        }

    def config_hash(self) -> str:
        """Deterministic — identical config -> identical hash, mirroring
        `FeaturePolicy.protocol_hash()`'s convention. Never includes any
        run-time-varying field."""
        canonical = json.dumps(self.config_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
