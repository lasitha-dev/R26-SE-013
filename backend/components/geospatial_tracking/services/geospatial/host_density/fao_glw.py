"""Checkpoint 5 Part 10: real FAO GLW4 host-density adapter.

GLW4 ("Gridded Livestock of the World", version 4) — the "Da"
(dasymetric-weighted) product, hosted on Harvard Dataverse. Its real
reference year is **2015** (verified directly from the dataset's own
metadata; it is NOT "current" and must never be described as 2020 or as
a live census). Every result therefore carries
`temporal_role=STATIC_REFERENCE_PROXY`: a regional livestock-density
proxy, never exact-farm or exact-current-herd truth (`host_density/base.py`).

**Unit correction discovered while building this adapter**: the shipped
`5_*_2015_Da.tif` raster does NOT contain a density. Its own metadata
document says verbatim: "This geotif layer contains the DA animal
numbers per pixel." An initial version of this module read that raster
and reported its raw values directly as "animals_per_km2" — which was
wrong (it produced an implausible ~3785 animals/km2 for a real Sri
Lanka smoke test) and has been corrected. GLW4 additionally ships a
companion `8_Areakm.tif` (same global 0.083333-decimal-degree/~10km
grid) giving the REAL geodesic area of every pixel in km2 (pixel area
shrinks with latitude — a flat degrees^2 approximation would itself be
a fabrication of the master-prompt's "never calculate ... using raw
lat/lon degrees" kind). Density is therefore derived, per AOI window,
as `sum(animal_count) / sum(pixel_area_km2)` over the same valid
pixels — a real area-weighted density, not a per-pixel ratio-then-
naive-average and not an AOI-max normalization.

Real, no-auth file locations (verified reachable, `curl -L` follows the
303 redirect to a presigned S3 URL successfully):
  - cattle:  DOI 10.7910/DVN/LHBICE, counts "5_Ct_2015_Da.tif" (id 6769711, ~10MB), area "8_Areakm.tif" (id 6769715)
  - buffalo: DOI 10.7910/DVN/I1WCAB, counts "5_Bf_2015_Da.tif" (id 6770179, ~5MB), area "8_Areakm.tif" (id 6770177)

Per master-prompt Part 10: prefer area-weighted/zonal extraction over
centroid-only lookup, and **never normalize by the current AOI's
maximum** — this module only ever returns the raw (real-area-derived)
density value, never rescaled against anything computed from the AOI.

**Checkpoint 5.6 Part 9-11 — grid-cell-aligned extraction, not an
arbitrary AOI-window radius.** `extract_density`'s `half_extent_km`
parameter showed a real problem in Checkpoint 5.5: the extracted Sri
Lanka cattle density was 0.0/km² at a 5km window vs. ~44.6/km² at a
10km window around the SAME centroid — an arbitrary radius choice
materially changes the number, and neither radius was chosen for a
principled reason. `extract_grid_cell_density` replaces that for the
actual computational risk grid: for a given `grid.GridCell`, it finds
every real GLW4 source pixel whose footprint overlaps the cell's own
bounds, computes each pixel's own density (`count / real_area_km2`,
same correction as `compute_zonal_density`), and takes the
OVERLAP-AREA-WEIGHTED mean across those pixels —
`sum(overlap_fraction_i * count_i) / sum(overlap_fraction_i * area_i)`.
A cell fully inside one source pixel algebraically reduces to exactly
that pixel's own density (the overlap fraction cancels — see
`compute_cell_density_from_pixel_overlaps`'s docstring), so a smaller
computational grid never manufactures finer livestock information than
GLW4's real ~10km source resolution actually contains
(`source_resolution` vs. `target_grid_resolution` are both always
reported — HOST-GRID-01..07).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import rasterio
from rasterio.windows import from_bounds

from ..feature_result import FeatureResult, FeatureStatus
from ..raster import LOCAL_GIS_CACHE_DIR, bbox_for, download_and_cache

DATASET_NAME = "FAO Gridded Livestock of the World (GLW4), Da (dasymetric) product"
REFERENCE_YEAR = "2015"
UNITS = "animals_per_km2"
SOURCE_CRS = "EPSG:4326"
SOURCE_RESOLUTION = "0.083333 decimal degrees (~10km at equator, source native resolution)"
TEMPORAL_ROLE = "STATIC_REFERENCE_PROXY"
DATAVERSE_ACCESS_URL = "https://dataverse.harvard.edu/api/access/datafile/{file_id}"


@dataclass(frozen=True)
class GlwSpecies:
    species: str
    doi: str
    count_file_id: int
    count_filename: str
    area_file_id: int
    area_filename: str


GLW_SPECIES: dict[str, GlwSpecies] = {
    "cattle": GlwSpecies(
        species="cattle",
        doi="10.7910/DVN/LHBICE",
        count_file_id=6769711,
        count_filename="5_Ct_2015_Da.tif",
        area_file_id=6769715,
        area_filename="8_Areakm_cattle.tif",
    ),
    "buffalo": GlwSpecies(
        species="buffalo",
        doi="10.7910/DVN/I1WCAB",
        count_file_id=6770179,
        count_filename="5_Bf_2015_Da.tif",
        area_file_id=6770177,
        area_filename="8_Areakm_buffalo.tif",
    ),
}


def compute_zonal_density(count_data, count_nodata, area_data, area_nodata) -> float | None:
    """Pure, network-free core: real area-weighted density = sum(valid
    animal counts) / sum(valid pixel areas km2), over pixels valid in
    BOTH rasters. Never a per-pixel ratio-then-average (that would
    over-weight tiny/edge pixels) and never a flat degrees^2 area
    approximation. Returns None (not 0.0) when there is no valid
    denominator, so "confirmed zero animals" stays distinguishable from
    "no data" (HOST-03)."""
    count_valid = count_data != count_nodata if count_nodata is not None else None
    area_valid = area_data != area_nodata if area_nodata is not None else None
    if count_valid is not None and area_valid is not None:
        valid = count_valid & area_valid
    elif count_valid is not None:
        valid = count_valid
    elif area_valid is not None:
        valid = area_valid
    else:
        valid = None

    if valid is not None:
        counts = count_data[valid]
        areas = area_data[valid]
    else:
        counts = count_data.ravel()
        areas = area_data.ravel()

    total_area = float(areas.sum()) if areas.size else 0.0
    if total_area <= 0:
        return None
    return float(counts.sum()) / total_area


def _cache_path_for(filename: str) -> Path:
    return LOCAL_GIS_CACHE_DIR / "glw" / filename


def _blocked(reason: str, retrieved_at: str, species: str) -> FeatureResult:
    return FeatureResult(
        feature_name=f"host_density_{species}",
        value=None,
        units=None,
        status=FeatureStatus.BLOCKED.value,
        dataset_name=DATASET_NAME,
        dataset_version=REFERENCE_YEAR,
        reference_time=REFERENCE_YEAR,
        retrieved_at=retrieved_at,
        source_resolution=SOURCE_RESOLUTION,
        source_crs=SOURCE_CRS,
        analysis_method="area-weighted zonal density (real per-pixel area raster)",
        quality_notes=reason,
    )


def _read_window(path: Path, bounds: tuple[float, float, float, float]):
    west, south, east, north = bounds
    with rasterio.open(path) as src:
        window = from_bounds(west, south, east, north, transform=src.transform)
        data = src.read(1, window=window)
        nodata = src.nodata
    return data, nodata


def extract_density(
    *,
    center_lat: float,
    center_lon: float,
    half_extent_km: float,
    species: str,
    timeout_seconds: float = 60.0,
) -> FeatureResult:
    """Real, RAW (non-normalized) host-density extraction for one
    species. Downloads (once) and caches both the animal-count raster
    and its companion real-area raster under `local_data/gis/glw/`,
    then derives density = sum(count)/sum(area_km2) over the small AOI
    window needed. Returns BLOCKED — never a fabricated density — on
    any download or read failure."""
    retrieved_at = datetime.now(timezone.utc).isoformat()
    if species not in GLW_SPECIES:
        return _blocked(f"unsupported species '{species}'; supported: {sorted(GLW_SPECIES)}", retrieved_at, species)

    spec = GLW_SPECIES[species]
    count_path = _cache_path_for(spec.count_filename)
    area_path = _cache_path_for(spec.area_filename)
    count_url = DATAVERSE_ACCESS_URL.format(file_id=spec.count_file_id)
    area_url = DATAVERSE_ACCESS_URL.format(file_id=spec.area_file_id)

    try:
        download_and_cache(count_url, count_path, timeout_seconds=timeout_seconds)
        download_and_cache(area_url, area_path, timeout_seconds=timeout_seconds)
    except Exception as exc:
        return _blocked(f"could not download GLW4 {species} count/area raster: {exc}", retrieved_at, species)

    bounds = bbox_for(center_lat, center_lon, half_extent_km)

    try:
        count_data, count_nodata = _read_window(count_path, bounds)
        area_data, area_nodata = _read_window(area_path, bounds)
    except Exception as exc:
        return _blocked(f"could not read cached GLW4 {species} raster: {exc}", retrieved_at, species)

    if count_data.size == 0 or area_data.size == 0 or count_data.shape != area_data.shape:
        return _blocked(
            f"AOI window read mismatch (count shape={count_data.shape}, area shape={area_data.shape})",
            retrieved_at,
            species,
        )

    density = compute_zonal_density(count_data, count_nodata, area_data, area_nodata)
    valid_pixels = int((count_data != count_nodata).sum()) if count_nodata is not None else count_data.size

    if density is None:
        return FeatureResult(
            feature_name=f"host_density_{species}",
            value=None,
            units=UNITS,
            status=FeatureStatus.MISSING.value,
            dataset_name=DATASET_NAME,
            dataset_version=REFERENCE_YEAR,
            reference_time=REFERENCE_YEAR,
            retrieved_at=retrieved_at,
            source_resolution=SOURCE_RESOLUTION,
            source_crs=SOURCE_CRS,
            analysis_method="area-weighted zonal density (real per-pixel area raster)",
            quality_notes="every pixel in the AOI window is nodata in the count and/or area raster",
        )

    return FeatureResult(
        feature_name=f"host_density_{species}",
        value=density,
        units=UNITS,
        status=FeatureStatus.REAL.value,
        dataset_name=DATASET_NAME,
        dataset_version=REFERENCE_YEAR,
        reference_time=REFERENCE_YEAR,
        retrieved_at=retrieved_at,
        source_resolution=SOURCE_RESOLUTION,
        source_crs=SOURCE_CRS,
        analysis_method=(
            "sum(animal count per pixel) / sum(real per-pixel area km2) over AOI window "
            "(source raster is animal COUNT per pixel, not density; area from companion Areakm raster); "
            "RAW value, not AOI-max normalized"
        ),
        quality_notes=(
            f"{TEMPORAL_ROLE}: GLW4 reference year is {REFERENCE_YEAR}, a regional livestock-density proxy, "
            f"not exact/current herd truth; {valid_pixels} valid count pixels in window"
        ),
    )


# ---------------------------------------------------------------------------
# Checkpoint 5.6 Parts 9-11: grid-cell-aligned overlap-area-weighted density
# ---------------------------------------------------------------------------

Bounds = tuple[float, float, float, float]  # (west, south, east, north)


def overlap_fraction(pixel_bounds: Bounds, cell_bounds: Bounds) -> float:
    """Pure: the fraction of `pixel_bounds`'s OWN area that overlaps
    `cell_bounds`. Both are `(west, south, east, north)` in the same
    (degree) units — safe here specifically because this is a ratio of
    two areas of the SAME rectangle (the pixel), so any latitude-
    dependent degrees-to-km distortion cancels out identically in the
    numerator and denominator; it is never used as an absolute area."""
    pw, ps, pe, pn = pixel_bounds
    cw, cs, ce, cn = cell_bounds
    overlap_w = max(0.0, min(pe, ce) - max(pw, cw))
    overlap_h = max(0.0, min(pn, cn) - max(ps, cs))
    pixel_area = (pe - pw) * (pn - ps)
    if pixel_area <= 0:
        return 0.0
    return (overlap_w * overlap_h) / pixel_area


def compute_cell_density_from_pixel_overlaps(
    cell_bounds: Bounds, pixel_records: list[tuple[Bounds, float, float, bool]]
) -> float | None:
    """Pure, network-free core (HOST-GRID-01..06). `pixel_records`: one
    `(pixel_bounds, count, area_km2, is_nodata)` per candidate GLW4
    source pixel. Returns the overlap-area-weighted density:

        sum(overlap_fraction_i * count_i) / sum(overlap_fraction_i * area_km2_i)

    A cell entirely inside a single pixel reduces algebraically to that
    pixel's own `count/area_km2` regardless of the cell's size — the
    shared `overlap_fraction` factor cancels between numerator and
    denominator (HOST-GRID-02): no arbitrary neighborhood-radius
    averaging is introduced by a smaller computational grid.

    Nodata pixels are excluded entirely (HOST-GRID-06) — never treated
    as `count=0`. Returns `None` (never `0.0`) when no valid overlap
    exists, so "confirmed zero animals" stays distinguishable from
    "no data"."""
    weighted_count = 0.0
    weighted_area = 0.0
    for pixel_bounds, count, area_km2, is_nodata in pixel_records:
        if is_nodata:
            continue
        frac = overlap_fraction(pixel_bounds, cell_bounds)
        if frac <= 0.0:
            continue
        weighted_count += frac * count
        weighted_area += frac * area_km2
    if weighted_area <= 0.0:
        return None
    return weighted_count / weighted_area


SAMPLING_PROTOCOL_VERSION = "GLW4_OVERLAP_AREA_WEIGHTED_V1"
# Checkpoint 6D.6 Part 7: a SOFTWARE numerical-representation tolerance
# for the identity digest only (never for the actual density value used
# in the returned `value` field) -- protects the hash against
# insignificant floating-point summation-order noise while still
# distinguishing any materially different weight.
_WEIGHT_DIGEST_DECIMALS = 12


def _effective_pixel_contributions(
    cell_bounds: Bounds, pixel_records: list[tuple[Bounds, float, float, bool]]
) -> list[tuple[tuple[float, float], float]]:
    """Checkpoint 6D.6 Part 1-2: mirrors `compute_cell_density_from_pixel_overlaps`'s
    own filter AND weighting (`frac * area_km2`, the exact denominator
    term that function accumulates) exactly, so the resulting NORMALIZED
    weights represent the true effective contribution of each pixel to
    the density value actually returned — never merely "which pixels
    were touched." Returns `[(pixel_center, normalized_weight), ...]`,
    pixels at an identical center merged (their weights summed) before
    normalization."""
    raw: dict[tuple[float, float], float] = {}
    for pixel_bounds, _count, area_km2, is_nodata in pixel_records:
        if is_nodata:
            continue
        frac = overlap_fraction(pixel_bounds, cell_bounds)
        if frac <= 0.0:
            continue
        west, south, east, north = pixel_bounds
        center = (round((west + east) / 2.0, 6), round((south + north) / 2.0, 6))
        raw[center] = raw.get(center, 0.0) + frac * area_km2
    total = sum(raw.values())
    if total <= 0.0:
        return []
    return sorted((center, weight / total) for center, weight in raw.items())


def contributing_pixel_sample_identity(
    cell_bounds: Bounds, pixel_records: list[tuple[Bounds, float, float, bool]], *, dataset_name: str, dataset_version: str, species: str, source_asset_id: str,
) -> str | None:
    """LEGACY (Checkpoint 6D.5): pixel-SET-only identity — does not
    distinguish different effective weightings of the same pixel set.
    Kept for backward compatibility/audit only; `services/factors/`
    (Checkpoint 6D.6 onward) uses `contributing_pixel_sample_support`
    below, which corrects this."""
    contributions = _effective_pixel_contributions(cell_bounds, pixel_records)
    if not contributions:
        return None
    import hashlib
    import json

    payload = {
        "dataset_name": dataset_name, "dataset_version": dataset_version, "species": species,
        "source_asset_id": source_asset_id, "pixel_centers": [c for c, _w in contributions],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"GLW4PIXELS:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24]}"


def contributing_pixel_sample_support(
    cell_bounds: Bounds, pixel_records: list[tuple[Bounds, float, float, bool]], *, dataset_name: str, dataset_version: str, species: str, source_asset_id: str,
) -> tuple[str | None, int]:
    """Checkpoint 6D.6 Parts 1-4: the CORRECTED effective-sample
    identity. Returns `(sample_support_digest, n_contributing_pixels)`.

    `sample_support_digest` is a deterministic SHA256 over: dataset
    name, dataset version, source asset id, species/band, the SORTED
    `(pixel_center, normalized_weight)` contributions (never dependent
    on input/dict ordering — WEIGHTED-REF-07), nodata-exclusion
    semantics (implicit: only non-nodata, positive-overlap pixels are
    ever included — mirrors `compute_cell_density_from_pixel_overlaps`
    exactly), and `SAMPLING_PROTOCOL_VERSION`. Two grid cells sharing
    the SAME pixel set but DIFFERENT effective overlap weights produce
    DIFFERENT digests (WEIGHTED-REF-03); a cell entirely inside one
    pixel always normalizes to weight `1.0` regardless of the cell's
    own size, so multiple such cells correctly share one digest
    (WEIGHTED-REF-01). Returns `(None, 0)` only when no pixel
    contributed (mirrors the `None`-density case) — never fabricated."""
    contributions = _effective_pixel_contributions(cell_bounds, pixel_records)
    if not contributions:
        return None, 0
    import hashlib
    import json

    payload = {
        "dataset_name": dataset_name, "dataset_version": dataset_version, "species": species,
        "source_asset_id": source_asset_id, "sampling_protocol_version": SAMPLING_PROTOCOL_VERSION,
        "contributions": [[center[0], center[1], round(weight, _WEIGHT_DIGEST_DECIMALS)] for center, weight in contributions],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = f"GLW4SUPPORT:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24]}"
    return digest, len(contributions)


def _pixel_records_from_window(count_path: Path, area_path: Path, padded_bounds: Bounds) -> list[tuple[Bounds, float, float, bool]]:
    """Real I/O: reads a small padded window from both the count and
    area rasters, enumerates each pixel's own real bounds (from the
    raster's affine transform — never assumed from the target grid),
    count, area, and nodata status."""
    with rasterio.open(count_path) as src_count:
        window_count = from_bounds(*padded_bounds, transform=src_count.transform).round_offsets().round_lengths()
        data_count = src_count.read(1, window=window_count)
        nodata_count = src_count.nodata
        window_transform = src_count.window_transform(window_count)

    with rasterio.open(area_path) as src_area:
        window_area = from_bounds(*padded_bounds, transform=src_area.transform).round_offsets().round_lengths()
        data_area = src_area.read(1, window=window_area)
        nodata_area = src_area.nodata

    if data_count.shape != data_area.shape:
        raise ValueError(f"count/area window shape mismatch: {data_count.shape} vs {data_area.shape}")

    records: list[tuple[Bounds, float, float, bool]] = []
    rows, cols = data_count.shape
    for r in range(rows):
        for c in range(cols):
            west, north = window_transform * (c, r)
            east, south = window_transform * (c + 1, r + 1)
            count_val = float(data_count[r, c])
            area_val = float(data_area[r, c])
            is_nodata = (nodata_count is not None and data_count[r, c] == nodata_count) or (
                nodata_area is not None and data_area[r, c] == nodata_area
            )
            records.append(((west, south, east, north), count_val, area_val, is_nodata))
    return records


def extract_grid_cell_density(
    *,
    grid_cell,
    species: str,
    padding_km: float = 15.0,
    timeout_seconds: float = 60.0,
) -> FeatureResult:
    """The PRIMARY host-density extraction for the actual computational
    risk grid (Checkpoint 5.6 Parts 9-11) — replaces an arbitrary
    AOI-window radius with a real overlap-area-weighted mean across
    whatever GLW4 source pixels actually intersect `grid_cell`'s own
    bounds (`grid.GridCell`: uses `centroid_lat`, `centroid_lon`,
    `cell_size_km`, `grid_cell_id`).

    `padding_km` reads a window comfortably larger than the cell
    (default 15km, larger than GLW4's ~10km native pixel) purely so no
    partially-overlapping edge pixel is missed by the raster read — it
    does NOT change which pixels are counted (nodata/geometry filtering
    happens in `compute_cell_density_from_pixel_overlaps`, which only
    ever weights TRUE geometric overlap with the cell itself, never
    anything from the padding margin).

    `source_resolution` (GLW4's real ~10km grid) and the cell's own
    `target_grid_resolution` are both always reported — a smaller
    computational grid cell never implies a finer livestock
    measurement than GLW4 actually contains."""
    retrieved_at = datetime.now(timezone.utc).isoformat()
    if species not in GLW_SPECIES:
        return _blocked(f"unsupported species '{species}'; supported: {sorted(GLW_SPECIES)}", retrieved_at, species)

    spec = GLW_SPECIES[species]
    count_path = _cache_path_for(spec.count_filename)
    area_path = _cache_path_for(spec.area_filename)
    count_url = DATAVERSE_ACCESS_URL.format(file_id=spec.count_file_id)
    area_url = DATAVERSE_ACCESS_URL.format(file_id=spec.area_file_id)

    try:
        download_and_cache(count_url, count_path, timeout_seconds=timeout_seconds)
        download_and_cache(area_url, area_path, timeout_seconds=timeout_seconds)
    except Exception as exc:
        return _blocked(f"could not download GLW4 {species} count/area raster: {exc}", retrieved_at, species)

    cell_half_extent_km = grid_cell.cell_size_km / 2.0
    cell_bounds = bbox_for(grid_cell.centroid_lat, grid_cell.centroid_lon, cell_half_extent_km)
    padded_bounds = bbox_for(grid_cell.centroid_lat, grid_cell.centroid_lon, cell_half_extent_km + padding_km)

    try:
        pixel_records = _pixel_records_from_window(count_path, area_path, padded_bounds)
    except Exception as exc:
        return _blocked(f"could not read cached GLW4 {species} raster for grid cell {grid_cell.grid_cell_id}: {exc}", retrieved_at, species)

    density = compute_cell_density_from_pixel_overlaps(cell_bounds, pixel_records)
    feature_name = f"host_density_{species}_grid_cell"
    target_grid_resolution = f"{grid_cell.cell_size_km}km (computational grid cell {grid_cell.grid_cell_id})"
    sample_identity = contributing_pixel_sample_identity(
        cell_bounds, pixel_records, dataset_name=DATASET_NAME, dataset_version=REFERENCE_YEAR, species=species,
        source_asset_id=spec.count_filename,
    )
    sample_support_digest, n_contributing_pixels = contributing_pixel_sample_support(
        cell_bounds, pixel_records, dataset_name=DATASET_NAME, dataset_version=REFERENCE_YEAR, species=species,
        source_asset_id=spec.count_filename,
    )

    if density is None:
        return FeatureResult(
            feature_name=feature_name,
            value=None,
            units=UNITS,
            status=FeatureStatus.MISSING.value,
            dataset_name=DATASET_NAME,
            dataset_version=REFERENCE_YEAR,
            reference_time=REFERENCE_YEAR,
            retrieved_at=retrieved_at,
            source_resolution=SOURCE_RESOLUTION,
            source_crs=SOURCE_CRS,
            analysis_method="overlap-area-weighted mean density across GLW4 source pixels intersecting the grid cell",
            quality_notes=(
                f"no valid (non-nodata) GLW4 pixel overlaps grid cell {grid_cell.grid_cell_id}; "
                f"target_grid_resolution={target_grid_resolution}"
            ),
        )

    return FeatureResult(
        feature_name=feature_name,
        value=density,
        units=UNITS,
        status=FeatureStatus.REAL.value,
        dataset_name=DATASET_NAME,
        dataset_version=REFERENCE_YEAR,
        reference_time=REFERENCE_YEAR,
        retrieved_at=retrieved_at,
        source_resolution=SOURCE_RESOLUTION,
        source_crs=SOURCE_CRS,
        analysis_method=(
            f"overlap-area-weighted mean density across GLW4 source pixels intersecting grid cell "
            f"{grid_cell.grid_cell_id}; target_grid_resolution={target_grid_resolution}; RAW value, not "
            "AOI-max normalized; fine computational grid != fine host-density measurement"
        ),
        quality_notes=(
            f"{TEMPORAL_ROLE}: GLW4 reference year is {REFERENCE_YEAR}, a regional livestock-density proxy, "
            f"not exact/current herd truth; {len(pixel_records)} candidate source pixel(s) in the padded window"
        ),
        sample_identity=sample_identity,
        sample_support_digest=sample_support_digest,
        sampling_protocol_version=SAMPLING_PROTOCOL_VERSION,
        n_contributing_pixels=n_contributing_pixels,
    )
