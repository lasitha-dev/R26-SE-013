"""Checkpoint 5 Part 9: real ESA WorldCover land-cover adapter.

Reads directly from ESA's public, no-authentication AWS S3 bucket
(`esa-worldcover.s3.eu-central-1.amazonaws.com`) via GDAL's `/vsicurl/`
mechanism (through `rasterio`) — a windowed HTTP range-request read of
only the small AOI window actually needed, never a full tile download
(WorldCover tiles are ~100s of MB each; master-prompt Part 3: "do not
download the world").

**WorldCover 2020 (v100) and 2021 (v200) were produced with different
algorithm versions — never mixed silently, never compared as if a
difference between them were real land-cover change** (master-prompt Part
2A). `WORLDCOVER_VERSIONS` documents both; every result carries its own
`dataset_version` explicitly. This checkpoint does not choose between
"one frozen static reference layer" and "year-specific sensitivity
analysis" as a modeling policy — that decision is deferred to
`ENVIRONMENTAL_FEATURE_PROTOCOL.md`, and is not made based on any model
performance (none exists).

Class codes are ESA's own official WorldCover v100/v200 legend (LC-01) —
this module never invents an additional class.

**Checkpoint 5.5 Part 10 — land-cover temporal policy resolver.**
`resolve_landcover_temporal_role` reports, per (worldcover_year,
target_year) pair, whether the retrieved layer is a genuine
`YEAR_MATCHED_REFERENCE` for the AOI's real target year (only possible
for 2020 or 2021, the only two years WorldCover ships) or a
`STATIC_REFERENCE_PROXY` for any other year — never silently presenting
either as time-matched when it is not. `v100` (2020) and `v200` (2021)
differ in algorithm, not just year — a difference between them is never
interpreted as real land-cover change (LC-TIME-04), and this checkpoint
does not choose one version over the other based on any later model
performance (no model exists yet).

**Checkpoint 5.5 Part 11 — area-statistic terminology correction.**
`compute_class_fractions` computes `count(class pixels) / count(valid
pixels)` on the COG's native EPSG:4326 pixel grid — a PIXEL-COUNT zonal
statistic, not a true metric/equal-area computation (which would
require reprojecting to the AOI's projected analysis CRS and weighting
by each pixel's real ground area). It is documented and named as such
below rather than overstated as "area-weighted." The approximation is
accepted for this checkpoint's small (~10-20km) AOI windows: WorldCover
pixels are stored on a fixed-degree-spacing grid, so ground area per
pixel varies only with `cos(latitude)`, and across a window this small
the latitude range spanned is a few km — sub-0.1% relative pixel-area
variation, well below this statistic's other sources of imprecision
(class-boundary aliasing at 10m resolution). A future checkpoint
covering a larger or high-latitude AOI should implement true projected
zonal-area weighting instead of relying on this approximation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import rasterio
from rasterio.windows import from_bounds

from ..distance import distance_km
from ..feature_result import FeatureResult, FeatureStatus

DATASET_NAME = "ESA WorldCover"
SOURCE_CRS = "EPSG:4326"
SOURCE_RESOLUTION = "10m"
S3_BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com"

# Official ESA WorldCover class legend (v100 2020 and v200 2021 share the
# same class codes) — never invent a class not in this table.
WORLDCOVER_CLASSES: dict[int, str] = {
    10: "tree_cover",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built_up",
    60: "bare_sparse_vegetation",
    70: "snow_and_ice",
    80: "permanent_water_bodies",
    90: "herbaceous_wetland",
    95: "mangroves",
    100: "moss_and_lichen",
}


@dataclass(frozen=True)
class WorldCoverVersion:
    version: str
    year: str

    @property
    def dataset_version_label(self) -> str:
        return f"{self.version} ({self.year})"


WORLDCOVER_VERSIONS: dict[str, WorldCoverVersion] = {
    "2020": WorldCoverVersion(version="v100", year="2020"),
    "2021": WorldCoverVersion(version="v200", year="2021"),
}

YEAR_MATCHED_REFERENCE = "YEAR_MATCHED_REFERENCE"
STATIC_REFERENCE_PROXY = "STATIC_REFERENCE_PROXY"
UNAVAILABLE_FOR_YEAR = "UNAVAILABLE_FOR_YEAR"


def resolve_landcover_temporal_role(worldcover_year: str, target_year: str | None) -> str:
    """Pure: `YEAR_MATCHED_REFERENCE` only when the retrieved WorldCover
    product's own year equals the AOI's real target year — the only two
    values `worldcover_year` may equal are `"2020"`/`"2021"`, so this is
    only ever true for a target event in one of those two years.
    `UNAVAILABLE_FOR_YEAR` if `worldcover_year` itself isn't a real
    WorldCover product. Otherwise `STATIC_REFERENCE_PROXY` — including
    when `target_year` is `None` (unknown target year is never silently
    treated as a match)."""
    if worldcover_year not in WORLDCOVER_VERSIONS:
        return UNAVAILABLE_FOR_YEAR
    if target_year is not None and target_year == worldcover_year:
        return YEAR_MATCHED_REFERENCE
    return STATIC_REFERENCE_PROXY


def tile_id_for(latitude: float, longitude: float) -> str:
    """WorldCover's 3-degree tile grid, named by the tile's SW corner."""
    lat_floor = int(latitude // 3) * 3
    lon_floor = int(longitude // 3) * 3
    ns = "N" if lat_floor >= 0 else "S"
    ew = "E" if lon_floor >= 0 else "W"
    return f"{ns}{abs(lat_floor):02d}{ew}{abs(lon_floor):03d}"


def tile_url(latitude: float, longitude: float, *, worldcover_year: str = "2021") -> str:
    wc = WORLDCOVER_VERSIONS[worldcover_year]
    tile = tile_id_for(latitude, longitude)
    return f"{S3_BASE}/{wc.version}/{wc.year}/map/ESA_WorldCover_10m_{wc.year}_{wc.version}_{tile}_Map.tif"


def _bbox_for(center_lat: float, center_lon: float, half_extent_km: float) -> tuple[float, float, float, float]:
    km_per_deg_lat = distance_km(center_lat, center_lon, center_lat + 0.01, center_lon) / 0.01
    km_per_deg_lon = distance_km(center_lat, center_lon, center_lat, center_lon + 0.01) / 0.01
    dlat = half_extent_km / km_per_deg_lat
    dlon = half_extent_km / km_per_deg_lon
    return (center_lon - dlon, center_lat - dlat, center_lon + dlon, center_lat + dlat)  # west, south, east, north


def compute_class_fractions(data, nodata) -> dict[int, float]:
    """Pure, network-free core: fraction of valid pixels per official
    class code, from a 2D array `data` and its `nodata` value (may be
    `None`). Nodata pixels are excluded from BOTH the numerator and the
    denominator — never counted as a real class, never silently treated
    as if they were valid observations (LC-02). Deterministic (LC-03):
    same array + nodata always produces the same fractions."""
    valid_mask = data != nodata if nodata is not None else None
    valid_pixels = data[valid_mask] if valid_mask is not None else data.ravel()
    valid_total = valid_pixels.size
    if valid_total == 0:
        return {}
    fractions: dict[int, float] = {}
    for code in WORLDCOVER_CLASSES:
        count = int((valid_pixels == code).sum())
        if count > 0:
            fractions[code] = count / valid_total
    return fractions


def _blocked(reason: str, retrieved_at: str, dataset_version: str | None) -> FeatureResult:
    return FeatureResult(
        feature_name="landcover_extraction",
        value=None,
        units=None,
        status=FeatureStatus.BLOCKED.value,
        dataset_name=DATASET_NAME,
        dataset_version=dataset_version,
        reference_time=None,
        retrieved_at=retrieved_at,
        source_resolution=SOURCE_RESOLUTION,
        source_crs=SOURCE_CRS,
        analysis_method="windowed vsicurl read",
        quality_notes=reason,
    )


def extract_landcover_fractions(
    *,
    center_lat: float,
    center_lon: float,
    half_extent_km: float,
    worldcover_year: str = "2021",
    target_year: str | None = None,
    timeout_seconds: float = 30.0,
) -> list[FeatureResult]:
    """PIXEL-COUNT zonal statistic (see module docstring Part 11 for why
    this is not a true metric area-weighting, and why that's accepted at
    this AOI scale): fraction of valid pixels in each official WorldCover
    class, within a small AOI window read directly off the real S3 COG
    tile (no full-tile download). Deterministic (LC-03) — same AOI + same
    tile version always reads the same window. Nodata pixels are
    excluded from the denominator (LC-02: nodata stays missing, never
    counted as a real class or silently zero-filled).

    `target_year`: the AOI's real target event year, if known — used only
    to compute `resolve_landcover_temporal_role` (Part 10) and label the
    result's `quality_notes` honestly as `YEAR_MATCHED_REFERENCE` or
    `STATIC_REFERENCE_PROXY`. Passing `None` never defaults to claiming a
    match."""
    retrieved_at = datetime.now(timezone.utc).isoformat()
    wc = WORLDCOVER_VERSIONS[worldcover_year]
    temporal_role = resolve_landcover_temporal_role(worldcover_year, target_year)
    url = tile_url(center_lat, center_lon, worldcover_year=worldcover_year)
    vsi_url = f"/vsicurl/{url}"
    west, south, east, north = _bbox_for(center_lat, center_lon, half_extent_km)

    try:
        with rasterio.Env(GDAL_HTTP_TIMEOUT=int(timeout_seconds), CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
            with rasterio.open(vsi_url) as src:
                window = from_bounds(west, south, east, north, transform=src.transform)
                data = src.read(1, window=window)
                nodata = src.nodata
    except Exception as exc:  # rasterio/GDAL raise a variety of exception types for network/format failures
        return [_blocked(f"could not read WorldCover tile {tile_url(center_lat, center_lon, worldcover_year=worldcover_year)}: {exc}", retrieved_at, wc.dataset_version_label)]

    if data.size == 0:
        return [_blocked("AOI window returned zero pixels from the source tile", retrieved_at, wc.dataset_version_label)]

    fractions = compute_class_fractions(data, nodata)
    valid_total = data.size - int((data == nodata).sum()) if nodata is not None else data.size

    if not fractions:
        return [
            FeatureResult(
                feature_name="landcover_all_classes",
                value=None,
                units="fraction",
                status=FeatureStatus.MISSING.value,
                dataset_name=DATASET_NAME,
                dataset_version=wc.dataset_version_label,
                reference_time=wc.year,
                retrieved_at=retrieved_at,
                source_resolution=SOURCE_RESOLUTION,
                source_crs=SOURCE_CRS,
                analysis_method="pixel-count zonal fraction (small-AOI local approximation; see module docstring Part 11)",
                quality_notes=f"every pixel in the AOI window is nodata; temporal_role={temporal_role}",
            )
        ]

    results: list[FeatureResult] = []
    for code, fraction in fractions.items():
        class_name = WORLDCOVER_CLASSES[code]
        results.append(
            FeatureResult(
                feature_name=f"landcover_{class_name}_fraction",
                value=fraction,
                units="fraction",
                status=FeatureStatus.REAL.value,
                dataset_name=DATASET_NAME,
                dataset_version=wc.dataset_version_label,
                reference_time=wc.year,
                retrieved_at=retrieved_at,
                source_resolution=SOURCE_RESOLUTION,
                source_crs=SOURCE_CRS,
                analysis_method="pixel-count zonal fraction over AOI window (small-AOI local approximation; see module docstring Part 11)",
                quality_notes=(
                    f"class_code={code}; {valid_total} valid pixels in window ({data.size - valid_total} nodata excluded); "
                    f"temporal_role={temporal_role} (worldcover_year={worldcover_year}, target_year={target_year})"
                ),
            )
        )
    return results
