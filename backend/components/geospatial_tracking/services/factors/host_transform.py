"""Checkpoint 6D Parts 9-12 / Checkpoint 6D.5 Parts 5, 11-14: host-density
raw combination and candidate transforms — corrected identity and
safety.

`host_density_total = cattle_density + buffalo_density` ONLY when BOTH
species values are `REAL`, both carry the SAME canonical unit
(`animals_per_km2`), and both are finite/non-negative — never
substituted with zero when unusable, never summed across incompatible
units. A real raster value of `0` is preserved as a genuine
observation, distinguishable from `MISSING`.

**Identity (6D.5 Part 5)**: `host_density_total_observation_id` is
derived from the underlying `cattle`/`buffalo` reference-observation
identities themselves (`SHA256(cattle_id + buffalo_id + canonical
units)`) — never independently re-derived from dataset versions and
rounded query coordinates. Two grid cells whose cattle AND buffalo
values both resolve to the same underlying raster observations produce
the SAME host-total identity, so repeated sampling of one real
observation never pseudo-replicates the reference distribution.

Two explicit candidate transforms (Part 11) — NEITHER scientifically
selected — see `contracts.EcdfTieConvention` for the documented,
identity-participating ECDF tie convention, and Part 13 for the
explicit `DEGENERATE_REFERENCE_DISTRIBUTION` status a degenerate
log1p reference span now returns instead of silently outputting `0`.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
from dataclasses import dataclass

from ...services.geospatial.host_density.fao_glw import UNITS as CANONICAL_HOST_DENSITY_UNITS
from .contracts import (
    BLOCKED,
    DEGENERATE_REFERENCE_DISTRIBUTION,
    MISSING,
    RAW_REAL_COMPONENT,
    REAL_TRANSFORMED_CANDIDATE,
    UNIT_MISMATCH,
    ClippingAudit,
    EcdfTieConvention,
    TransformedFactorProvenance,
)
from .reference_observations import resolve_static_observation_identity
from .transform_config import FactorTransformConfig, HostTransformFamily

_SPECIES = ("cattle", "buffalo")


def _observation_id(identity: dict) -> str:
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def _validate_real_host_value(value) -> str | None:
    """Returns an error string if the value must be rejected as unusable
    (never summed/transformed), else `None`. NaN/infinity/negative
    values are rejected -- current REAL host density should never
    produce them, but this is never trusted implicitly (Part 12)."""
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"non-numeric REAL value {value!r}"
    if math.isnan(value) or math.isinf(value):
        return "NaN/infinite REAL value rejected"
    if value < 0:
        return "negative REAL host-density value rejected"
    return None


@dataclass(frozen=True)
class HostDensityRaw:
    cattle_value: float | None
    cattle_status: str
    cattle_observation_id: str | None
    cattle_identity_source: str | None  # RASTER_EFFECTIVE_SAMPLE_IDENTITY | QUERY_CENTROID_FALLBACK | None
    buffalo_value: float | None
    buffalo_status: str
    buffalo_observation_id: str | None
    buffalo_identity_source: str | None
    host_density_total: float | None
    host_density_total_status: str  # RAW_REAL_COMPONENT | MISSING | BLOCKED | UNIT_MISMATCH
    host_density_total_observation_id: str | None
    units: str | None
    dataset_versions: tuple

    def as_dict(self) -> dict:
        return {
            "cattle_value": self.cattle_value, "cattle_status": self.cattle_status, "cattle_observation_id": self.cattle_observation_id,
            "cattle_identity_source": self.cattle_identity_source,
            "buffalo_value": self.buffalo_value, "buffalo_status": self.buffalo_status, "buffalo_observation_id": self.buffalo_observation_id,
            "buffalo_identity_source": self.buffalo_identity_source,
            "host_density_total": self.host_density_total, "host_density_total_status": self.host_density_total_status,
            "host_density_total_observation_id": self.host_density_total_observation_id,
            "units": self.units, "dataset_versions": list(self.dataset_versions),
        }


def compute_host_density_total(cell: dict) -> HostDensityRaw:
    """`cell`: one `GridCellFeatures.as_dict()`-shaped dict. Never
    substitutes zero for a MISSING/BLOCKED/invalid species value; never
    sums mismatched units."""
    hd = cell.get("host_density") or {}
    cattle = hd.get("cattle") or {}
    buffalo = hd.get("buffalo") or {}
    cattle_status = cattle.get("status", MISSING)
    buffalo_status = buffalo.get("status", MISSING)

    cattle_identity_dict, cattle_identity_source = resolve_static_observation_identity(cattle, cell=cell) if cattle_status == "REAL" else (None, None)
    buffalo_identity_dict, buffalo_identity_source = resolve_static_observation_identity(buffalo, cell=cell) if buffalo_status == "REAL" else (None, None)
    cattle_identity = _observation_id(cattle_identity_dict) if cattle_identity_dict is not None else None
    buffalo_identity = _observation_id(buffalo_identity_dict) if buffalo_identity_dict is not None else None

    total: float | None = None
    total_status: str
    total_observation_id: str | None = None

    cattle_error = _validate_real_host_value(cattle.get("value")) if cattle_status == "REAL" else None
    buffalo_error = _validate_real_host_value(buffalo.get("value")) if buffalo_status == "REAL" else None

    if cattle_status == "REAL" and cattle_error:
        total_status = BLOCKED
    elif buffalo_status == "REAL" and buffalo_error:
        total_status = BLOCKED
    elif cattle_status == "REAL" and buffalo_status == "REAL":
        cattle_units = cattle.get("units")
        buffalo_units = buffalo.get("units")
        if cattle_units != CANONICAL_HOST_DENSITY_UNITS or buffalo_units != CANONICAL_HOST_DENSITY_UNITS or cattle_units != buffalo_units:
            total_status = UNIT_MISMATCH
        else:
            total = cattle["value"] + buffalo["value"]
            total_status = RAW_REAL_COMPONENT
            total_observation_id = _observation_id({
                "cattle_observation_id": cattle_identity, "buffalo_observation_id": buffalo_identity,
                "canonical_units": CANONICAL_HOST_DENSITY_UNITS,
            })
    elif cattle_status == "BLOCKED" or buffalo_status == "BLOCKED":
        total_status = BLOCKED
    else:
        total_status = MISSING

    return HostDensityRaw(
        cattle_value=cattle.get("value"), cattle_status=cattle_status, cattle_observation_id=cattle_identity,
        cattle_identity_source=cattle_identity_source,
        buffalo_value=buffalo.get("value"), buffalo_status=buffalo_status, buffalo_observation_id=buffalo_identity,
        buffalo_identity_source=buffalo_identity_source,
        host_density_total=total, host_density_total_status=total_status, host_density_total_observation_id=total_observation_id,
        units=cattle.get("units") or buffalo.get("units"),
        dataset_versions=(cattle.get("dataset_version"), buffalo.get("dataset_version")),
    )


def transform_log1p_robust_reference_scale(
    *, host_density_total: float, reference_log1p_lower: float, reference_log1p_upper: float
) -> tuple[float | None, ClippingAudit | None, str]:
    """Pure. Returns `(value, clipping_audit, candidate_status)`.
    `reference_log1p_lower`/`_upper` MUST come from a
    `FactorReferenceProfile` built from FIT_DEVELOPMENT-only material —
    never this AOI's own min/max. If the reference span is degenerate
    (`upper <= lower`), returns `(None, None, DEGENERATE_REFERENCE_DISTRIBUTION)`
    — never a silently chosen 0/0.5 (6D.5 Part 13)."""
    if reference_log1p_upper <= reference_log1p_lower:
        return None, None, DEGENERATE_REFERENCE_DISTRIBUTION
    x = math.log1p(host_density_total)
    span = reference_log1p_upper - reference_log1p_lower
    raw_z = (x - reference_log1p_lower) / span
    clipped_low = raw_z < 0.0
    clipped_high = raw_z > 1.0
    z = min(1.0, max(0.0, raw_z))
    audit = ClippingAudit(was_clipped_low=clipped_low, was_clipped_high=clipped_high, reference_lower=reference_log1p_lower, reference_upper=reference_log1p_upper)
    return z, audit, REAL_TRANSFORMED_CANDIDATE


def transform_empirical_cdf_reference(
    *, host_density_total: float, sorted_reference_values: tuple, tie_convention: str = EcdfTieConvention.LOWER_RANK.value
) -> float | None:
    """Pure, deterministic percentile rank of `host_density_total`
    within the FIT_DEVELOPMENT-only sorted reference sample, using the
    EXPLICIT `tie_convention` (Part 14 — never left implicit, never
    chosen using held-out performance). `0..1` is a relative/reference
    scale, NOT a probability."""
    if not sorted_reference_values:
        return None
    if tie_convention == EcdfTieConvention.LOWER_RANK.value:
        idx = bisect.bisect_left(sorted_reference_values, host_density_total)
        return idx / len(sorted_reference_values)
    if tie_convention == EcdfTieConvention.MID_RANK.value:
        lo = bisect.bisect_left(sorted_reference_values, host_density_total)
        hi = bisect.bisect_right(sorted_reference_values, host_density_total)
        return ((lo + hi) / 2.0) / len(sorted_reference_values)
    raise ValueError(f"unknown ecdf_tie_convention {tie_convention!r}")


def build_host_factor_candidates(
    *,
    cell: dict,
    feature_snapshot_id: str,
    reference_profile,
    transform_config: FactorTransformConfig,
) -> dict:
    """Returns `{candidate_name: TransformedFactorProvenance}` — raw
    cattle/buffalo/host_density_total preservation plus both candidate
    transforms."""
    raw = compute_host_density_total(cell)
    reference_profile_hash = reference_profile.reference_profile_hash()
    transform_config_hash = transform_config.config_hash()

    out: dict[str, TransformedFactorProvenance] = {}
    out["cattle_density"] = TransformedFactorProvenance(
        factor_or_component_name="cattle_density", raw_feature_names=("host_density_cattle_grid_cell",),
        raw_values=(raw.cattle_value,), raw_units=(raw.units,), raw_feature_statuses=(raw.cattle_status,),
        source_dataset_versions=(raw.dataset_versions[0],), feature_snapshot_id=feature_snapshot_id,
        transform_id=None, transform_config_hash=None, reference_profile_hash=None,
        transformed_value=raw.cattle_value if raw.cattle_status == "REAL" else None,
        candidate_status=RAW_REAL_COMPONENT if raw.cattle_status == "REAL" else raw.cattle_status,
        clipping=None, notes="GLW4 host-density PROXY, not exact farm inventory/animal population",
    )
    out["buffalo_density"] = TransformedFactorProvenance(
        factor_or_component_name="buffalo_density", raw_feature_names=("host_density_buffalo_grid_cell",),
        raw_values=(raw.buffalo_value,), raw_units=(raw.units,), raw_feature_statuses=(raw.buffalo_status,),
        source_dataset_versions=(raw.dataset_versions[1],), feature_snapshot_id=feature_snapshot_id,
        transform_id=None, transform_config_hash=None, reference_profile_hash=None,
        transformed_value=raw.buffalo_value if raw.buffalo_status == "REAL" else None,
        candidate_status=RAW_REAL_COMPONENT if raw.buffalo_status == "REAL" else raw.buffalo_status,
        clipping=None, notes="GLW4 host-density PROXY, not exact farm inventory/animal population",
    )
    out["host_density_total"] = TransformedFactorProvenance(
        factor_or_component_name="host_density_total", raw_feature_names=("host_density_cattle_grid_cell", "host_density_buffalo_grid_cell"),
        raw_values=(raw.cattle_value, raw.buffalo_value), raw_units=(raw.units, raw.units),
        raw_feature_statuses=(raw.cattle_status, raw.buffalo_status), source_dataset_versions=raw.dataset_versions,
        feature_snapshot_id=feature_snapshot_id, transform_id=None, transform_config_hash=None, reference_profile_hash=None,
        transformed_value=raw.host_density_total, candidate_status=raw.host_density_total_status, clipping=None,
        notes="cattle_density + buffalo_density, only when both are REAL with matching canonical units; a value "
              "of 0 is a real observation, not proof of zero susceptible livestock",
    )

    if raw.host_density_total_status != RAW_REAL_COMPONENT:
        for family in HostTransformFamily:
            out[family.value] = TransformedFactorProvenance(
                factor_or_component_name=family.value, raw_feature_names=("host_density_total",), raw_values=(raw.host_density_total,),
                raw_units=(raw.units,), raw_feature_statuses=(raw.host_density_total_status,), source_dataset_versions=raw.dataset_versions,
                feature_snapshot_id=feature_snapshot_id, transform_id=family.value, transform_config_hash=transform_config_hash,
                reference_profile_hash=reference_profile_hash, transformed_value=None, candidate_status=raw.host_density_total_status,
                clipping=None, notes="host_density_total unavailable — never substituted with 0/1",
            )
        return out

    if HostTransformFamily.LOG1P_ROBUST_REFERENCE_SCALE.value in transform_config.host_transform_candidates:
        z, clip_audit, status = transform_log1p_robust_reference_scale(
            host_density_total=raw.host_density_total,
            reference_log1p_lower=reference_profile.host_density_total_log1p_quantiles["lower"],
            reference_log1p_upper=reference_profile.host_density_total_log1p_quantiles["upper"],
        )
        out[HostTransformFamily.LOG1P_ROBUST_REFERENCE_SCALE.value] = TransformedFactorProvenance(
            factor_or_component_name=HostTransformFamily.LOG1P_ROBUST_REFERENCE_SCALE.value, raw_feature_names=("host_density_total",),
            raw_values=(raw.host_density_total,), raw_units=(raw.units,), raw_feature_statuses=(raw.host_density_total_status,),
            source_dataset_versions=raw.dataset_versions, feature_snapshot_id=feature_snapshot_id,
            transform_id=HostTransformFamily.LOG1P_ROBUST_REFERENCE_SCALE.value, transform_config_hash=transform_config_hash,
            reference_profile_hash=reference_profile_hash, transformed_value=z, candidate_status=status,
            clipping=clip_audit, notes=(
                "candidate only -- not scientifically selected; reference bounds are FIT_DEVELOPMENT quantiles, "
                "never this AOI's own min/max, never called maximum biological density"
            ) if status == REAL_TRANSFORMED_CANDIDATE else "reference log1p span is degenerate (upper <= lower) -- never silently defaulted to 0/0.5",
        )

    if HostTransformFamily.EMPIRICAL_CDF_REFERENCE.value in transform_config.host_transform_candidates:
        pct = transform_empirical_cdf_reference(
            host_density_total=raw.host_density_total, sorted_reference_values=reference_profile.host_density_total_reference_values,
            tie_convention=transform_config.ecdf_tie_convention,
        )
        status = REAL_TRANSFORMED_CANDIDATE if pct is not None else DEGENERATE_REFERENCE_DISTRIBUTION
        out[HostTransformFamily.EMPIRICAL_CDF_REFERENCE.value] = TransformedFactorProvenance(
            factor_or_component_name=HostTransformFamily.EMPIRICAL_CDF_REFERENCE.value, raw_feature_names=("host_density_total",),
            raw_values=(raw.host_density_total,), raw_units=(raw.units,), raw_feature_statuses=(raw.host_density_total_status,),
            source_dataset_versions=raw.dataset_versions, feature_snapshot_id=feature_snapshot_id,
            transform_id=HostTransformFamily.EMPIRICAL_CDF_REFERENCE.value, transform_config_hash=transform_config_hash,
            reference_profile_hash=reference_profile_hash, transformed_value=pct, candidate_status=status,
            clipping=None, notes=f"candidate only -- not scientifically selected; percentile (tie_convention={transform_config.ecdf_tie_convention}) "
                                  "within a FIT_DEVELOPMENT reference sample is a relative/reference scale, NOT probability",
        )

    return out
