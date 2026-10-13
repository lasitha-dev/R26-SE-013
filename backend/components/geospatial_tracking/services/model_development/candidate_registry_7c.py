"""Checkpoint 7C Parts 3, 10, 13-14: the frozen 7C candidate registry --
built BEFORE any 7C predictive scoring, exactly like 7B's 24-candidate
registry.

**Anchor (Part 3)**: `C0_FROZEN_B0_ISOTROPIC` reproduces the exact
Checkpoint 7B selected baseline (`CAND:B0_DISTANCE_ONLY:EXPONENTIAL:25KM:NONE:a48d9efcbb587cf1`,
`frozen_spec_hash=6bb8f67a7bc1188be324bf0a58e2399ed87df619b96c5a0db0ba5a3191794950`)
-- EXPONENTIAL kernel, 25km scale, no host factor. 7C never refits this
kernel family/scale (Part 3).

**Wind family (Part 9-10, 13)**: `CW_MODULATING(k)`/`CW_ANGULAR_NORMALIZED(k)`
-- the frozen B0 kernel sum modulated per-source by the EXISTING
`services.hazard.anisotropy` primitive. Checkpoint 6C left TWO
anisotropy semantics undecided (`MODULATING` changes total angular
mass with `kappa`; `ANGULAR_NORMALIZED` keeps direction-averaged mass
at 1 regardless of `kappa`) -- rather than arbitrarily picking one now,
BOTH pre-existing modes are registered as separate candidate families
(never a NEW third semantic), keeping the registry small and
hypothesis-driven (8 wind candidates, no environmental/water crossing
-- Part 11-12 exclude those factors entirely; see FACTOR_READINESS_AUDIT).

`ANISOTROPY_STRENGTH_CANDIDATES = (0.25, 0.50, 1.00, 2.00)` (Part 10) is
frozen here, before any 7C target score is read, and is never
added/removed after seeing development results.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from ..hazard.contracts import AnisotropyMode, KernelFamily
from .evaluation_protocol_7c import (
    ANISOTROPY_IMPLEMENTATION_VERSION_7C,
    LEGACY_EVALUATION_PROTOCOL_VERSION_7C,
    PARENT_7B_FROZEN_SPEC_HASH,
    evaluation_protocol_hash_7c,
    legacy_evaluation_protocol_hash_7c,
)

PARENT_7B_SELECTED_CANDIDATE_ID = "CAND:B0_DISTANCE_ONLY:EXPONENTIAL:25KM:NONE:a48d9efcbb587cf1"

FROZEN_KERNEL_FAMILY = KernelFamily.EXPONENTIAL.value
FROZEN_KERNEL_SCALE_KM = 25.0

ANISOTROPY_STRENGTH_CANDIDATES: tuple = (0.25, 0.50, 1.00, 2.00)
ANISOTROPY_MODE_CANDIDATES: tuple = (AnisotropyMode.MODULATING.value, AnisotropyMode.ANGULAR_NORMALIZED.value)
ANISOTROPY_CANDIDATE_REGISTRY_VERSION = "7C.1"

C0_FAMILY = "C0_FROZEN_B0_ISOTROPIC"
CW_FAMILY = "CW_WIND_ANISOTROPIC"

# Checkpoint 7C.1 Part 5: "7C.1" (the version the real 579-origin
# development run actually scored under) is kept ONLY as
# `LEGACY_CANDIDATE_REGISTRY_VERSION_7C` so `build_identity_only_result_remap_7c`
# can prove a bijective old-id -> new-id mapping; the live registry now
# builds under "7C.2" (identity-hardened -- Part 4).
LEGACY_CANDIDATE_REGISTRY_VERSION_7C = "7C.1"
CANDIDATE_REGISTRY_VERSION_7C = "7C.2"


@dataclass(frozen=True)
class Candidate7CSpec:
    candidate_id: str
    family: str
    kernel_family: str
    kernel_scale_km: float
    anisotropy_mode: str | None  # None for C0
    anisotropy_kappa: float | None  # None for C0
    output_label: str

    def as_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id, "family": self.family,
            "kernel_family": self.kernel_family, "kernel_scale_km": self.kernel_scale_km,
            "anisotropy_mode": self.anisotropy_mode, "anisotropy_kappa": self.anisotropy_kappa,
            "output_label": self.output_label,
        }


def _identity_payload(*, family: str, anisotropy_mode: str | None, anisotropy_kappa: float | None, registry_version: str, evaluation_protocol_hash: str) -> dict:
    return {
        "candidate_registry_version_7c": registry_version,
        "parent_7b_frozen_spec_hash": PARENT_7B_FROZEN_SPEC_HASH,
        "evaluation_protocol_hash_7c": evaluation_protocol_hash,
        "family": family,
        "kernel_family": FROZEN_KERNEL_FAMILY,
        "kernel_scale_km": FROZEN_KERNEL_SCALE_KM,
        "anisotropy_mode": anisotropy_mode,
        "anisotropy_kappa": anisotropy_kappa,
        "anisotropy_implementation_version": ANISOTROPY_IMPLEMENTATION_VERSION_7C,
    }


def _candidate_id_for(*, family: str, anisotropy_mode: str | None, anisotropy_kappa: float | None, registry_version: str, evaluation_protocol_hash: str) -> str:
    payload = _identity_payload(
        family=family, anisotropy_mode=anisotropy_mode, anisotropy_kappa=anisotropy_kappa,
        registry_version=registry_version, evaluation_protocol_hash=evaluation_protocol_hash,
    )
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    if family == C0_FAMILY:
        return f"C7C:{family}:{digest}"
    return f"C7C:{family}:{anisotropy_mode}:{anisotropy_kappa:g}:{digest}"


def _candidate_id(*, family: str, anisotropy_mode: str | None, anisotropy_kappa: float | None) -> str:
    return _candidate_id_for(
        family=family, anisotropy_mode=anisotropy_mode, anisotropy_kappa=anisotropy_kappa,
        registry_version=CANDIDATE_REGISTRY_VERSION_7C, evaluation_protocol_hash=evaluation_protocol_hash_7c(),
    )


def _legacy_candidate_id_7c(*, family: str, anisotropy_mode: str | None, anisotropy_kappa: float | None) -> str:
    """Checkpoint 7C.1 Part 5: the PRE-hardening (7C.1) identity scheme --
    preserved ONLY so `build_identity_only_result_remap_7c` can prove a
    deterministic one-to-one mapping from the already-completed real
    run's candidate ids to the current (7C.2) ones. Never used to build
    the live registry."""
    return _candidate_id_for(
        family=family, anisotropy_mode=anisotropy_mode, anisotropy_kappa=anisotropy_kappa,
        registry_version=LEGACY_CANDIDATE_REGISTRY_VERSION_7C, evaluation_protocol_hash=legacy_evaluation_protocol_hash_7c(),
    )


def _enumerate_candidate_tuples():
    yield (C0_FAMILY, None, None)
    for mode in ANISOTROPY_MODE_CANDIDATES:
        for kappa in ANISOTROPY_STRENGTH_CANDIDATES:
            yield (CW_FAMILY, mode, kappa)


def build_candidate_registry_7c() -> tuple[Candidate7CSpec, ...]:
    """9 candidates total: 1 frozen anchor + 8 wind candidates (2 modes x
    4 strengths). Takes no arguments -- reads only frozen module-level
    constants, so held-out/Sri Lanka results can never mutate it."""
    candidates: list[Candidate7CSpec] = []
    for family, mode, kappa in _enumerate_candidate_tuples():
        candidates.append(Candidate7CSpec(
            candidate_id=_candidate_id(family=family, anisotropy_mode=mode, anisotropy_kappa=kappa),
            family=family, kernel_family=FROZEN_KERNEL_FAMILY, kernel_scale_km=FROZEN_KERNEL_SCALE_KM,
            anisotropy_mode=mode, anisotropy_kappa=kappa, output_label="RELATIVE_SPATIAL_SCORE",
        ))
    return tuple(sorted(candidates, key=lambda c: c.candidate_id))


def build_identity_only_result_remap_7c() -> dict:
    """Checkpoint 7C.1 Part 5: `IDENTITY_ONLY_7C_RESULT_REMAP` -- a
    deterministic, one-to-one mapping from every legacy (7C.1, the
    version the real 579-origin development run actually scored under)
    `candidate_id` to its current (7C.2, identity-hardened) `candidate_id`,
    over the SAME 9 underlying (family, anisotropy_mode, anisotropy_kappa)
    tuples. Proves the identity-hardening change never touched grid/
    source/kernel/anisotropy/weather-fetch computation -- only how the
    candidate is NAMED -- so the already-computed real numerical results
    can be relabeled instead of re-running the ~18-minute 579-origin
    scoring pass."""
    mapping: dict[str, str] = {}
    for family, mode, kappa in _enumerate_candidate_tuples():
        old_id = _legacy_candidate_id_7c(family=family, anisotropy_mode=mode, anisotropy_kappa=kappa)
        new_id = _candidate_id(family=family, anisotropy_mode=mode, anisotropy_kappa=kappa)
        mapping[old_id] = new_id
    return mapping


def candidate_registry_dict_7c() -> dict:
    return {
        "version": CANDIDATE_REGISTRY_VERSION_7C,
        "anisotropy_strength_candidates": list(ANISOTROPY_STRENGTH_CANDIDATES),
        "anisotropy_mode_candidates": list(ANISOTROPY_MODE_CANDIDATES),
        "anisotropy_candidate_registry_version": ANISOTROPY_CANDIDATE_REGISTRY_VERSION,
        "parent_7b_frozen_spec_hash": PARENT_7B_FROZEN_SPEC_HASH,
        "candidates": [c.as_dict() for c in build_candidate_registry_7c()],
    }


def candidate_registry_hash_7c() -> str:
    canonical = json.dumps(candidate_registry_dict_7c(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
