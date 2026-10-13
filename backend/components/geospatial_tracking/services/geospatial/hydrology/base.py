"""Checkpoint 5 Part 13: hydrology adapter interface.

Water proximity is a CONTEXTUAL COVARIATE (vector/fomite pathway
plausibility), never proof of transmission. Distances are always
computed in a real projected/geodesic-safe way — **never** raw
lat/lon-degree differences treated as kilometers (master-prompt Part 5
applies here too).
"""

from __future__ import annotations

from typing import Protocol

from ..feature_result import FeatureResult


class HydrologyAdapter(Protocol):
    def distance_to_nearest_river_km(
        self, *, center_lat: float, center_lon: float, search_radius_km: float
    ) -> FeatureResult:
        ...

    def distance_to_nearest_lake_km(
        self, *, center_lat: float, center_lon: float, search_radius_km: float
    ) -> FeatureResult:
        ...
