# Integration plan: improvmnet-all into bugfix/improved

Prepared on 16 October 2026. Status: implemented and validated; integrated into `bugfix/improved` with a merge commit.

## Verified branch history

| Item | Commit / result |
| --- | --- |
| Target branch | `bugfix/improved` at `8d209c5755c83397010c87aa0157c7ca1486518e` |
| Incoming branch | `improvmnet-all` at `6ce9f8df78729e97704dc3bab9bafb216cd6797e` |
| Common ancestor | `8a778207d3f892534a7efdd898c5a9ff04803f31` (`main`) |
| Unique commits | 84 target; 8 incoming |
| Remote verification | Both branch tips matched GitHub during analysis |
| Working tree | No reported changes before analysis |

Reviewed the history and changes on both sides of the common ancestor. The incoming commits are:

| Commit | Subject | Main contribution |
| --- | --- | --- |
| `3a96360` | location bug fixed | Farm profile/location persistence; frontend dependency change |
| `6d5bed2` | 7 day output developed | Wellness status presentation, herd registry and shared vet screens |
| `4d24419` | suggested automation done | Bulk intake, monitoring automation and triage workflow |
| `e8d4111` | bug fixed | Intake validation and backend adjustments |
| `3da17b2` | ui updated | Animal profile and intake presentation |
| `7db765c` | csv bug fix | CSV parsing/import and date handling |
| `7c016e1` | bug fixed | Seven-day triage and backend adjustments |
| `6ce9f8d` | model input errors fixed | Scaler-based model inputs, BCS/animal screens |

The target branch includes forecasting v2, stored forecast presentation, seasonal outlooks, severity presentation, advisory/follow-up workflows, and grounded diagnosis/severity and case-access controls. These remain preservation requirements.

## Merge simulation

Ran Git's actual merge algorithm using a temporary object store, without changing the index, branch, or working tree. Result: **zero Git conflicts**.

The simulated result changes 44 paths relative to the target: 20 tracked `node_modules` paths and 24 other paths, including `.DS_Store`. Model-pointer conversions shared by both branches produce no additional forecasting changes.

The simulation leaves these areas unchanged:

- `frontend/src/features/RiskForecasting/`, including `DaphDistrictForecasts.jsx`.
- `backend/components/risk_forecasting/`.
- The frontend and backend core Smart Diagnostics directories.
- The frontend and backend geospatial directories.

Shared overlaps are `health_anomaly/router.py`, `health_anomaly/schemas.py`, `FarmerSmartDiagnostics.jsx`, and `VetDashboard.jsx`. An AST comparison confirms all eight target-specific router function changes survive unchanged, including case authorization and notification handling. None of those functions also changed in the incoming branch. This is structural evidence; runtime compatibility still needs testing.

## Integration decisions and risks

| Area | Finding | Planned treatment |
| --- | --- | --- |
| CSV duplicates | Incoming bulk import deletes and replaces existing cattle/date records before inference. | User confirmed automatic replacement of matching cattle/date records, preserving the behavior of `improvmnet-all`. No duplicate-specific confirmation step. Validate replacements before applying them and keep imports scoped to the authenticated farm. |
| Farm isolation | Bulk import accepts missing/invalid authentication, can fall back to all farms, and can resolve an object ID outside the farm-scoped lookup. | Enforce the appropriate authenticated farm scope consistently; test duplicate identifiers across farms and unauthorized IDs. |
| Animal lifecycle | New bulk and seven-day prediction updates write both `status` and `health_status` without a deceased guard. | Preserve deceased state and prevent automated monitoring from reviving animals or clearing protected lifecycle state. |
| Historical imports | Status/weight updates use the latest imported row, which can be older than an existing stored row. | Derive current animal state from the latest eligible stored record; test historical backfills. |
| Dates | Incoming date normalizers assume month-first slash dates and can construct invalid dates without calendar validation. | Check frontend/backend agreement and existing data conventions; reject invalid dates and resolve ambiguous formats explicitly. |
| API compatibility | Bulk response changes from `count` to `inserted_count` plus inference summaries; authentication and payload handling also change. | Review every caller and preserve required response compatibility while adding the new summary fields. |
| Inference failure | Replacement/insertion happens before model inference; a failure can return 500 after data has already changed. | Make partial outcomes explicit and retry behavior safe; avoid deleting valid records before validation. |
| Model assets | New `late_fusion_scalers.pkl` is an LFS pointer; its 9,970-byte object is not cached locally. | Retrieve the object, verify its hash, and check scaler keys, feature ordering and model input shapes. Existing late-fusion and monitoring model objects are cached. |
| Dependencies | Incoming React Vite plugin changes from `^5.0.0` to `^4.7.0`; both declare compatibility with the repository's Vite 5. | Validate the incoming manifest/lockfile pair with a clean install and production build. Do not infer correctness from tracked dependency files. |
| Generated files | Incoming commits include tracked dependency files, Vite caches and `.DS_Store`. | Preserve the target versions of these files in the integration commit; use an isolated install for validation. Defer repository-wide generated-file cleanup. |
| Location persistence | Login/profile now cache farm coordinates and district in browser storage. | Verify saving, reloading and switching between accounts, including a farm with no location. Prevent stale coordinates from crossing accounts. |

## Execution plan

1. **Protect the starting point.** Recheck both tips and working-tree status. Create a backup ref at the target commit and prepare the integration in an isolated checkout. Keep the merge uncommitted while reviewing the combined result. Use a merge commit so both histories remain traceable.

2. **Establish the validation baseline.** Record the existing failures listed below. Check whether failures come from test setup, fixtures or application behavior, and keep any necessary corrections separately identifiable. Preserve current navigation, diagnosis access rules and forecasting behavior.

3. **Integrate the incoming features.** Merge the eight incoming commits together, retain both sides of the shared-file changes, and exclude incidental dependency/cache/OS-file changes from the final integration diff. Preserve the incoming registry, intake, location, BCS, seven-day triage and richer wellness status features.

4. **Resolve behavioral integration issues.** Automatically replace matching cattle/date records, as confirmed by the user. Add farm-scoping and lifecycle guards, protect current state during historical imports, verify date/API contracts, and handle missing assets and inference failures clearly. Ask about any additional incompatible product behavior discovered during implementation.

5. **Verify the combined application.** Run all frontend tests, the three incoming wellness suites, forecasting and diagnosis backend suites, and relevant geospatial/integration tests. Add focused backend regressions for the new bulk importer and model-input contracts. Build the frontend from a clean dependency install. Smoke-test farmer, vet and DAPH routes, diagnosis submission/review, wellness alerts, CSV imports, triage, location persistence, stored forecasts, seasonal outlooks, advisories and follow-ups. Use isolated database fakes/fixtures for automated writes.

6. **Complete the merge.** Review the final diff against the backup and incoming branch. Confirm both histories are retained, all intended incoming features are present, existing features remain usable, model assets resolve, and no new failures remain. Complete the merge on `bugfix/improved` and report exact validation results and any remaining pre-existing limitations.

## Baseline validation already performed

- Full frontend run: **138 suites passed, 2 failed; 1,990 tests passed, 1 failed; 1 unhandled error**. This was the unchanged target branch, before merging.
- A targeted rerun reproduced the existing problems:
  - `App.test.jsx`: `window.URL.createObjectURL` is missing in the test environment.
  - `RoleBasedNavigation.test.jsx`: farmer navigation expectation fails.
  - `DaphFollowUpComposer.test.jsx`: unhandled access to `issuedFollowUps.length` when the value is undefined.
- Selected backend baseline: **51 tests passed** across case access, grounded reasoning and vet identity schemas.
- The backend virtual environment lacks pytest; the successful baseline used the available system Python.
- The first sandboxed frontend attempt could not resolve the OneDrive workspace. Running the same tests with approved expanded access succeeded in starting and produced the results above.

The baseline above was recorded before implementation. The execution results below supersede the planning status.


## Integration results

Implemented all eight incoming commits together, preserving both branch histories. Recovery reference: `backup/bugfix-improved-before-improvmnet-all-20261016` at `8d209c5`.

- CSV imports automatically replace matching cattle/date records, as requested. Replacement preserves record IDs, validates and evaluates the entire batch before writing, and supports safe retries. Repeated keys in one CSV use the last row. The legacy `count` response field remains available alongside the incoming summaries.
- Farm-scoped lookup prevents unknown/foreign IDs and duplicate tags in other farms from resolving outside the authenticated farm. Listing daily logs also requires authentication and never falls back to other farms.
- Monitoring preserves deceased animals. Seven-day status writes require farm ownership; its frontend caller now sends authentication. Male/deceased CSV rows are skipped with a count.
- Historical imports evaluate the latest stored day rather than regressing current weight/status to the latest imported day. The monitoring date does not move backwards.
- Frontend/backend date parsing agrees on year-first dates and month-first CSV dates, with real calendar validation. Invalid dates do not silently roll over.
- Responses retain optional sensor readings and the cattle monitoring date needed by the incoming registry and triage screens.
- Login/profile hydration clears missing cached location values so accounts do not inherit the previous farm's coordinates.
- Downloaded the new scaler and verified SHA-256 `137b70171d3d7cd10855c1814596096c212f4e329882c742999d7d5d9ed26ad3`.
- Kept the incoming frontend manifest/lockfile dependency pairing; excluded incidental tracked dependency/cache/OS-file changes. Declared the directly imported backend `joblib` dependency.
- Fixed existing frontend validation issues through browser URL test stubs, current navigation expectations, and isolated/complete advisory and follow-up test fixtures. Forecasting application source remains unchanged.
- AST verification confirms all eight target-specific diagnosis router function changes remain unchanged. Core diagnosis, forecasting and geospatial application directories remain unchanged.

## Final validation

| Check | Result |
| --- | --- |
| Clean frontend dependency installation | Passed (`npm ci`) |
| Full frontend suite | 144 files; 2,024 tests passed; no unhandled errors |
| Core backend: forecasting, diagnosis, wellness, vet identity schemas | 644 passed, including 24 new monitoring integration tests |
| Geospatial parsing, schemas, repositories, runtime routers and event sources | 119 passed |
| Production frontend build | Passed; existing large-bundle warning |
| Real persistent-monitoring model inference | Passed on synthetic inputs, without database writes |
| Real seven-day model/scaler inference | Passed; inputs `(1, 7, 8)`, `(1, 45)`, `(1, 1)`; finite three-class probabilities |
| Browser smoke checks with isolated API fixtures | Farmer login, registry, intake, triage and diagnosis; vet dashboard, diagnosis and forecasting; DAPH national/district forecasts and follow-up monitoring rendered without captured browser errors |
| Preservation review | Both histories retained; protected diagnosis functions unchanged; preserved component application source unchanged |

Backend checks used an isolated Python environment with the missing `pytest-asyncio` and `geopandas` validation dependencies. A fresh `--basetemp` resolved Windows permission errors affecting the default pytest temporary directory. No changes to the user's existing Python environment were required.

Full geospatial scientific validation remains incomplete: the checkout has no root `local_data` research datasets or populated historical SQLite database. The initial broad backend attempt reported 2,727 passed, 193 failed, 153 skipped and 322 errors, including temporary-directory permission failures and absent research artifacts/tables. The core suites were then rerun successfully with a writable temporary directory, and the independent geospatial runtime selection passed. The full research suite was not rerun without its required data. No geospatial application source changes were made.

The existing model artifacts were trained with scikit-learn 1.6.1; local validation used 1.8.0 and emitted version warnings, although both real wellness inference checks passed. Browser smoke checks used isolated read fixtures; no live-database end-to-end writes or deployment were performed.
