"""Checkpoint 5 Part 9: land-cover adapter interface.

Land cover is a CONTEXTUAL COVARIATE, never proof of LSD transmission —
no adapter in this package computes or returns any transmission/risk
score. Raw, interpretable per-class area fractions only
(`landcover_<class>_fraction`); coefficient/importance assignment is
explicitly out of scope for this checkpoint (master-prompt Part 9).
"""

from __future__ import annotations

from typing import Protocol

from ..feature_result import FeatureResult


class LandCoverAdapter(Protocol):
    def extract_fractions(
        self, *, center_lat: float, center_lon: float, half_extent_km: float
    ) -> list[FeatureResult]:
        ...
