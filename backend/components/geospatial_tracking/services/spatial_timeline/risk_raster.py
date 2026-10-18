"""Day-d risk field raster for the map (Risk Zones surface + hover card).

Evaluates the engine's practical risk field (engine.py, RISK_FIELD_*) on a
fixed lon/lat grid over Sri Lanka, so the map only colours numbers the
backend computed:

    F_d(x) = sum_j exp(-r_j / 25 km) * min(g_reach_j, p_j * g_path_j + (1 - p_j) * g_iso_j),   score B = 1 - exp(-F_d)

Grid: GRID_STEP_DEG (~1.65 km) cells anchored at (GRID_WEST, GRID_SOUTH);
cell (i, j) is centred at (GRID_WEST + (i + 0.5) * step, GRID_SOUTH + (j + 0.5) * step),
j counting northward. Distances are local flat-earth km (< 0.3 % off the
geodesic within the 25 km domain). Only cells on scored land (plus one cell
of margin for the map's interpolation at the coast) are evaluated.

Encoding of one day (`encode`): the smallest window [i0, j0, w, h] holding
every drawn cell; `mask` = row-major bitset of the drawn cells (row 0 =
southern row, numpy `packbits` big-endian bit order); `pixels` = for each
drawn cell in the same order, 8 bytes little-endian:
    score  u8   round(B * 250)  (1..250; B >= MIN_SCORE)
    count  u8   cases holding >= MIN_SHARE of F_d here
    share1 u8   round(share of the largest contributor * 250)
    share2 u8   round(share of the second contributor * 250), 0 if none
    case1  u16  1-based index into the snapshot's `sources` list
    case2  u16  1-based index of the second contributor, 0 if none
"""

from __future__ import annotations

import base64
import math

import numpy as np
import shapely

from ..model_development.candidate_registry_7c import FROZEN_KERNEL_SCALE_KM

GRID_WEST = 79.4
GRID_SOUTH = 5.7
GRID_STEP_DEG = 0.015
MIN_SCORE = 0.03
MIN_SHARE = 0.01
LEVELS = 250
GATE_SDS = 3.5  # Gaussian gates are < 0.2 % beyond this
KM_PER_DEG_LAT = 110.574

_PIXEL = np.dtype([("score", "u1"), ("count", "u1"), ("share1", "u1"), ("share2", "u1"), ("case1", "<u2"), ("case2", "<u2")])


def _km_per_deg_lon(lat):
    return 111.32 * np.cos(np.radians(lat))


# Headings over half a turn (the other half is its mirror image).
_ISO_HEADINGS = (np.arange(180) + 0.5) * math.pi / 180


def iso_gate(r_km, length_km: float, sd_km: float):
    """Direction-averaged tube gate: exp(-1/2 (d/sd)^2) around a straight path
    of `length_km` from the case, averaged over every heading -- the gate when
    the model gives no direction (a case's spread, direction unknown)."""
    r = np.asarray(r_km, dtype=float)[..., None]
    cos, sin = np.cos(_ISO_HEADINGS), np.sin(_ISO_HEADINGS)
    along = np.clip(r * cos, 0.0, length_km)
    d = np.hypot(r - along * cos, along * sin)
    return np.exp(-0.5 * (d / sd_km) ** 2).mean(axis=-1)


def kernel_radius_km(kernel: dict) -> float:
    """Distance from the case beyond which the kernel is negligible."""
    lon0, lat0 = kernel["origin"]
    kx = float(_km_per_deg_lon(lat0))
    path = max(math.hypot((lon - lon0) * kx, (lat - lat0) * KM_PER_DEG_LAT) + core + GATE_SDS * sd for lon, lat, core, sd in kernel["spine"])
    iso = kernel.get("iso_length_km", 0.0) + GATE_SDS * kernel["fringe_km"]
    return min(max(path, iso), kernel["reach_km"] + GATE_SDS * kernel["fringe_km"])


def kernel_values(kernel: dict, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    """c_j on a lon/lat mesh (same shape)."""
    lon0, lat0 = kernel["origin"]
    kx = _km_per_deg_lon(lats)
    r = np.hypot((lons - lon0) * kx, (lats - lat0) * KM_PER_DEG_LAT)
    g_reach = np.exp(-0.5 * (np.maximum(0.0, r - kernel["reach_km"]) / kernel["fringe_km"]) ** 2)
    g_path = np.zeros_like(r)
    for plon, plat, core, sd in kernel["spine"]:
        d = np.hypot((lons - plon) * kx, (lats - plat) * KM_PER_DEG_LAT)
        np.maximum(g_path, np.exp(-0.5 * (np.maximum(0.0, d - core) / sd) ** 2), out=g_path)
    share = kernel.get("directional_share", 1.0)
    if share < 1.0:
        # Radial table of the direction-averaged gate, interpolated per cell.
        table_r = np.arange(0.0, float(r.max(initial=0.0)) + 0.2, 0.1)
        g_iso = np.interp(r, table_r, iso_gate(table_r, kernel.get("iso_length_km", 0.0), kernel["fringe_km"]))
        g_path = share * g_path + (1.0 - share) * g_iso
    return kernel.get("weight", 1.0) * np.exp(-r / FROZEN_KERNEL_SCALE_KM) * np.minimum(g_path, g_reach)


def district_cells(district_geometry, land_geometry):
    """Grid cell centres inside the district (on land) and each cell's area
    in km2 -- the cells the district influence below is counted on."""
    west, south, east, north = district_geometry.bounds
    i0, i1 = math.floor((west - GRID_WEST) / GRID_STEP_DEG), math.ceil((east - GRID_WEST) / GRID_STEP_DEG)
    j0, j1 = math.floor((south - GRID_SOUTH) / GRID_STEP_DEG), math.ceil((north - GRID_SOUTH) / GRID_STEP_DEG)
    lons, lats = np.meshgrid(GRID_WEST + (np.arange(i0, i1) + 0.5) * GRID_STEP_DEG, GRID_SOUTH + (np.arange(j0, j1) + 0.5) * GRID_STEP_DEG)
    region = district_geometry.intersection(land_geometry) if land_geometry is not None else district_geometry
    inside = shapely.contains_xy(region, lons, lats)
    lons, lats = lons[inside], lats[inside]
    return lons, lats, (GRID_STEP_DEG * KM_PER_DEG_LAT) * (GRID_STEP_DEG * _km_per_deg_lon(lats))


def source_district_influence(kernel: dict, cells) -> dict:
    """One source's own day-d influence inside a district: the land area of
    the district cells where its kernel alone reaches the map's visible score
    (1 - exp(-c_j) >= MIN_SCORE), and its highest score there."""
    lons, lats, cell_km2 = cells
    if not len(lons):
        return {"area_km2": 0.0, "max_score": None}
    lon0, lat0 = kernel["origin"]
    r = np.hypot((lons - lon0) * _km_per_deg_lon(lats), (lats - lat0) * KM_PER_DEG_LAT)
    if r.min() > kernel_radius_km(kernel):
        return {"area_km2": 0.0, "max_score": None}
    score = 1.0 - np.exp(-kernel_values(kernel, lons, lats))
    hit = score >= MIN_SCORE
    if not hit.any():
        return {"area_km2": 0.0, "max_score": None}
    return {"area_km2": round(float(cell_km2[hit].sum()), 3), "max_score": round(float(score[hit].max()), 4)}


class ScoredLand:
    """The cells the map may colour: scored land plus one grid cell of margin."""

    def __init__(self, geometry):
        self.geometry = geometry.buffer(GRID_STEP_DEG) if geometry is not None and not geometry.is_empty else None
        if self.geometry is not None:
            shapely.prepare(self.geometry)

    def window_for(self, kernels: list[dict]) -> tuple[int, int, int, int] | None:
        if self.geometry is None or not kernels:
            return None
        west, south, east, north = self.geometry.bounds
        boxes = []
        for kernel in kernels:
            radius = kernel_radius_km(kernel)
            lon0, lat0 = kernel["origin"]
            dlon = radius / float(_km_per_deg_lon(lat0))
            dlat = radius / KM_PER_DEG_LAT
            boxes.append((max(west, lon0 - dlon), max(south, lat0 - dlat), min(east, lon0 + dlon), min(north, lat0 + dlat)))
        w0, s0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        e0, n0 = max(b[2] for b in boxes), max(b[3] for b in boxes)
        if w0 >= e0 or s0 >= n0:
            return None
        i0, j0 = math.floor((w0 - GRID_WEST) / GRID_STEP_DEG), math.floor((s0 - GRID_SOUTH) / GRID_STEP_DEG)
        i1, j1 = math.ceil((e0 - GRID_WEST) / GRID_STEP_DEG), math.ceil((n0 - GRID_SOUTH) / GRID_STEP_DEG)
        return max(0, i0), max(0, j0), max(1, i1 - max(0, i0)), max(1, j1 - max(0, j0))


def build_day_raster(kernels: list[dict], source_index: dict[str, int], land: ScoredLand) -> dict | None:
    """Encoded day-d raster (see module docstring), or None when nothing is drawn."""
    window = land.window_for(kernels)
    if window is None:
        return None
    i0, j0, w, h = window
    lons1 = GRID_WEST + (np.arange(i0, i0 + w) + 0.5) * GRID_STEP_DEG
    lats1 = GRID_SOUTH + (np.arange(j0, j0 + h) + 0.5) * GRID_STEP_DEG
    lons, lats = np.meshgrid(lons1, lats1)  # row 0 = southern row
    on_land = shapely.contains_xy(land.geometry, lons, lats)
    if not on_land.any():
        return None
    values = np.zeros((len(kernels), h, w))
    for k, kernel in enumerate(kernels):
        # Only the kernel's own influence box.
        radius = kernel_radius_km(kernel)
        lon0, lat0 = kernel["origin"]
        dlon, dlat = radius / float(_km_per_deg_lon(lat0)), radius / KM_PER_DEG_LAT
        cols = slice(max(0, math.floor((lon0 - dlon - GRID_WEST) / GRID_STEP_DEG) - i0), max(0, math.ceil((lon0 + dlon - GRID_WEST) / GRID_STEP_DEG) - i0 + 1))
        rows = slice(max(0, math.floor((lat0 - dlat - GRID_SOUTH) / GRID_STEP_DEG) - j0), max(0, math.ceil((lat0 + dlat - GRID_SOUTH) / GRID_STEP_DEG) - j0 + 1))
        sub = on_land[rows, cols]
        if sub.any():
            values[k, rows, cols][sub] = kernel_values(kernel, lons[rows, cols][sub], lats[rows, cols][sub])
    total = values.sum(axis=0)
    score = 1.0 - np.exp(-total)
    drawn = on_land & (score >= MIN_SCORE)
    if not drawn.any():
        return None
    v = values[:, drawn]  # kernels x drawn cells
    t = total[drawn]
    order = np.argsort(-v, axis=0)
    first, second = order[0], order[1] if len(kernels) > 1 else np.zeros_like(order[0])
    cols = np.arange(v.shape[1])
    share1 = v[first, cols] / t
    share2 = v[second, cols] / t if len(kernels) > 1 else np.zeros_like(share1)
    case_ids = np.array([source_index[k["source_id"]] + 1 for k in kernels], dtype=np.uint16)
    pixels = np.zeros(v.shape[1], dtype=_PIXEL)
    pixels["score"] = np.clip(np.rint(score[drawn] * LEVELS), 1, LEVELS)
    pixels["count"] = np.minimum(255, (v / t >= MIN_SHARE).sum(axis=0))
    pixels["share1"] = np.rint(share1 * LEVELS)
    pixels["share2"] = np.where(share2 >= MIN_SHARE, np.rint(share2 * LEVELS), 0)
    pixels["case1"] = case_ids[first]
    pixels["case2"] = np.where(share2 >= MIN_SHARE, case_ids[second], 0)
    return {
        "window": [i0, j0, w, h],
        "drawn_cells": int(drawn.sum()),
        "mask": base64.b64encode(np.packbits(drawn.ravel()).tobytes()).decode("ascii"),
        "pixels": base64.b64encode(pixels.tobytes()).decode("ascii"),
    }


def decode_day_raster(raster: dict) -> dict:
    """Inverse of `build_day_raster` (tests and tooling)."""
    i0, j0, w, h = raster["window"]
    drawn = np.unpackbits(np.frombuffer(base64.b64decode(raster["mask"]), dtype=np.uint8))[: w * h].reshape(h, w).astype(bool)
    pixels = np.frombuffer(base64.b64decode(raster["pixels"]), dtype=_PIXEL)
    return {"window": (i0, j0, w, h), "drawn": drawn, "pixels": pixels}


GRID_SPEC = {
    "west": GRID_WEST, "south": GRID_SOUTH, "step_deg": GRID_STEP_DEG, "levels": LEVELS,
    "min_score": MIN_SCORE, "min_share": MIN_SHARE,
    "pixel_layout": "u8 score, u8 count, u8 share1, u8 share2, u16le case1, u16le case2 (1-based index into sources)",
    "mask_layout": "row-major bitset over the window, row 0 = southern row, MSB first",
}
