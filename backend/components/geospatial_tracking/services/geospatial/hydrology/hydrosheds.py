"""Checkpoint 5 Part 13: real HydroRIVERS (HydroSHEDS) hydrology adapter.

Real, no-auth, range-request-capable source (verified reachable, HTTP
206 on a partial-content probe): HydroRIVERS v1.0, continental shapefile
distributions from data.hydrosheds.org. Both smoke AOIs (Sri Lanka,
Thailand) fall within the "as" (Asia) continental region file — this
adapter currently only supports that region; an AOI outside it returns
BLOCKED rather than silently using the wrong continent's rivers or a
fabricated distance.

Distance is computed the geodesic-safe way required by master-prompt
Part 5/13: the AOI point and every candidate river reach are reprojected
into the AOI's own UTM analysis CRS (`crs.analysis_crs_for`, Part 5 —
never one hardcoded country CRS) and the minimum PLANAR distance is
taken in that metric CRS, then converted to km. Raw lat/lon degree
differences are never used as distance.

HydroLAKES (lake distance) is explicitly **deferred** in this
checkpoint: master-prompt Part 3 requires the smallest real subsets
necessary, and HydroLAKES ships as a single global file well beyond
what a smoke test needs — `distance_to_nearest_lake_km` therefore
always returns BLOCKED with that reason, never a fabricated distance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
from shapely.ops import transform as shapely_transform

from ..crs import WGS84, analysis_crs_for, build_transformer
from ..feature_result import FeatureResult, FeatureStatus
from ..raster import LOCAL_GIS_CACHE_DIR, bbox_for, download_and_cache

DATASET_NAME = "HydroRIVERS v1.0 (HydroSHEDS)"
DATASET_VERSION = "v1.0"
SOURCE_CRS = WGS84
SUPPORTED_REGIONS: dict[str, str] = {
    "as": "https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_as_shp.zip",
}
# path of the .shp *inside* each region's zip (HydroRIVERS nests the
# shapefile in a subfolder alongside a tech-doc PDF, so GDAL's zip
# auto-detection can't be relied on — the inner path must be explicit).
_INNER_SHP_PATH: dict[str, str] = {
    "as": "HydroRIVERS_v10_as_shp/HydroRIVERS_v10_as.shp",
}
UNITS = "km"


def _cache_path_for(region: str) -> Path:
    return LOCAL_GIS_CACHE_DIR / "hydrosheds" / f"HydroRIVERS_v10_{region}_shp.zip"


def nearest_feature_distance_km(point_xy: tuple[float, float], geometries_xy: list) -> float | None:
    """Pure, network-free core: minimum planar distance (already-
    projected metric coordinates, e.g. UTM meters) from `point_xy` to
    any geometry in `geometries_xy`. Returns None (not a fabricated
    number) when there are no candidate geometries."""
    if not geometries_xy:
        return None
    from shapely.geometry import Point

    point = Point(point_xy)
    return min(point.distance(geom) for geom in geometries_xy) / 1000.0


def _blocked(feature_name: str, reason: str, retrieved_at: str) -> FeatureResult:
    return FeatureResult(
        feature_name=feature_name,
        value=None,
        units=None,
        status=FeatureStatus.BLOCKED.value,
        dataset_name=DATASET_NAME,
        dataset_version=DATASET_VERSION,
        reference_time=None,
        retrieved_at=retrieved_at,
        source_resolution=None,
        source_crs=SOURCE_CRS,
        analysis_method="nearest-feature planar distance in AOI UTM CRS",
        quality_notes=reason,
    )


def distance_to_nearest_river_km(
    *,
    center_lat: float,
    center_lon: float,
    search_radius_km: float,
    region: str = "as",
    timeout_seconds: float = 120.0,
) -> FeatureResult:
    """Real distance-to-nearest-river extraction. Downloads (once) and
    caches the continental HydroRIVERS shapefile zip, reads only
    features within a small AOI bbox (geopandas bbox-filtered read —
    never the whole continent into memory), then computes a real
    geodesic-safe planar distance in the AOI's own UTM zone. Returns
    MISSING (not a fabricated distance) if no river reach falls within
    `search_radius_km`, and BLOCKED on any download/read failure."""
    retrieved_at = datetime.now(timezone.utc).isoformat()
    feature_name = "distance_to_nearest_river_km"

    if region not in SUPPORTED_REGIONS:
        return _blocked(
            feature_name,
            f"unsupported HydroRIVERS region '{region}'; supported: {sorted(SUPPORTED_REGIONS)}",
            retrieved_at,
        )

    cache_path = _cache_path_for(region)
    url = SUPPORTED_REGIONS[region]

    try:
        download_and_cache(url, cache_path, timeout_seconds=timeout_seconds)
    except Exception as exc:
        return _blocked(feature_name, f"could not download HydroRIVERS {region} shapefile from {url}: {exc}", retrieved_at)

    bounds = bbox_for(center_lat, center_lon, search_radius_km * 1.5)

    try:
        gdf = gpd.read_file(f"zip://{cache_path}!{_INNER_SHP_PATH[region]}", bbox=bounds)
    except Exception as exc:
        return _blocked(feature_name, f"could not read HydroRIVERS {region} shapefile {cache_path}: {exc}", retrieved_at)

    if gdf.empty:
        return FeatureResult(
            feature_name=feature_name,
            value=None,
            units=UNITS,
            status=FeatureStatus.MISSING.value,
            dataset_name=DATASET_NAME,
            dataset_version=DATASET_VERSION,
            reference_time=None,
            retrieved_at=retrieved_at,
            source_resolution=None,
            source_crs=SOURCE_CRS,
            analysis_method="nearest-feature planar distance in AOI UTM CRS",
            quality_notes=f"no HydroRIVERS reach found within the {search_radius_km * 1.5:.1f}km search bbox",
        )

    crs_choice = analysis_crs_for(center_lat, center_lon)
    transformer = build_transformer(WGS84, crs_choice.analysis_crs)
    project = lambda x, y: transformer.transform(x, y)  # noqa: E731
    point_xy = transformer.transform(center_lon, center_lat)
    geometries_xy = [shapely_transform(project, geom) for geom in gdf.geometry]

    distance_km = nearest_feature_distance_km(point_xy, geometries_xy)

    if distance_km is None or distance_km > search_radius_km:
        return FeatureResult(
            feature_name=feature_name,
            value=None,
            units=UNITS,
            status=FeatureStatus.MISSING.value,
            dataset_name=DATASET_NAME,
            dataset_version=DATASET_VERSION,
            reference_time=None,
            retrieved_at=retrieved_at,
            source_resolution=None,
            source_crs=SOURCE_CRS,
            analysis_method="nearest-feature planar distance in AOI UTM CRS",
            quality_notes=f"nearest HydroRIVERS reach is beyond the requested search_radius_km={search_radius_km}",
        )

    return FeatureResult(
        feature_name=feature_name,
        value=distance_km,
        units=UNITS,
        status=FeatureStatus.REAL.value,
        dataset_name=DATASET_NAME,
        dataset_version=DATASET_VERSION,
        reference_time=None,
        retrieved_at=retrieved_at,
        source_resolution="vector (reach-level), Asia continental HydroRIVERS extract",
        source_crs=SOURCE_CRS,
        analysis_method=f"nearest-feature planar distance in {crs_choice.analysis_crs} (AOI UTM zone {crs_choice.utm_zone}{crs_choice.hemisphere})",
        quality_notes=f"{len(gdf)} candidate reach(es) considered within search bbox",
    )


def distance_to_nearest_lake_km(
    *, center_lat: float, center_lon: float, search_radius_km: float
) -> FeatureResult:
    """HydroLAKES is deliberately NOT integrated in this checkpoint —
    see module docstring. Always BLOCKED, never a fabricated distance."""
    return _blocked(
        "distance_to_nearest_lake_km",
        "HydroLAKES deferred: global single-file dataset exceeds Checkpoint 5's smoke-test scope "
        "(master-prompt Part 3, 'do not download the world'); not yet integrated",
        datetime.now(timezone.utc).isoformat(),
    )
