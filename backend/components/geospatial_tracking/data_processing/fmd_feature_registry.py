"""FMD-04: machine-readable + human-readable source-validation registry for
the FMD environmental/host-context feature layer.

Mirrors `services/geospatial/source_registry.py`'s `GisSourceEntry` contract
exactly (reused, not re-defined) so this registry is directly comparable to
the existing LSD-facing GIS source registry — same fields, same discipline
("REAL"/"AVAILABLE_NOT_YET_SELECTED"/"UNAVAILABLE"/"BLOCKED", never a
fabricated entry for an integration that does not exist).

**This file documents CANDIDATE feature families, not permission to
fabricate an integration** (FMD-04 Step 3). Every entry below was verified
against actual repository code before being marked `REAL` — see
`build_fmd_features.py` for the orchestration that calls these adapters,
and `FMD_FEATURE_AUDIT.md` (generated) for the real extraction results.

FMD-specific findings vs. the existing (LSD-facing) registry:

- **Host density is species-limited to cattle/buffalo only** (`services/
  geospatial/host_density/fao_glw.py`'s `GLW_SPECIES`). FMD is multi-host
  (cattle, buffalo, swine, sheep, goat all susceptible) — swine/sheep/goat
  density has NO validated adapter in this repository. Marked
  `UNAVAILABLE` below, never fabricated from the two available species.
- **HydroRIVERS covers Asia ("as" region) only.** The existing LSD registry
  entry notes this as a minor caveat (both LSD smoke AOIs are in Asia); for
  FMD it is a MATERIAL limitation — the real FMD corpus spans 96 countries,
  most of them outside HydroRIVERS' "as" coverage (`FMD_HYDROLOGY_ASIA_BBOX`
  in `build_fmd_features.py`). Every non-Asia event is classified
  `OUTSIDE_SOURCE_COVERAGE`, not silently skipped or BLOCKED.
- **No road-density/OSM/livestock-movement-proxy adapter exists anywhere in
  this repository** (verified by direct grep across `geospatial_tracking`
  before writing this entry). Marked `UNAVAILABLE` — not a stub, not
  attempted, no placeholder value.
"""

from __future__ import annotations

from ..services.geospatial.source_registry import GisSourceEntry

FMD_FEATURE_SOURCE_REGISTRY: tuple[GisSourceEntry, ...] = (
    GisSourceEntry(
        dataset_name="ERA5 reanalysis (via Open-Meteo Historical Weather API, intermediary)",
        provider="ECMWF / Copernicus Climate Change Service (C3S, original reanalysis); Open-Meteo (intermediary API, not the data producer)",
        official_source="https://archive-api.open-meteo.com/v1/archive (models=era5 always explicit — see services/geospatial/weather/era5.py)",
        dataset_version="ERA5 (models=era5) — single fixed-version reanalysis, never the unset best_match default",
        reference_year_or_temporal_coverage="1940-present, hourly — fully covers the FMD corpus's real 2002-04-29..2026-08-09 date range",
        spatial_resolution="0.25 degrees (~25km at equator) — ERA5's native reanalysis grid",
        native_crs="EPSG:4326",
        file_format="JSON (REST API)",
        variables_used=("temperature_2m", "dew_point_2m", "precipitation", "wind_speed_10m", "wind_direction_10m"),
        license="Copernicus/ECMWF open licence (via Open-Meteo, free non-commercial/research use, attribution required)",
        citation="Hersbach, H. et al. (2020): ERA5 hourly data, Copernicus Climate Change Service (C3S) Climate Data Store; served via open-meteo.com",
        retrieval_method="HTTPS GET, JSON REST API (no auth), models=era5 always explicit; cached per-request under local_data/cache/weather/ (shared cache dir, key derived from exact request params, safe across diseases)",
        retrieval_date="2026-08-23",
        local_file_hash=None,
        scientific_role=(
            "FMD environmental covariates (NOT a vector-transmission field — FMD is not vector-borne; "
            "weather here is an epidemiological covariate only): mean_temperature_2m, mean_relative_humidity_2m "
            "[derived], precipitation_accumulation, mean_u10/mean_v10/mean_wind_speed/vector_resultant_speed/"
            "directional_persistence [wind, from PAIRED HOURLY speed+direction — never averaged compass degrees], "
            "computed for 4 candidate pre-t0 windows: event_day (24h), 3day (72h), 7day (168h), 14day (336h)"
        ),
        temporal_role="HISTORICAL_REANALYSIS",
        known_limitations=(
            "reanalysis, not a live operational forecast; pre-t0-only (RETROSPECTIVE_REANALYSIS_STATE_PROXY), "
            "availability_quality=UNKNOWN by default (valid-time safety only, not a claim of real-time operational "
            "availability); 0.25 degree resolution; window sizes (24/72/168/336h) are candidate/UNFROZEN_DEVELOPMENT_PARAMETER "
            "choices, not selected/optimized against any outcome in FMD-04"
        ),
        status="REAL",
    ),
    GisSourceEntry(
        dataset_name='AWS "Terrain Tiles" (elevation-tiles-prod, Terrarium encoding)',
        provider="Amazon Web Services Open Data / Mapzen (original curator, now archived)",
        official_source="https://registry.opendata.aws/terrain-tiles/ (bucket: elevation-tiles-prod)",
        dataset_version="Terrarium PNG encoding, mosaic of SRTM/NED/EU-DEM and other public DEMs",
        reference_year_or_temporal_coverage="mosaic of multiple source DEMs, no single reference year (static)",
        spatial_resolution="zoom-dependent slippy tile (~38m/pixel at zoom 12 near the equator)",
        native_crs="Web Mercator tile grid (EPSG:3857), decoded per-pixel at query lat/lon in EPSG:4326",
        file_format="PNG (Terrarium RGB elevation encoding)",
        variables_used=("elevation_m",),
        license="Public domain / mixed (per constituent source datasets; see AWS Open Data Registry)",
        citation="AWS Open Data Registry: 'Terrain Tiles', https://registry.opendata.aws/terrain-tiles/",
        retrieval_method="windowed HTTP GET via GDAL /vsicurl/ (rasterio), single pixel per query, not a bulk download; global coverage, no pre-check needed",
        retrieval_date="2026-08-23",
        local_file_hash=None,
        scientific_role="terrain covariate: point elevation (m) at the event's own coordinates. NOT NASADEM (see services/geospatial/elevation/nasadem.py — real NASADEM requires an Earthdata Login unavailable in this environment)",
        temporal_role="STATIC_REFERENCE_PROXY",
        known_limitations="slope/aspect NOT computed (would need a real multi-pixel, meter-based gradient — out of scope; never approximated from raw degrees)",
        status="REAL",
    ),
    GisSourceEntry(
        dataset_name="FAO Gridded Livestock of the World (GLW4), Da product — cattle",
        provider="FAO / Fondation Bill & Melinda Gates / Univ. Liverpool (GLW4 consortium)",
        official_source="https://dataverse.harvard.edu (dataverse 'glw', GLW4 sub-dataverse)",
        dataset_version="GLW4 Da (dasymetric)",
        reference_year_or_temporal_coverage="2015 (verified from source metadata; not current)",
        spatial_resolution="0.083333 decimal degrees (~10km at equator)",
        native_crs="EPSG:4326",
        file_format="GeoTIFF",
        variables_used=("cattle_count_per_pixel", "pixel_area_km2"),
        license="CC0 1.0 (per Dataverse dataset metadata)",
        citation="doi:10.7910/DVN/LHBICE 'Global cattle distribution in 2015'",
        retrieval_method="HTTP GET via Dataverse access API (303 redirect to presigned S3 URL), cached locally under local_data/gis/glw/ (shared cache — same files LSD already uses)",
        retrieval_date="2026-08-23",
        local_file_hash="5_Ct_2015_Da.tif (cached locally; see GIS_DATA_SOURCES.md for hash)",
        scientific_role="host-density covariate: cattle_density_animals_per_km2, area-weighted AOI-window extraction (half_extent_km=10.0, matched to GLW4's own ~10km source resolution — see build_fmd_features.py FmdFeatureExtractionConfig)",
        temporal_role="STATIC_REFERENCE_PROXY",
        known_limitations=(
            "reference year 2015, not current; AOI-window (not grid-cell-overlap) extraction is used here since FMD-04 "
            "builds no spatial grid (that belongs to a later checkpoint) — the module's own documented sensitivity to "
            "half_extent_km choice applies; a fixed, documented, non-outcome-tuned half_extent_km=10.0 is used for "
            "every event, never varied per-event"
        ),
        status="REAL",
    ),
    GisSourceEntry(
        dataset_name="FAO Gridded Livestock of the World (GLW4), Da product — buffalo",
        provider="FAO / Fondation Bill & Melinda Gates / Univ. Liverpool (GLW4 consortium)",
        official_source="https://dataverse.harvard.edu (dataverse 'glw', GLW4 sub-dataverse)",
        dataset_version="GLW4 Da (dasymetric)",
        reference_year_or_temporal_coverage="2015 (verified from source metadata; not current)",
        spatial_resolution="0.083333 decimal degrees (~10km at equator)",
        native_crs="EPSG:4326",
        file_format="GeoTIFF",
        variables_used=("buffalo_count_per_pixel", "pixel_area_km2"),
        license="CC0 1.0 (per Dataverse dataset metadata)",
        citation="doi:10.7910/DVN/I1WCAB 'Global buffaloes distribution in 2015'",
        retrieval_method="HTTP GET via Dataverse access API (303 redirect to presigned S3 URL), cached locally under local_data/gis/glw/",
        retrieval_date="2026-08-23",
        local_file_hash="5_Bf_2015_Da.tif (cached locally; see GIS_DATA_SOURCES.md for hash)",
        scientific_role="host-density covariate: buffalo_density_animals_per_km2, same extraction method as cattle",
        temporal_role="STATIC_REFERENCE_PROXY",
        known_limitations="reference year 2015, not current; same half_extent_km sensitivity caveat as cattle",
        status="REAL",
    ),
    GisSourceEntry(
        dataset_name="FAO GLW4 swine/sheep/goat density — NOT INTEGRATED",
        provider="FAO / GLW4 consortium (product exists; this repository does not consume it)",
        official_source="https://dataverse.harvard.edu (GLW4 sub-dataverse publishes Pigs/Sheep/Goats products, e.g. doi:10.7910/DVN/5U0MDS and siblings)",
        dataset_version="n/a — not retrieved",
        reference_year_or_temporal_coverage="n/a",
        spatial_resolution="n/a",
        native_crs="n/a",
        file_format="n/a",
        variables_used=(),
        license="n/a",
        citation="n/a — not retrieved this checkpoint",
        retrieval_method="not attempted: `services/geospatial/host_density/fao_glw.py`'s `GLW_SPECIES` dict only wires cattle and buffalo; extending it (new species entries, new local raster downloads) is real, feasible future work, not attempted in FMD-04",
        retrieval_date="n/a",
        local_file_hash=None,
        scientific_role="swine/sheep/goat host-density — FMD is multi-host and these ARE epidemiologically relevant, but no validated local integration exists",
        temporal_role="UNKNOWN",
        known_limitations="single biggest host-context gap for FMD-04 — see FMD_FEATURE_AUDIT.md 'Scientific Limitations'",
        status="UNAVAILABLE",
    ),
    GisSourceEntry(
        dataset_name="ESA WorldCover",
        provider="European Space Agency (ESA) / VITO / consortium",
        official_source="https://esa-worldcover.org (public COG tiles: esa-worldcover.s3.eu-central-1.amazonaws.com)",
        dataset_version="v100 (2020) and v200 (2021) — both present, never mixed silently",
        reference_year_or_temporal_coverage="2020 (v100) or 2021 (v200) — the FMD corpus spans 2002-2026, so almost every event falls outside WorldCover's own 2 covered years",
        spatial_resolution="10m",
        native_crs="EPSG:4326",
        file_format="Cloud-Optimized GeoTIFF (COG)",
        variables_used=("land_cover_class",),
        license="CC BY 4.0",
        citation="Zanaga et al. (2021/2022), ESA WorldCover 10 m v100/v200, doi:10.5281/zenodo.5571936 (v100) / 10.5281/zenodo.7254221 (v200)",
        retrieval_method="windowed HTTP GET via GDAL /vsicurl/ (rasterio), no full-tile download, no app-level cache (live S3 read every call)",
        retrieval_date="2026-08-23",
        local_file_hash="not cached as a static file — windowed vsicurl reads only",
        scientific_role="contextual land-cover covariate (per-class pixel-count area fraction), half_extent_km=10.0",
        temporal_role="STATIC_REFERENCE_PROXY (YEAR_MATCHED_REFERENCE only for the small subset of FMD events actually dated 2020/2021)",
        known_limitations=(
            "only 2 single-year snapshots exist; for a corpus spanning 24 years, the overwhelming majority of events "
            "get STATIC_REFERENCE_PROXY, not a genuine time-matched land-cover observation — this is reported "
            "explicitly per event (temporal_role), never silently presented as time-matched"
        ),
        status="REAL",
    ),
    GisSourceEntry(
        dataset_name="HydroRIVERS v1.0 (HydroSHEDS)",
        provider="HydroSHEDS (WWF / McGill University / consortium)",
        official_source="https://data.hydrosheds.org (continental shapefile distributions)",
        dataset_version="v1.0",
        reference_year_or_temporal_coverage="static hydrography (no single reference year)",
        spatial_resolution="vector (reach-level, derived from ~90m/15m source DEMs)",
        native_crs="EPSG:4326",
        file_format="ESRI Shapefile (zipped)",
        variables_used=("river_reach_geometry",),
        license="Free for scientific, educational and non-commercial use per the HydroSHEDS Data License Agreement",
        citation="Lehner, B., Grill G. (2013): Global river hydrography and network routing, Hydrological Processes, 27(15): 2171-2186, doi:10.1002/hyp.9740",
        retrieval_method="HTTP GET (range-request capable), continental zip cached locally under local_data/gis/hydrosheds/ (shared cache), bbox-filtered read via geopandas",
        retrieval_date="2026-08-23",
        local_file_hash="HydroRIVERS_v10_as_shp.zip (cached locally; see GIS_DATA_SOURCES.md for hash)",
        scientific_role="distance-to-nearest-river covariate (proxy context only, never described as a transmission vector)",
        temporal_role="STATIC_REFERENCE_PROXY",
        known_limitations=(
            "ONLY the Asia ('as') continental region is integrated. The real FMD corpus spans 96 countries "
            "globally (dominated by South Africa, Algeria, Zimbabwe, Israel, Republic of Korea, per "
            "FMD_DATA_AUDIT.md) — an event whose coordinates fall outside a documented Asia bounding box "
            "(build_fmd_features.FMD_HYDROLOGY_ASIA_BBOX) is classified OUTSIDE_SOURCE_COVERAGE and never "
            "queried against the wrong continent's rivers or given a fabricated distance. This is a MATERIAL "
            "coverage gap for FMD, unlike for LSD's Sri Lanka/Thailand-scoped smoke AOIs"
        ),
        status="REAL",
    ),
    GisSourceEntry(
        dataset_name="Road network / OSM / livestock-movement proxy — NOT INTEGRATED",
        provider="n/a",
        official_source="n/a",
        dataset_version="n/a",
        reference_year_or_temporal_coverage="n/a",
        spatial_resolution="n/a",
        native_crs="n/a",
        file_format="n/a",
        variables_used=(),
        license="n/a",
        citation="n/a",
        retrieval_method=(
            "not attempted: verified by direct grep across the whole geospatial_tracking component (`road`, `osm`, "
            "`OSMnx`, `movement`, `proximity`, `distance_to_road`) that no road-network/OSM adapter exists anywhere "
            "in this repository; `osmnx` is not in backend/requirements.txt; no cached road data exists under "
            "local_data/"
        ),
        retrieval_date="n/a",
        local_file_hash=None,
        scientific_role="anthropogenic/movement-context proxy (road density, distance-to-transport-network) — would need to remain explicitly labeled a PROXY, never a direct livestock-movement measurement, per FMD-04's own instructions",
        temporal_role="UNKNOWN",
        known_limitations="genuine gap — no source exists to validate; not fabricated",
        status="UNAVAILABLE",
    ),
)
