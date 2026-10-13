"""Checkpoint 5/5.5/5.6 Parts 17-18: real-data smoke tests for Sri Lanka
(Event_3473) and Thailand (Event_3644).

Not a pytest suite (deliberately — it makes real network calls to
external services and downloads/caches real files, so it must not run
on every `pytest` invocation). Run directly:

    python -m components.geospatial_tracking.smoke_tests.run_smoke_test

Exercises, for each AOI: the smoke grid (Part 7), geometry_by_source
against the OTHER real outbreak localities from the same WAHIS event
(Part 8), land cover with real forecast-origin-year matching (Part 9/10),
grid-cell-aligned host density for EVERY cell in the grid (Checkpoint
5.6 Parts 9-11 — replaces the arbitrary AOI-window radius that was the
final feature through Checkpoint 5.5), a pre-t0-only historical weather
summary built from PAIRED HOURLY wind, timezone-safe DATE_ONLY t0
resolution, and an explicit valid-time-vs-availability-time split
(Checkpoint 5.6 Parts 1-8), river distance (Part 13), and elevation
(Part 14) — every result carrying REAL/MISSING/BLOCKED status, never a
fabricated value. No PISTES risk/direction/speed computation happens
here (a smoke test containing MISSING/BLOCKED entries is an acceptable,
expected outcome when scientifically justified — 100% REAL is not the
gate).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ..config import WEATHER_LOOKBACK_HOURS_DEV_DEFAULT
from ..services.geospatial.elevation.terrain_tiles import extract_elevation
from ..services.geospatial.grid import build_smoke_grid
from ..services.geospatial.host_density.fao_glw import extract_grid_cell_density
from ..services.geospatial.hydrology.hydrosheds import distance_to_nearest_river_km
from ..services.geospatial.landcover.esa_worldcover import extract_landcover_fractions
from ..services.geospatial.raster import LOCAL_GIS_CACHE_DIR
from ..services.geospatial.source_geometry import EligibleSourcePoint, build_geometry_for_grid
from ..services.geospatial.weather.base import T0Precision
from ..services.geospatial.weather.era5 import build_pre_t0_weather_summary

REPORT_DIR = LOCAL_GIS_CACHE_DIR.parent / "smoke_test_reports"

# UNFROZEN_DEVELOPMENT_PARAMETER (config.py): the previous completed 24
# hours before t0 — a documented fixture for this smoke test only, never
# claimed epidemiologically optimal.
SMOKE_LOOKBACK_HOURS = WEATHER_LOOKBACK_HOURS_DEV_DEFAULT


def _feature_result_to_dict(fr) -> dict:
    return asdict(fr) if hasattr(fr, "__dataclass_fields__") else fr


def run_smoke_test(
    *,
    aoi_name: str,
    center_lat: float,
    center_lon: float,
    outbreak_start_date: str,
    worldcover_year: str,
    other_localities: list[EligibleSourcePoint],
    half_extent_km: float = 5.0,
    cell_size_km: float = 2.5,
) -> dict:
    report: dict = {"aoi_name": aoi_name, "center_lat": center_lat, "center_lon": center_lon}

    cells, crs_choice = build_smoke_grid(
        center_lat=center_lat,
        center_lon=center_lon,
        half_extent_km=half_extent_km,
        cell_size_km=cell_size_km,
        id_prefix=aoi_name.upper().replace(" ", "_"),
    )
    report["grid"] = {
        "n_cells": len(cells),
        "analysis_crs": crs_choice.as_dict(),
        "cells": [c.as_dict() for c in cells],
    }

    geometry_by_grid = build_geometry_for_grid(cells, other_localities)
    report["geometry_by_source"] = {
        cell_id: {sid: asdict(vec) for sid, vec in sources.items()}
        for cell_id, sources in geometry_by_grid.items()
    }
    report["eligible_sources"] = [asdict(s) for s in other_localities]

    # Part 9/10: WorldCover year matched to the AOI's real event year —
    # target_year makes the resolver report YEAR_MATCHED_REFERENCE, not a
    # silent "nearest available year" substitution.
    target_year = outbreak_start_date[:4]
    landcover_results = extract_landcover_fractions(
        center_lat=center_lat,
        center_lon=center_lon,
        half_extent_km=half_extent_km,
        worldcover_year=worldcover_year,
        target_year=target_year,
    )
    report["landcover"] = [_feature_result_to_dict(r) for r in landcover_results]

    # Checkpoint 5.6 Parts 9-11: grid-cell-aligned host density for EVERY
    # cell in the computational grid — no arbitrary AOI-window radius.
    # GLW4's native ~10km pixel is coarser than each 2.5km computational
    # cell, so neighboring cells legitimately share a source pixel (and
    # therefore an identical density) — that is the real, honest
    # consequence of "fine computational grid != fine host-density
    # measurement" (Part 10), not a bug.
    host_density_results: list = []
    host_density_by_cell: dict = {}
    for cell in cells:
        cell_results = {}
        for sp in ("cattle", "buffalo"):
            r = extract_grid_cell_density(grid_cell=cell, species=sp)
            host_density_results.append(r)
            cell_results[sp] = _feature_result_to_dict(r)
        host_density_by_cell[cell.grid_cell_id] = cell_results
    center_cell = cells[len(cells) // 2]
    report["host_density"] = {
        "source_resolution": "~10km (GLW4 native grid)",
        "target_grid_resolution_km": cell_size_km,
        "center_cell_id": center_cell.grid_cell_id,
        "center_cell": host_density_by_cell[center_cell.grid_cell_id],
        "by_cell": host_density_by_cell,
        "note": (
            "overlap-area-weighted density per computational grid cell (Checkpoint 5.6) — replaces "
            "Checkpoint 5.5's arbitrary AOI-window radius (which showed 0.0 vs ~44.6 animals/km2 for the "
            "SAME Sri Lanka centroid depending only on window size, with no principled reason to prefer "
            "either). Neighboring cells legitimately sharing one GLW4 source pixel's density is expected, "
            "not an error — the source resolution (~10km) is coarser than the 2.5km computational grid."
        ),
    }

    # Part 5-7/13: PRIMARY weather = pre-t0 observed history only, real
    # forecast-origin semantics (DATE_ONLY: the outbreak_start_date is a
    # calendar date, not an exact trigger timestamp), hourly-paired wind.
    t0_precision = T0Precision.DATE_ONLY.value
    weather_window, weather_results = build_pre_t0_weather_summary(
        latitude=center_lat,
        longitude=center_lon,
        t0=outbreak_start_date,
        t0_precision=t0_precision,
        lookback_hours=SMOKE_LOOKBACK_HOURS,
    )
    report["weather"] = {
        "t0": outbreak_start_date,
        "t0_precision": t0_precision,
        "lookback_hours": SMOKE_LOOKBACK_HOURS,
        "lookback_hours_status": "UNFROZEN_DEVELOPMENT_PARAMETER",
        "window": weather_window.as_dict(),
        "results": [_feature_result_to_dict(r) for r in weather_results],
    }

    river_result = distance_to_nearest_river_km(center_lat=center_lat, center_lon=center_lon, search_radius_km=25.0)
    report["hydrology"] = [_feature_result_to_dict(river_result)]

    elevation_result = extract_elevation(latitude=center_lat, longitude=center_lon)
    report["elevation"] = [_feature_result_to_dict(elevation_result)]

    all_results = landcover_results + host_density_results + weather_results + [river_result, elevation_result]
    report["status_summary"] = {
        status: sum(1 for r in all_results if r.status == status) for status in ("REAL", "MISSING", "BLOCKED", "DEMO")
    }
    report["no_demo_data_confirmed"] = report["status_summary"]["DEMO"] == 0

    return report


def _save_report(report: dict, filename: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    return path


def run_sri_lanka_event_3473() -> dict:
    # Chavakachcheri (9.6579014, 80.1643076) is a real Event_3473 locality
    # (WAHIS Event_3473.pdf, outbreak OB_80064, real outbreak_start_date
    # 2020-09-09). The other real Event_3473 localities are used as
    # `EligibleSourcePoint`s for geometry_by_source. Event year is 2020 —
    # uses WorldCover 2020 v100 (YEAR_MATCHED_REFERENCE), corrected from
    # Checkpoint 5's incorrect 2021 "nearest available year" choice.
    other_localities = [
        EligibleSourcePoint(source_id="Kopay", latitude=9.7151701, longitude=80.0668497),
        EligibleSourcePoint(source_id="Nallur", latitude=9.6734908, longitude=80.0290277),
        EligibleSourcePoint(source_id="Murunkan", latitude=9.75, longitude=80.08333),
        EligibleSourcePoint(source_id="Manthei_west", latitude=8.888178931, longitude=80.0461103553),
        EligibleSourcePoint(source_id="Vavuniya", latitude=9.0621351, longitude=80.6608048),
    ]
    return run_smoke_test(
        aoi_name="sri_lanka_event_3473_chavakachcheri",
        center_lat=9.6579014,
        center_lon=80.1643076,
        outbreak_start_date="2020-09-09",
        worldcover_year="2020",
        other_localities=other_localities,
    )


def run_thailand_event_3644() -> dict:
    # Muang Suang (15.785878, 103.807367) is a real Event_3644 locality
    # (real outbreak_start_date 2021-03-10). Event year is 2021 — uses
    # WorldCover 2021 v200 (YEAR_MATCHED_REFERENCE). Proves cross-country
    # correctness: different UTM zone, different WorldCover tile, no
    # Sri Lanka-specific assumption anywhere in the adapter chain.
    other_localities = [
        EligibleSourcePoint(source_id="Phakdi_Chumphol", latitude=15.788812, longitude=101.374847),
        EligibleSourcePoint(source_id="Amphoe_Muang_Yasothon", latitude=15.794722, longitude=104.140556),
        EligibleSourcePoint(source_id="Kut_Khao_Pun", latitude=15.78944, longitude=104.9951),
    ]
    return run_smoke_test(
        aoi_name="thailand_event_3644_muang_suang",
        center_lat=15.785878,
        center_lon=103.807367,
        outbreak_start_date="2021-03-10",
        worldcover_year="2021",
        other_localities=other_localities,
    )


if __name__ == "__main__":
    sl_report = run_sri_lanka_event_3473()
    sl_path = _save_report(sl_report, "sri_lanka_event_3473.json")
    print(f"Sri Lanka Event_3473 smoke test -> {sl_path}")
    print(json.dumps(sl_report["status_summary"], indent=2))

    th_report = run_thailand_event_3644()
    th_path = _save_report(th_report, "thailand_event_3644.json")
    print(f"Thailand Event_3644 smoke test -> {th_path}")
    print(json.dumps(th_report["status_summary"], indent=2))
