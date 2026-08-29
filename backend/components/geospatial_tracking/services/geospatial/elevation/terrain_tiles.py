"""Checkpoint 5 Part 14: real AWS "Terrain Tiles" elevation adapter.

**This is NOT NASADEM.** AWS/Mapzen "Terrain Tiles" (public,
no-authentication S3 bucket `elevation-tiles-prod`) is a real, separate,
independently-attributed elevation dataset (mosaic of SRTM, NED, EU-DEM
and other sources — see AWS Open Data Registry) used here only because
NASADEM itself sits behind a NASA Earthdata Login this environment
cannot complete (`elevation/nasadem.py`). Never described as NASADEM,
never silently substituted for it.

Elevation is decoded from the "Terrarium" PNG tile encoding (documented
by the Terrain Tiles project):
    elevation_m = (red * 256 + green + blue / 256) - 32768
one real pixel value per query point, read via a windowed `/vsicurl/`
GET of a single 256x256 PNG tile (not a bulk download).

Slope is intentionally **not computed** in this checkpoint: a
geospatially-correct slope needs a real multi-pixel DEM window with a
meter-based (not degrees-based) gradient, which is out of scope for
this single-point smoke extraction — computing it approximately here
would risk exactly the "slope from degrees, not meters" error the
master prompt explicitly forbids (Part 5/14). Status for slope stays
unimplemented, not a guessed value.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import rasterio
from rasterio.windows import Window

from ..feature_result import FeatureResult, FeatureStatus

DATASET_NAME = 'AWS "Terrain Tiles" (elevation-tiles-prod, Terrarium encoding)'
TILE_URL_TEMPLATE = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
DEFAULT_ZOOM = 12  # ~38m/pixel near the equator — adequate for a point smoke extraction
TILE_SIZE = 256
UNITS = "m"


def lonlat_to_tile_pixel(latitude: float, longitude: float, zoom: int) -> tuple[int, int, int, int]:
    """Pure: standard slippy-map tile math. Returns (xtile, ytile,
    pixel_x_in_tile, pixel_y_in_tile)."""
    lat_rad = math.radians(latitude)
    n = 2.0**zoom
    x_frac = (longitude + 180.0) / 360.0 * n
    y_frac = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    xtile = int(x_frac)
    ytile = int(y_frac)
    px = int((x_frac - xtile) * TILE_SIZE)
    py = int((y_frac - ytile) * TILE_SIZE)
    return xtile, ytile, px, py


def decode_terrarium_elevation(red: int, green: int, blue: int) -> float:
    """Pure: the Terrarium PNG encoding's documented formula."""
    return (red * 256 + green + blue / 256.0) - 32768.0


def _blocked(reason: str, retrieved_at: str) -> FeatureResult:
    return FeatureResult(
        feature_name="elevation_m",
        value=None,
        units=None,
        status=FeatureStatus.BLOCKED.value,
        dataset_name=DATASET_NAME,
        dataset_version=None,
        reference_time=None,
        retrieved_at=retrieved_at,
        source_resolution=None,
        source_crs="EPSG:4326",
        analysis_method="Terrarium PNG pixel decode",
        quality_notes=reason,
    )


def extract_elevation(*, latitude: float, longitude: float, zoom: int = DEFAULT_ZOOM, timeout_seconds: float = 20.0) -> FeatureResult:
    """Real single-point elevation from a real, no-auth AWS Terrain
    Tiles PNG, read via a windowed vsicurl GET (one pixel's worth of
    data, not a full tile download). Returns BLOCKED — never a
    fabricated elevation — on any read/decode failure."""
    retrieved_at = datetime.now(timezone.utc).isoformat()
    xtile, ytile, px, py = lonlat_to_tile_pixel(latitude, longitude, zoom)
    url = TILE_URL_TEMPLATE.format(z=zoom, x=xtile, y=ytile)
    vsi_url = f"/vsicurl/{url}"

    try:
        with rasterio.Env(GDAL_HTTP_TIMEOUT=int(timeout_seconds), CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".png"):
            with rasterio.open(vsi_url) as src:
                window = Window(px, py, 1, 1)
                red = int(src.read(1, window=window)[0, 0])
                green = int(src.read(2, window=window)[0, 0])
                blue = int(src.read(3, window=window)[0, 0])
    except Exception as exc:
        return _blocked(f"could not read Terrain Tile {url} (zoom={zoom}): {exc}", retrieved_at)

    elevation_m = decode_terrarium_elevation(red, green, blue)

    return FeatureResult(
        feature_name="elevation_m",
        value=elevation_m,
        units=UNITS,
        status=FeatureStatus.REAL.value,
        dataset_name=DATASET_NAME,
        dataset_version="Terrarium encoding",
        reference_time=None,
        retrieved_at=retrieved_at,
        source_resolution=f"zoom {zoom} slippy tile (~{40075.0 * math.cos(math.radians(latitude)) / (2 ** zoom) / TILE_SIZE * 1000:.0f}m/pixel at this latitude)",
        source_crs="EPSG:4326",
        analysis_method="single-pixel read, Terrarium PNG decode: (R*256+G+B/256)-32768",
        quality_notes="AVAILABLE_NOT_YET_SELECTED: real value retrieved, but elevation is not yet included as a "
        "PISTES input feature (no scientific-role justification decided in this checkpoint); "
        "slope not computed (see module docstring)",
    )
