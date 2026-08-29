"""Checkpoint 6A.5 Parts 7-8, 11: the RESOLVED DATA SIGNATURE, land-cover
comparability groups, and cross-snapshot compatibility comparison.

Two identities are kept explicitly separate (Part 7):

- `FeaturePolicy.protocol_hash()` (`feature_policy_hash`) — what the
  researcher DECLARED/configured (`feature_policy.py`). Two AOIs
  assembled under the identical policy always share this hash.
- `compute_resolved_data_signature(...)` (`resolved_data_signature_hash`)
  — what datasets/methods ACTUALLY resolved for THIS particular
  snapshot. Two snapshots built under the identical declared policy can
  still resolve to genuinely different real datasets — the clearest
  real example in this codebase: Sri Lanka (a 2020 event) and Thailand
  (a 2021 event), assembled under the SAME `YEAR_MATCHED_REFERENCE`
  policy, resolve to WorldCover v100 and v200 respectively — different
  algorithm versions, not just different years. `feature_policy_hash`
  alone cannot distinguish them (it's identical for both); the resolved
  signature does.

Same exact resolved scientific configuration -> same resolved signature.
`generated_at`/`retrieved_at` are never part of either hash.
"""

from __future__ import annotations

import hashlib
import json

# Checkpoint 6A.5/6B Part 0: WorldCover algorithm-version comparability groups.
LANDCOVER_GROUP_V100 = "WORLDCOVER_V100"
LANDCOVER_GROUP_V200 = "WORLDCOVER_V200"
LANDCOVER_GROUP_NOT_SELECTED = "NOT_SELECTED"
# Checkpoint 6B Part 0: a non-empty, non-"NOT_SELECTED" version string that
# doesn't match any KNOWN product must never be folded into NOT_SELECTED —
# that would hide a genuinely different, unrecognized future product as if
# land cover had been deliberately omitted. UNRECOGNIZED keeps that case
# visible and flaggable (`compare_feature_compatibility`) instead.
LANDCOVER_GROUP_UNRECOGNIZED = "UNRECOGNIZED"

_WORLDCOVER_VERSION_PREFIX_TO_GROUP = {
    "v100": LANDCOVER_GROUP_V100,
    "v200": LANDCOVER_GROUP_V200,
}


def landcover_comparability_group(dataset_version_label: str | None) -> str:
    """Pure: `dataset_version_label` like `"v100 (2020)"` -> comparability
    group.

    - `None` or the literal `"NOT_SELECTED"` -> `NOT_SELECTED` (land
      cover was deliberately not computed for this snapshot).
    - a KNOWN WorldCover version prefix (`v100`/`v200`) -> its group.
    - any OTHER non-empty string -> `UNRECOGNIZED` (Checkpoint 6B Part 0
      fix — a real dataset_version WAS resolved, it just isn't one of
      the two products this codebase currently knows about; never
      silently collapsed into NOT_SELECTED, which would hide it as if
      land cover had been omitted rather than genuinely different).

    Two `YEAR_MATCHED_REFERENCE` snapshots resolving to v100 and v200
    must NOT be silently pooled into one primary model matrix as if the
    algorithm-version difference were pure environmental change — this
    function is what lets a caller detect that before doing so (see
    `compare_feature_compatibility`)."""
    if not dataset_version_label or dataset_version_label == "NOT_SELECTED":
        return LANDCOVER_GROUP_NOT_SELECTED
    for prefix, group in _WORLDCOVER_VERSION_PREFIX_TO_GROUP.items():
        if dataset_version_label.startswith(prefix):
            return group
    return LANDCOVER_GROUP_UNRECOGNIZED


def compute_resolved_data_signature(
    *,
    feature_policy_hash: str,
    landcover_dataset_version: str,
    host_density_dataset_version: str,
    weather_provider: str,
    weather_model: str,
    weather_model_resolution: str,
    weather_temporal_role: str,
    weather_sampling_strategy: str,
    hydrology_dataset_version: str,
    resolved_t0_cutoff_utc: str | None,
    source_timezone: str | None,
) -> str:
    """Deterministic (SIGNATURE-01): identical resolved configuration ->
    identical hash. Sensitive to real dataset identity (SIGNATURE-02):
    a different `landcover_dataset_version` (e.g. v100 vs v200) changes
    this hash even under an identical declared policy. Never includes
    `generated_at`/`retrieved_at` (SIGNATURE-03)."""
    payload = {
        "feature_policy_hash": feature_policy_hash,
        "landcover_dataset_version": landcover_dataset_version,
        "landcover_comparability_group": landcover_comparability_group(landcover_dataset_version),
        "host_density_dataset_version": host_density_dataset_version,
        "weather_provider": weather_provider,
        "weather_model": weather_model,
        "weather_model_resolution": weather_model_resolution,
        "weather_temporal_role": weather_temporal_role,
        "weather_sampling_strategy": weather_sampling_strategy,
        "hydrology_dataset_version": hydrology_dataset_version,
        "resolved_t0_cutoff_utc": resolved_t0_cutoff_utc,
        "source_timezone": source_timezone,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# Checkpoint 6A.5 Part 11 / 6B Part 0: cross-snapshot compatibility comparison.
MISMATCH_POLICY = "POLICY_MISMATCH"
MISMATCH_LANDCOVER_VERSION = "LANDCOVER_VERSION_MISMATCH"
MISMATCH_LANDCOVER_UNRECOGNIZED = "LANDCOVER_UNRECOGNIZED_PRODUCT"
MISMATCH_WEATHER_MODEL = "WEATHER_MODEL_MISMATCH"
MISMATCH_HOST_DATASET = "HOST_DATASET_MISMATCH"
MISMATCH_HYDROLOGY_DATASET = "HYDROLOGY_DATASET_MISMATCH"
MISMATCH_GRID_PROTOCOL = "GRID_PROTOCOL_MISMATCH"


def compare_feature_compatibility(snapshot_a, snapshot_b) -> list[str]:
    """Reports explicit scientific-compatibility WARNINGS for combining
    two snapshots into one model matrix — never automatically "invalid"
    (Part 11): a caller decides what to do with these, this function
    only makes the difference visible rather than silently pooling
    incompatible resolved datasets."""
    mismatches: list[str] = []

    if snapshot_a.feature_protocol_hash != snapshot_b.feature_protocol_hash:
        mismatches.append(MISMATCH_POLICY)

    group_a = landcover_comparability_group(snapshot_a.source_dataset_versions.get("landcover"))
    group_b = landcover_comparability_group(snapshot_b.source_dataset_versions.get("landcover"))
    if group_a != group_b:
        mismatches.append(MISMATCH_LANDCOVER_VERSION)
    # Checkpoint 6B Part 0: flag an unrecognized product explicitly, even
    # when both sides happen to share the SAME unrecognized group — a
    # caller must never mistake "not NOT_SELECTED" alone for "known and
    # handled."
    if LANDCOVER_GROUP_UNRECOGNIZED in (group_a, group_b):
        mismatches.append(MISMATCH_LANDCOVER_UNRECOGNIZED)

    model_a = snapshot_a.weather.get("window", {}).get("weather_model")
    model_b = snapshot_b.weather.get("window", {}).get("weather_model")
    if model_a != model_b:
        mismatches.append(MISMATCH_WEATHER_MODEL)

    if snapshot_a.source_dataset_versions.get("host_density") != snapshot_b.source_dataset_versions.get("host_density"):
        mismatches.append(MISMATCH_HOST_DATASET)

    if snapshot_a.source_dataset_versions.get("hydrology") != snapshot_b.source_dataset_versions.get("hydrology"):
        mismatches.append(MISMATCH_HYDROLOGY_DATASET)

    grid_a = (snapshot_a.grid_meta.get("cell_size_km"), snapshot_a.grid_meta.get("half_extent_km"))
    grid_b = (snapshot_b.grid_meta.get("cell_size_km"), snapshot_b.grid_meta.get("half_extent_km"))
    if grid_a != grid_b:
        mismatches.append(MISMATCH_GRID_PROTOCOL)

    return mismatches
