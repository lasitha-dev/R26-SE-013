"""Checkpoint 5 Part 1/4: machine-readable GIS source registry model.

Mirrors `local_data/manifests/gis_source_registry.json` (the
human/tool-readable manifest) and `GIS_DATA_SOURCES.md` (the narrative
doc) — every entry here has a matching entry in both. Kept in sync by
hand in this checkpoint; there is no automated writer yet.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class GisSourceEntry:
    dataset_name: str
    provider: str
    official_source: str
    dataset_version: str
    reference_year_or_temporal_coverage: str
    spatial_resolution: str
    native_crs: str
    file_format: str
    variables_used: tuple[str, ...]
    license: str
    citation: str
    retrieval_method: str
    retrieval_date: str
    local_file_hash: str | None
    scientific_role: str
    temporal_role: str
    known_limitations: str
    status: str

    def as_dict(self) -> dict:
        d = asdict(self)
        d["variables_used"] = list(self.variables_used)
        return d


REGISTRY: tuple[GisSourceEntry, ...] = (
    GisSourceEntry(
        dataset_name="ESA WorldCover",
        provider="European Space Agency (ESA) / VITO / consortium",
        official_source="https://esa-worldcover.org (public COG tiles: esa-worldcover.s3.eu-central-1.amazonaws.com)",
        dataset_version="v100 (2020) and v200 (2021) — both present, never mixed silently",
        reference_year_or_temporal_coverage="2020 (v100) or 2021 (v200), single-year global land-cover snapshot per version",
        spatial_resolution="10m",
        native_crs="EPSG:4326",
        file_format="Cloud-Optimized GeoTIFF (COG)",
        variables_used=("land_cover_class",),
        license="CC BY 4.0",
        citation="Zanaga et al. (2021/2022), ESA WorldCover 10 m v100/v200, doi:10.5281/zenodo.5571936 (v100) / 10.5281/zenodo.7254221 (v200)",
        retrieval_method="windowed HTTP GET via GDAL /vsicurl/ (rasterio), no full-tile download",
        retrieval_date="2026-08-18",
        local_file_hash="not cached as a static file — windowed vsicurl reads only, no full tile stored locally",
        scientific_role="contextual land-cover covariate (per-class area fraction, zonal statistic)",
        temporal_role="STATIC_REFERENCE_PROXY",
        known_limitations=(
            "only two single-year snapshots exist (2020, 2021); using either for an event in any other year is a "
            "static proxy, not time-matched ground truth; v100/v200 differ in algorithm, not just year, so a "
            "difference between them is not real land-cover change"
        ),
        status="REAL",
    ),
    GisSourceEntry(
        dataset_name="FAO Gridded Livestock of the World (GLW4), Da product",
        provider="FAO / Fondation Bill & Melinda Gates / Univ. Liverpool (GLW4 consortium)",
        official_source="https://dataverse.harvard.edu (dataverse 'glw', GLW4 sub-dataverse)",
        dataset_version="GLW4 Da (dasymetric)",
        reference_year_or_temporal_coverage="2015 (verified from source metadata; NOT 2020, common misconception)",
        spatial_resolution="0.083333 decimal degrees (~10km at equator)",
        native_crs="EPSG:4326",
        file_format="GeoTIFF",
        variables_used=("cattle_count_per_pixel", "buffalo_count_per_pixel", "pixel_area_km2"),
        license="CC0 1.0 (per Dataverse dataset metadata)",
        citation=(
            "cattle: doi:10.7910/DVN/LHBICE 'Global cattle distribution in 2015'; "
            "buffalo: doi:10.7910/DVN/I1WCAB 'Global buffaloes distribution in 2015'"
        ),
        retrieval_method="HTTP GET via Dataverse access API (303 redirect to presigned S3 URL), cached locally",
        retrieval_date="2026-08-18",
        local_file_hash=(
            "5_Ct_2015_Da.tif(sha256)=16faa66cc8a6e78efc77bb942b56ebf3e8e2d02496e3ec77f59aaf080248dbdf; "
            "5_Bf_2015_Da.tif(sha256)=cdb61be53c2c90a966281ec3c43cd6843bddb9374496759a98ef634350a15736; "
            "8_Areakm.tif(sha256, identical for both species datasets)=ec13f93df87bccbdbc297778681879609d8cb32497b5e4e50a83f4325da99e39"
        ),
        scientific_role="regional livestock host-density proxy (area-weighted density = sum(count)/sum(real pixel area))",
        temporal_role="STATIC_REFERENCE_PROXY",
        known_limitations=(
            "reference year 2015; the raw raster stores animal COUNT per pixel, not density directly — density is "
            "derived here using the companion Areakm raster's real per-pixel area, never a flat degrees^2 "
            "approximation; never normalize by current-AOI maximum; never treat as an exact/current herd count; "
            "the computational-risk-grid feature (extract_grid_cell_density, Checkpoint 5.6) uses an overlap-area-"
            "weighted mean across intersecting source pixels per grid cell, not an arbitrary AOI-window radius — "
            "a finer computational grid never implies a finer livestock measurement than GLW4's real ~10km "
            "resolution actually contains"
        ),
        status="REAL",
    ),
    GisSourceEntry(
        dataset_name="ERA5 reanalysis (via Open-Meteo Historical Weather API, intermediary)",
        provider="ECMWF / Copernicus Climate Change Service (C3S, original reanalysis); Open-Meteo (intermediary API, not the data producer)",
        official_source="https://archive-api.open-meteo.com/v1/archive (explicit models=era5 — see services/geospatial/weather/era5.py module docstring for the full model-selection evidence: ERA5-Land lacks wind/precip entirely for this API; era5_seamless/best_match silently blend ERA5-Land+ERA5; ecmwf_ifs is a temporally-inconsistent operational archive per Open-Meteo's own documentation; cerra does not cover either smoke AOI)",
        dataset_version="ERA5 (models=era5) — single fixed-version reanalysis, not the unset best_match default",
        reference_year_or_temporal_coverage="1940-present, hourly reanalysis (retrieved per pre-t0 window, per-AOI)",
        spatial_resolution="0.25 degrees (~25km at equator) — ERA5's native reanalysis grid, verified via official Open-Meteo documentation and live request/response probing on 2026-08-19",
        native_crs="EPSG:4326",
        file_format="JSON (REST API)",
        variables_used=(
            "temperature_2m",
            "dew_point_2m",
            "precipitation",
            "wind_speed_10m",
            "wind_direction_10m",
        ),
        license="Copernicus/ECMWF open licence (via Open-Meteo, free non-commercial/research use, attribution required)",
        citation="Hersbach, H. et al. (2020): ERA5 hourly data, Copernicus Climate Change Service (C3S) Climate Data Store; served via open-meteo.com",
        retrieval_method="HTTPS GET, JSON REST API (no auth), models=era5 always passed explicitly — used because direct "
        "Copernicus CDS access requires registered API credentials not available in this environment",
        retrieval_date="2026-08-19",
        local_file_hash=None,
        scientific_role="primary historical weather covariates: pre-t0-only mean temperature, mean relative humidity "
        "[derived], precipitation accumulation, and mean_u10/mean_v10 [derived from PAIRED HOURLY speed+direction, "
        "never daily-max-speed + dominant-direction]",
        temporal_role="HISTORICAL_REANALYSIS",
        known_limitations=(
            "reanalysis, not a live operational forecast; per-query sub-classified as "
            "RETROSPECTIVE_REANALYSIS_STATE_PROXY or REALIZED_FUTURE_REANALYSIS (see weather/base.py) — no forecast "
            "archive exists in this pipeline, so future weather relative to any t0 is never fabricated; "
            "REALIZED_FUTURE_REANALYSIS is gated off by default and only for clearly-labeled retrospective/oracle "
            "analysis, never primary deployable validation; 0.25 degree resolution is coarser than "
            "ERA5-Land/IFS/CERRA, accepted as the tradeoff for a single, temporally-consistent, variable-complete "
            "model; date-only t0 uses a timezone-resolved (AOI's real IANA timezone, zoneinfo, historically-correct "
            "offset), strict pre-local-midnight-UTC cutoff, never an unconditional UTC midnight and never a full "
            "t0-calendar-day (Checkpoint 5.6); RETROSPECTIVE_REANALYSIS_STATE_PROXY answers only whether a value's "
            "meteorological valid_time was pre-t0 — it is NOT a claim the value was operationally available by t0 "
            "(availability_quality is a separate, UNKNOWN-by-default field; see ENVIRONMENTAL_FEATURE_PROTOCOL.md)"
        ),
        status="REAL",
    ),
    GisSourceEntry(
        dataset_name="HydroRIVERS v1.0 (HydroSHEDS)",
        provider="HydroSHEDS (WWF / McGill University / consortium)",
        official_source="https://data.hydrosheds.org (continental shapefile distributions)",
        dataset_version="v1.0",
        reference_year_or_temporal_coverage="static hydrography (no single reference year; derived from SRTM-era elevation)",
        spatial_resolution="vector (reach-level, derived from ~90m/15m source DEMs)",
        native_crs="EPSG:4326",
        file_format="ESRI Shapefile (zipped)",
        variables_used=("river_reach_geometry",),
        license="Free for scientific, educational and non-commercial use per the HydroSHEDS Data License Agreement",
        citation="Lehner, B., Grill G. (2013): Global river hydrography and network routing, Hydrological Processes, 27(15): 2171-2186, doi:10.1002/hyp.9740",
        retrieval_method="HTTP GET (range-request capable), continental zip cached locally, bbox-filtered read via geopandas",
        retrieval_date="2026-08-18",
        local_file_hash="HydroRIVERS_v10_as_shp.zip(sha256)=29780b0a75f90024f22e7e2029e5e3045f7325cda0528db65c5cc4c864b98525",
        scientific_role="distance-to-nearest-river covariate (vector/fomite pathway plausibility)",
        temporal_role="STATIC_REFERENCE_PROXY",
        known_limitations=(
            "only the Asia ('as') continental file is integrated in this checkpoint (both smoke AOIs fall within "
            "it); an AOI outside Asia returns BLOCKED, never a wrong-continent or fabricated distance; "
            "non-commercial license restricts downstream use"
        ),
        status="REAL",
    ),
    GisSourceEntry(
        dataset_name="HydroLAKES (HydroSHEDS)",
        provider="HydroSHEDS (WWF / McGill University / consortium)",
        official_source="https://www.hydrosheds.org/products/hydrolakes",
        dataset_version="v1.0",
        reference_year_or_temporal_coverage="static hydrography",
        spatial_resolution="vector (lake polygons)",
        native_crs="EPSG:4326",
        file_format="ESRI Shapefile / Geodatabase (single global file)",
        variables_used=(),
        license="Free for scientific, educational and non-commercial use per the HydroSHEDS Data License Agreement",
        citation="Messager, M.L., Lehner, B., Grill, G., Nedeva, I., Schmitt, O. (2016): Estimating the volume and age of water stored in global lakes, Nature Communications, doi:10.1038/ncomms13603",
        retrieval_method="not retrieved in this checkpoint",
        retrieval_date="n/a",
        local_file_hash=None,
        scientific_role="distance-to-nearest-lake covariate (not yet integrated)",
        temporal_role="UNKNOWN",
        known_limitations="deferred: ships as a single global file, exceeding this checkpoint's smoke-test scope (master-prompt Part 3)",
        status="BLOCKED",
    ),
    GisSourceEntry(
        dataset_name="NASADEM",
        provider="NASA JPL",
        official_source="https://www.earthdata.nasa.gov (requires Earthdata Login)",
        dataset_version="NASADEM_HGT v001",
        reference_year_or_temporal_coverage="2000 (SRTM-era acquisition, NASADEM reprocessing released 2020)",
        spatial_resolution="~30m (1 arc-second)",
        native_crs="EPSG:4326",
        file_format="GeoTIFF / HGT",
        variables_used=(),
        license="NASA Earthdata (free, requires registered account)",
        citation="NASA JPL (2020): NASADEM Merged DEM Global 1 arc second, doi:10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001",
        retrieval_method="not retrieved: requires NASA Earthdata Login credentials not available in this environment",
        retrieval_date="n/a",
        local_file_hash=None,
        scientific_role="elevation covariate (not selected)",
        temporal_role="UNKNOWN",
        known_limitations="auth wall (Earthdata Login) — real access could not be verified in this environment; see AWS Terrain Tiles for the real, honestly-labeled alternative actually used",
        status="BLOCKED",
    ),
    GisSourceEntry(
        dataset_name='AWS "Terrain Tiles" (elevation-tiles-prod, Terrarium encoding)',
        provider="Amazon Web Services Open Data / Mapzen (original curator, now archived)",
        official_source="https://registry.opendata.aws/terrain-tiles/ (bucket: elevation-tiles-prod)",
        dataset_version="Terrarium PNG encoding, mosaic of SRTM/NED/EU-DEM and other public DEMs",
        reference_year_or_temporal_coverage="mosaic of multiple source DEMs, no single reference year",
        spatial_resolution="zoom-dependent slippy tile (~38m/pixel at zoom 12 near the equator)",
        native_crs="Web Mercator tile grid (EPSG:3857), decoded per-pixel at query lat/lon in EPSG:4326",
        file_format="PNG (Terrarium RGB elevation encoding)",
        variables_used=("elevation_m",),
        license="Public domain / mixed (per constituent source datasets; see AWS Open Data Registry)",
        citation="AWS Open Data Registry: 'Terrain Tiles', https://registry.opendata.aws/terrain-tiles/",
        retrieval_method="windowed HTTP GET via GDAL /vsicurl/ (rasterio), single pixel per query, not a bulk download",
        retrieval_date="2026-08-18",
        local_file_hash=None,
        scientific_role="elevation covariate; retrieval verified, NOT yet selected as a PISTES input",
        temporal_role="STATIC_REFERENCE_PROXY",
        known_limitations=(
            "explicitly NOT NASADEM (a different, mixed-source dataset) — used only because NASADEM's real Earthdata "
            "Login access could not be completed in this environment; slope is not computed (would need a "
            "multi-pixel, meter-based gradient, out of scope for this single-point smoke extraction)"
        ),
        status="AVAILABLE_NOT_YET_SELECTED",
    ),
)
