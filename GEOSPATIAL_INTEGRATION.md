# Geospatial integration into bugfix/improved

Integration date: 18 October 2026. Local merge; no remote push.

## History reviewed

| Reference | Commit |
| --- | --- |
| Target `bugfix/improved` before integration | `712388620a4f32969c81b9bccf388878a36f203d` |
| Incoming `origin/feature/geospatial-fix-final` | `7663ebf9f846447a717656f9c35e85ba14ae5aa3` |
| Common ancestor | `8a778207d3f892534a7efdd898c5a9ff04803f31` |
| Recovery branch | `backup/bugfix-improved-before-geospatial-20261018` |

Fetched origin before comparing histories: 94 commits unique to the target and 20 unique to the incoming branch. The target contains forecasting, diagnosis/severity and wellness updates. The incoming commits supply MongoDB-backed geospatial sources, Asia/Colombo dates, live case-change events, district surveillance, spatial timelines/clustering, risk rasters, map/weather presentation, My Area, analysis and GPS persistence.

Only two paths changed on both sides: `backend/main.py` and `frontend/src/features/HealthAnomaly/screens/SettingsFarmConfiguration.jsx`.

## Conflict resolution

`backend/main.py` merged automatically. It retains the target's `LesionSegmenter` configuration while adding the incoming spatial timeline router, historical-source reader and optional schema-initialization skip.

Farm settings had four conflicting regions: GPS selection, map confirmation, profile hydration and coordinates used during profile saving. The user selected **Combine both approaches as recommended**.

- The loaded farm profile supplies coordinates and district; browser storage mirrors that profile and successful location saves. Profile updates never recover coordinates from browser storage.
- GPS selections and confirmed map/search selections save immediately, check the HTTP response, and update the displayed/cached location after a successful save. Failed writes retain the previous saved location.
- District and formatted location remain separate: for example, `location_district: "Galle District"` and `location: "6.0500, 80.2200 (Galle District)"`.
- Legacy coordinate labels remain readable; missing coordinates clear stale cached GPS values. The existing shared wellness cache helper handles every location cache field.
- District lookup failures retain usable GPS with an explicit `Unknown District` label. Selections outside Sri Lanka are rejected.

Added eight farm settings regression tests covering profile saves, cache contamination, missing GPS, legacy labels, immediate GPS persistence/reloading, HTTP/network failures, map search confirmation and geocoder failure.

Core forecasting, diagnosis and wellness backend source, forecasting frontend source and core diagnosis frontend source remain unchanged. Apart from farm settings, the backend entry point and Vite's incoming proxy change, application changes belong to the geospatial component. Removed one incoming blank line at the end of a stylesheet for a clean whitespace check.

## Validation

| Check | Result |
| --- | --- |
| Full frontend suite | 197 files, 2,549 tests passed |
| Farm settings integration tests | 8 passed, included above |
| Geospatial frontend suite | 122 files, 1,477 tests passed, also included above |
| Core backend plus operational/router integration | 755 passed |
| Spatial timeline, host authorization, sources, events, dynamic cases, district surveillance and related backend checks | 174 passed, 2 failed |
| Production frontend build | Passed; large-bundle warning |
| Whitespace/conflict-marker review | Passed |

Backend tests used an isolated validation environment, fixture collections, an unreachable local MongoDB URL, `GEOSPATIAL_SKIP_SCHEMA_INIT=1`, and live-database tests disabled. No live database writes or deployment were performed. Existing model-version and deprecation warnings remain. Frontend tests emit jsdom WebGL fallback and React test warnings while passing.

## Incoming branch limitations

Both failures below reproduce with identical values against an isolated archive of the **unmerged incoming branch** in the same environment. Geospatial scientific code was preserved.

1. `test_spatial_timeline.py::test_every_case_gets_a_daily_heading_from_land_cattle_net_wind_and_nearby_cases`: expects FAO GLW4 cattle-density data, which is absent locally; the engine reports `UNAVAILABLE`.
2. `test_spatial_timeline.py::test_risk_field_grows_day_by_day_in_the_spread_direction_not_behind_it`: expects an ahead/behind risk ratio greater than 3; observed approximately 2.925 (`0.3231976189527753 / 0.11050058907599647`).

The full geospatial research suite requiring external datasets was not run. Live MongoDB end-to-end behavior and GPU/browser WebGL rendering were not validated by these automated checks.
