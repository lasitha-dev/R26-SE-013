"""Checkpoint 5 Part 14: elevation adapter interface.

Elevation/slope is not automatically included in PISTES — a genuine
scientific-role justification (e.g. drainage/runoff proxy for
fomite spread) would be needed first. Every result here can legitimately
carry status `AVAILABLE_NOT_YET_SELECTED` even when a real value was
retrieved: retrieval capability and model-inclusion decision are
separate questions.
"""

from __future__ import annotations

from typing import Protocol

from ..feature_result import FeatureResult


class ElevationAdapter(Protocol):
    def extract_elevation(self, *, latitude: float, longitude: float) -> FeatureResult:
        ...
