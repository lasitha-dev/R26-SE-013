"""Checkpoint 5 Part 5: CRS policy — AOI-aware, never hardcoded to one country.

**Storage/interchange CRS: WGS84 / EPSG:4326** for every coordinate this
component stores or exchanges (matches Checkpoint 1-4.5's `latitude`/
`longitude` fields — unchanged).

**Analysis CRS (planar-metric operations — grid cell area, zonal
statistics, raster resampling): chosen PER AOI**, never one fixed EPSG
code for the whole system. A single hardcoded metric CRS (e.g. EPSG:5235,
which is Sri Lanka's national grid) silently distorts area/distance for
every other country — Thailand's real projected CRS is a different UTM
zone entirely. `analysis_crs_for` picks the correct UTM zone from the
AOI's own centroid longitude/hemisphere, which is correct for both
Sri Lanka (UTM 44N) and Thailand (UTM 47N/48N depending on where in the
country) without any per-country special-casing.

Pure geodesic distance/bearing (`services/geospatial/distance.py`) does
NOT need a projected CRS at all — it operates directly on WGS84
ellipsoidal coordinates via `pyproj.Geod`, which is the correct approach
for point-to-point distance/bearing regardless of AOI. The projected
"analysis CRS" here is for operations that genuinely need a planar
plane (e.g. building a regular metric grid, computing polygon area).
"""

from __future__ import annotations

import functools
from dataclasses import dataclass

import pyproj

WGS84 = "EPSG:4326"


@dataclass(frozen=True)
class CrsChoice:
    source_crs: str
    analysis_crs: str
    transform_method: str
    utm_zone: int
    hemisphere: str

    def as_dict(self) -> dict:
        return {
            "source_crs": self.source_crs,
            "analysis_crs": self.analysis_crs,
            "transform_method": self.transform_method,
            "utm_zone": self.utm_zone,
            "hemisphere": self.hemisphere,
        }


def utm_zone_for(longitude: float) -> int:
    """Standard UTM zone number (1-60) for a given longitude."""
    zone = int((longitude + 180) // 6) + 1
    return max(1, min(60, zone))


def analysis_crs_for(latitude: float, longitude: float) -> CrsChoice:
    """AOI-aware planar analysis CRS: WGS84 UTM, zone/hemisphere derived
    from the AOI's own centroid — never a fixed EPSG code. Sri Lanka
    (~9N, 80E) resolves to UTM zone 44N (EPSG:32644); Thailand's Event_3644
    area (~15-19N, 98-104E) resolves to zone 47N/48N (EPSG:326xx)
    depending on exactly where in the country — computed correctly either
    way, never forced to Sri Lanka's zone."""
    zone = utm_zone_for(longitude)
    hemisphere = "N" if latitude >= 0 else "S"
    epsg = (32600 if hemisphere == "N" else 32700) + zone
    return CrsChoice(
        source_crs=WGS84,
        analysis_crs=f"EPSG:{epsg}",
        transform_method="WGS84 -> UTM (AOI centroid zone/hemisphere)",
        utm_zone=zone,
        hemisphere=hemisphere,
    )


@functools.lru_cache(maxsize=256)
def build_transformer(source_crs: str, target_crs: str) -> pyproj.Transformer:
    """Cached — `pyproj.Transformer.from_crs` does real CRS-database work
    on every call; construction is otherwise stateless/pure given the
    same (source_crs, target_crs) pair, so real callers that build many
    transformers for the same few CRS pairs (e.g. one UTM zone per real
    local forecast context, across many candidate parameters) are not
    forced to repeat that work. Never affects correctness — a cached
    transformer is functionally identical to a freshly constructed one."""
    return pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)
