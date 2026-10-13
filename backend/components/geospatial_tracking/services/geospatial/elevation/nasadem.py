"""Checkpoint 5 Part 14: NASADEM interface stub.

NASADEM (NASA JPL) is the elevation product most commonly meant by
"elevation" in remote-sensing contexts, but real access requires a NASA
Earthdata Login (registered credentials not available in this
environment — verified by probing the Earthdata authentication wall
before writing this module). Rather than silently substitute a
different dataset under NASADEM's name, this adapter always returns
BLOCKED with that reason. `elevation/terrain_tiles.py` provides the
actual real, no-auth smoke-test elevation source and is explicitly
labeled as a DIFFERENT dataset (AWS Terrain Tiles), never as NASADEM.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..feature_result import FeatureResult, FeatureStatus

DATASET_NAME = "NASADEM (NASA JPL)"


def extract_elevation(*, latitude: float, longitude: float) -> FeatureResult:
    return FeatureResult(
        feature_name="elevation_m",
        value=None,
        units=None,
        status=FeatureStatus.BLOCKED.value,
        dataset_name=DATASET_NAME,
        dataset_version=None,
        reference_time=None,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        source_resolution=None,
        source_crs=None,
        analysis_method=None,
        quality_notes="NASADEM requires a NASA Earthdata Login; no registered credentials available in this "
        "environment. See elevation/terrain_tiles.py for a real, honestly-labeled, no-auth alternative "
        "(a different dataset, not NASADEM).",
    )
