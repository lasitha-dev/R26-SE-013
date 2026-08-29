"""Checkpoint 5 Part 4: shared raster helpers.

Small, network-aware utilities reused by every raster-backed adapter
(land cover, host density, elevation). Kept separate from any one
adapter so the "do not download the world" caching discipline (Part 20)
is enforced in exactly one place.
"""

from __future__ import annotations

from pathlib import Path

import requests

from .distance import distance_km

# All real downloaded raster subsets live under here — gitignored, never
# committed (master-prompt Part 20).
LOCAL_GIS_CACHE_DIR = Path(__file__).resolve().parents[5] / "local_data" / "gis"


def bbox_for(center_lat: float, center_lon: float, half_extent_km: float) -> tuple[float, float, float, float]:
    """West, south, east, north degrees bbox for a small AOI window,
    sized via real geodesic distance (never a flat degrees-as-km
    approximation) at the AOI centroid."""
    km_per_deg_lat = distance_km(center_lat, center_lon, center_lat + 0.01, center_lon) / 0.01
    km_per_deg_lon = distance_km(center_lat, center_lon, center_lat, center_lon + 0.01) / 0.01
    dlat = half_extent_km / km_per_deg_lat
    dlon = half_extent_km / km_per_deg_lon
    return (center_lon - dlon, center_lat - dlat, center_lon + dlon, center_lat + dlat)


def download_and_cache(url: str, cache_path: Path, *, timeout_seconds: float = 60.0) -> Path:
    """Download `url` to `cache_path` if not already cached, following
    redirects (Dataverse's access endpoint 303s to a presigned S3 URL).
    Raises on any HTTP/network failure — callers must turn that into a
    BLOCKED FeatureResult, never a fabricated value."""
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=timeout_seconds, allow_redirects=True, stream=True)
    response.raise_for_status()
    tmp_path = cache_path.with_suffix(cache_path.suffix + ".partial")
    with open(tmp_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
    tmp_path.replace(cache_path)
    return cache_path
