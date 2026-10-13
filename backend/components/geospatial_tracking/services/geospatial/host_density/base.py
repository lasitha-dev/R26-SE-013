"""Checkpoint 5 Part 10: host-density adapter interface.

Treat every result as a REGIONAL LIVESTOCK-DENSITY PROXY — never "exact
farm density," "exact infected animals," or "exact current herd count."
GLW4's reference year is 2015; using it for events from other years is a
`STATIC_REFERENCE_PROXY` (see `GIS_DATA_SOURCES.md`), never presented as
time-matched livestock census truth for that other year.
"""

from __future__ import annotations

from typing import Protocol

from ..feature_result import FeatureResult


class HostDensityAdapter(Protocol):
    def extract_density(
        self, *, center_lat: float, center_lon: float, half_extent_km: float, species: str
    ) -> FeatureResult:
        ...
