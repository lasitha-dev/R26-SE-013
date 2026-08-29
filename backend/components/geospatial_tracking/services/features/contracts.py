"""Checkpoint 6A Parts 3, 15, 21: the FeatureSnapshot contract,
readiness concepts, and deterministic snapshot identity.

No field here is `risk`, `probability`, `confidence`, `spread_direction`,
or `speed` — this checkpoint assembles raw, provenance-preserving
environmental/geometry inputs only (Part 3). The later PISTES risk
engine consumes a `FeatureSnapshot`; it never calls WorldCover/GLW/
ERA5/HydroRIVERS adapters directly.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum


class SnapshotReadiness(str, Enum):
    """Never called "model confidence" (Part 15) — these describe
    whether ASSEMBLY succeeded, not how much a future model should
    trust the result."""

    COMPLETE_FOR_ASSEMBLY = "COMPLETE_FOR_ASSEMBLY"
    INCOMPLETE_REQUIRED_FEATURE = "INCOMPLETE_REQUIRED_FEATURE"
    CANDIDATE_FEATURE_MISSING = "CANDIDATE_FEATURE_MISSING"


@dataclass
class GridCellFeatures:
    grid_cell_id: str
    row: int
    col: int
    centroid_lat: float
    centroid_lon: float
    cell_size_km: float
    area_km2: float
    geometry_by_source: dict  # source_id -> {distance_km, t_hat_east, t_hat_north}
    host_density: dict  # species -> FeatureResult.as_dict()
    landcover: dict | None  # class_name -> FeatureResult.as_dict(), or None == NOT_SELECTED
    hydrology: dict | None  # FeatureResult.as_dict(), or None == NOT_SELECTED

    def as_dict(self) -> dict:
        return {
            "grid_cell_id": self.grid_cell_id,
            "row": self.row,
            "col": self.col,
            "centroid_lat": self.centroid_lat,
            "centroid_lon": self.centroid_lon,
            "cell_size_km": self.cell_size_km,
            "area_km2": self.area_km2,
            "geometry_by_source": self.geometry_by_source,
            "host_density": self.host_density,
            "landcover": self.landcover,
            "hydrology": self.hydrology,
        }


@dataclass
class FeatureSnapshot:
    snapshot_id: str
    forecast_origin_id: str
    t0: str
    t0_precision: str
    temporal_mode: str
    country_scope: str | None
    disease: str

    active_source_ids: list = field(default_factory=list)
    active_source_count: int = 0

    grid_meta: dict = field(default_factory=dict)
    grid_cells: list = field(default_factory=list)  # list[GridCellFeatures]

    weather: dict = field(default_factory=dict)  # {window: {...}, results: {feature_name: {...}}}
    weather_sampling_location: str = "AOI_CENTER"

    feature_status_summary: dict = field(default_factory=dict)
    source_dataset_versions: dict = field(default_factory=dict)
    landcover_comparability_group: str = "NOT_SELECTED"

    # Checkpoint 6A.5 Part 10: surfaced explicitly (not just nested
    # inside weather.window) so their relationship to snapshot identity
    # is visible without digging into the weather block.
    source_timezone: str | None = None
    t0_timezone_quality: str | None = None
    resolved_t0_cutoff_utc: str | None = None

    feature_protocol_version: str = ""
    feature_protocol_config: dict = field(default_factory=dict)
    feature_policy_hash: str = ""  # Checkpoint 6A.5: what was DECLARED
    resolved_data_signature_hash: str = ""  # Checkpoint 6A.5: what ACTUALLY resolved

    readiness: str = SnapshotReadiness.INCOMPLETE_REQUIRED_FEATURE.value
    readiness_notes: list = field(default_factory=list)

    generated_at: str = ""

    @property
    def feature_protocol_hash(self) -> str:
        """Backward-compatible alias for `feature_policy_hash` (the name
        used through Checkpoint 6A) — Checkpoint 6A.5 introduced the more
        precise `feature_policy_hash`/`resolved_data_signature_hash`
        split; existing callers reading `.feature_protocol_hash` still
        see the declared-policy hash."""
        return self.feature_policy_hash

    def as_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "forecast_origin_id": self.forecast_origin_id,
            "t0": self.t0,
            "t0_precision": self.t0_precision,
            "temporal_mode": self.temporal_mode,
            "country_scope": self.country_scope,
            "disease": self.disease,
            "active_source_ids": self.active_source_ids,
            "active_source_count": self.active_source_count,
            "grid": self.grid_meta,
            "grid_cells": [c.as_dict() if hasattr(c, "as_dict") else c for c in self.grid_cells],
            "weather": self.weather,
            "weather_sampling_location": self.weather_sampling_location,
            "feature_status_summary": self.feature_status_summary,
            "source_dataset_versions": self.source_dataset_versions,
            "landcover_comparability_group": self.landcover_comparability_group,
            "source_timezone": self.source_timezone,
            "t0_timezone_quality": self.t0_timezone_quality,
            "resolved_t0_cutoff_utc": self.resolved_t0_cutoff_utc,
            "feature_protocol_version": self.feature_protocol_version,
            "feature_protocol_config": self.feature_protocol_config,
            "feature_policy_hash": self.feature_policy_hash,
            "resolved_data_signature_hash": self.resolved_data_signature_hash,
            "readiness": self.readiness,
            "readiness_notes": self.readiness_notes,
            "generated_at": self.generated_at,
        }

    def as_dict_excluding_generated_at(self) -> dict:
        """For determinism checks (ASSEMBLY-01) — everything except the
        one field that's allowed, expected to vary between two
        otherwise-identical assembly runs."""
        d = self.as_dict()
        d.pop("generated_at", None)
        return d


def compute_snapshot_id(
    *,
    forecast_origin_id: str,
    t0: str,
    t0_precision: str,
    temporal_mode: str,
    country_scope: str | None,
    disease: str,
    active_source_ids: list,
    grid_config: dict,
    feature_policy_hash: str,
    resolved_data_signature_hash: str,
) -> str:
    """Deterministic (Part 21, extended by Checkpoint 6A.5 Part 9):
    depends only on scientific inputs. `t0_precision` is now included
    explicitly — DATE_ONLY and TIMESTAMP resolve to different weather
    windows for the same nominal `t0` string, so they must never share
    a snapshot ID; `resolved_data_signature_hash` is included so a
    change in what ACTUALLY resolved (e.g. WorldCover v100 vs v200)
    changes the ID even under an identical declared `FeaturePolicy`.
    Never a random UUID and never `generated_at`."""
    payload = {
        "forecast_origin_id": forecast_origin_id,
        "t0": t0,
        "t0_precision": t0_precision,
        "temporal_mode": temporal_mode,
        "country_scope": country_scope,
        "disease": disease,
        "active_source_ids": sorted(active_source_ids),
        "grid_config": grid_config,
        "feature_policy_hash": feature_policy_hash,
        "resolved_data_signature_hash": resolved_data_signature_hash,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"SNAPSHOT:{digest[:24]}"
