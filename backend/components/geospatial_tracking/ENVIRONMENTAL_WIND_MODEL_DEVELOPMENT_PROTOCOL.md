# Checkpoint 7C — Environmental / Wind-Anisotropic Model Development Protocol

## 1. Purpose

7C asks one question: **does scientifically defensible t0-available
environmental or wind-direction information improve spatial ranking
beyond the frozen isotropic distance-only 7B baseline?** The 7B baseline
(`CAND:B0_DISTANCE_ONLY:EXPONENTIAL:25KM:NONE:a48d9efcbb587cf1`,
`frozen_spec_hash=6bb8f67a7bc1188be324bf0a58e2399ed87df619b96c5a0db0ba5a3191794950`)
is the mandatory anchor and is never refit. 7C is not final external
validation, infection probability, causal transmission, final PISTES
risk, final spread direction, or spread-front speed — output remains a
relative spatial ranking, exactly as in 7B.

## 2. Firewall and reused infrastructure

Identical firewall to 7B: `assert_fit_development_only` at the entry
point of `run_checkpoint_7c_development`; `HELD_OUT_FROM_MODEL_FITTING`/
`SRI_LANKA_TRANSFER_CASE_STUDY` origins are hard-rejected before any
repository access. Reused UNCHANGED: `build_calendar_year_folds` (same
folds, same 7-day purge), `classify_target_primary_scope`/
`build_scientific_evaluation_domain` (same 5km grid, same 25km domain),
`dedupe_targets_by_origin_and_event`, the entire 7B evaluation/selection
semantic stack (`compute_area_weighted_percentiles`,
`compute_target_cell_ranks`, `compute_coverage_record`,
`assess_candidate_coverage_eligibility`, `summarize_by_cluster`,
`fold_origin_balanced_metrics`, `overall_equal_origin_weighted`,
`select_candidate`, `clustered_bootstrap_ci`).

**Host-free by design**: 7C candidates never read `Host_i` — no raw host
snapshot cache, no fold-safe reference is built at all. The scientific
grid comes directly from `scientific_domain.build_scientific_evaluation_domain(...).all_cells()`.

## 3. Factor readiness audit

| Factor | Scientific meaning | Raw source | t0 availability | Real/Missing/Blocked/Demo/Not-selected | May enter 7C primary candidates? |
|---|---|---|---|---|---|
| Distance kernel (frozen) | Spatial decay from source | geodesic distance | always | REAL | Yes — the C0 anchor, unchanged from 7B |
| Wind vector (u10/v10) | AOI-center pre-t0 mean wind | ERA5 via Open-Meteo archive API (`services/geospatial/weather/era5.py`) | REAL, network-fetched per origin, `RETROSPECTIVE_REANALYSIS_STATE_PROXY`, t0-safe (`t0_resolution.py`) | REAL (or `WEATHER_INPUT_UNAVAILABLE` per-origin) | Yes — modulates CW(k) via the existing anisotropy primitive |
| Anisotropy factor | Directional modulation of a source's kernel contribution | `services/hazard/anisotropy.py` (existing, reused) | derived from wind + per-source geometry | REAL when wind REAL | Yes |
| Host density | Cattle/buffalo density | FAO GLW | n/a | `NOT_PRIMARY_ELIGIBLE_FROM_7B_COVERAGE_AUDIT` (7B finding: real GLW support gaps) | **No** — never forced back in |
| `environmental_suitability_factor` | Composite temp/humidity/precip/landcover suitability | none defined | n/a | `NOT_YET_SCIENTIFICALLY_DEFINED` (`services/factors/environmental_components.py`) | **No** |
| `water_context_factor` | Distance-to-river transmission relevance | HydroRIVERS | n/a | `NOT_YET_SCIENTIFICALLY_DEFINED` (`services/factors/water_context.py`) | **No** |
| `source_strength_factor` | Per-source outbreak intensity | none defined | n/a | `NOT_SELECTED` (`services/factors/source_strength.py`) | **No** — never substituted with 1 |

No arbitrary weighted composite (e.g. `0.4*rain + 0.3*humidity + ...`) is
constructed anywhere in 7C (Part 12) — none of the raw environmental
components has a scientifically approved aggregation protocol, so none
enters a primary candidate. The full multi-factor hazard-mixing formula
in `services/hazard/source_hazard.py` (`H = a*L + b*W`) is **not used at
all** in 7C: its `L`/`W` pathways structurally require
`host_factor`/`environmental_suitability_factor`/`source_strength_factor`
(local) and additionally `water_context_factor`/`wind_speed_factor`
(anisotropic) to all be `.usable` — none of these are REAL data today, so
that pathway would return `SOURCE_HAZARD_INCOMPLETE` for every real
origin. 7C instead composes the frozen B0 kernel sum directly with the
LOWER-LEVEL, factor-independent anisotropy primitives
(`compute_meteorological_alignment`/`compute_anisotropy_factor`), which
have no such dependency.

## 4. Weather temporal protocol

`services/model_development/wind_readiness_7c.py` calls
`services.geospatial.weather.era5.build_pre_t0_weather_summary` exactly
as `services/features/assembler.py` already does for the primary
historical path: `t0_precision=DATE_ONLY` (this corpus's real
precision), `strict_operational_availability=False`,
`model="era5"`, AOI center = centroid of the origin's own trigger
sources (falling back to all active sources), reusing
`assembler._aoi_center` unchanged. `temporal_role` is always
`RETROSPECTIVE_REANALYSIS_STATE_PROXY`. Missing wind (`BLOCKED`/`MISSING`
u10 or v10) is recorded as `WEATHER_INPUT_UNAVAILABLE` — never replaced
with 0 m/s, north, isotropic-without-label, or a previous value. Real
network responses are cached to disk (`FileWeatherCache`, gitignored
`local_data/cache/weather/`) so a rerun never re-issues an identical
request.

## 5. Anisotropy equation and pre-registered strengths

Reused unchanged from `services/hazard/anisotropy.py` (Checkpoint 6C):

    alignment = t_hat_east * wind_unit_east + t_hat_north * wind_unit_north   (in [-1, 1])
    MODULATING:         A(alignment, kappa) = exp(kappa * alignment)
    ANGULAR_NORMALIZED: A(alignment, kappa) = exp(kappa * alignment) / I0(kappa)

Calm wind (`|wind| < 1e-6 m/s`) always yields `A = 1.0` exactly
(`CALM_NEUTRAL`) — a genuine software guarantee, not an approximation.
`kappa >= 0` is unfrozen. Pre-registered, before any 7C target score was
read: `ANISOTROPY_STRENGTH_CANDIDATES = (0.25, 0.50, 1.00, 2.00)`. Both
pre-existing modes were kept (rather than arbitrarily picking one) since
Checkpoint 6C never scientifically selected between them — this yields 8
wind candidates (2 modes x 4 strengths), never 16 or more (no
environmental/water crossing).

**Mathematical finding (documented, not a bug) — `ANISOTROPY_MODE_NOT_IDENTIFIABLE_UNDER_RANK_METRIC`**:
because `ANGULAR_NORMALIZED`'s `I0(kappa)` divisor is a single positive
constant per candidate (same for every source, every cell, within one
origin's domain), `ANGULAR_NORMALIZED(k)`'s cell scores are always
exactly `MODULATING(k)`'s scores divided by that one constant — a
uniform positive rescaling. The `AREA_WEIGHTED_TARGET_PERCENTILE` metric
(and therefore TOP5/TOP10 capture and rank) is invariant to any such
rescaling. **The two modes are therefore provably rank-equivalent under
this development metric for every kappa.** This was first confirmed
empirically on a small 96-origin `FIT_DEVELOPMENT` sanity subset during
implementation, and has since been **re-confirmed on the completed real
579-origin `FIT_DEVELOPMENT` run**: `MODULATING(k)` and
`ANGULAR_NORMALIZED(k)` produced byte-identical
`mean_target_percentile`/`top5_capture_rate`/`top10_capture_rate` at
every one of the 4 pre-registered kappa values (e.g. `k=0.25`:
`61.31066937113494` for both modes — see
`local_data/model_development/7c/selected_candidate.json`). This metric
cannot distinguish the two hypotheses; a future checkpoint using an
absolute (non-rank) score comparison would be required to do so. If a
wind candidate were ever selected, the report never says "the data
preferred MODULATING/ANGULAR_NORMALIZED" — only that the selected
candidate's kappa defines a rank-equivalence class, and the concrete
mode was resolved solely by the frozen candidate-ID lexical tie-break.

## 6. Candidate registry (Part 13-14)

`C0_FROZEN_B0_ISOTROPIC` (1) + `CW_WIND_ANISOTROPIC` (8) = 9 candidates,
built by `candidate_registry_7c.build_candidate_registry_7c()` (no
arguments — pure). Candidate identity binds: `parent_7b_frozen_spec_hash`,
`evaluation_protocol_hash_7c` (itself binding 7B's own
`baseline_evaluation_protocol_hash`, the weather temporal protocol, and
the anisotropy implementation version), kernel family/scale (frozen),
anisotropy mode/strength. `generated_at` never participates.

## 7. Coverage eligibility and selection

Identical rule to 7B: `PRIMARY_SELECTION_ELIGIBLE` only with zero
`TARGET_SCORE_UNAVAILABLE` rows and missing domain area under the
software-zero tolerance. A wind candidate is ineligible exactly when at
least one validation origin's wind was `WEATHER_INPUT_UNAVAILABLE` (a
real ERA5 gap for that origin/date, never a predictive judgement).
`classify_selection_note_7c` reports
`WIND_CANDIDATES_NOT_PRIMARY_COMPARABLE_DUE_TO_INCOMPLETE_WEATHER_SUPPORT`
precisely when the ineligible set is exactly the wind family and C0
remains fully eligible — mirroring 7B's host-coverage wording rule.

## 8. Paired comparison against the frozen anchor

For every eligible non-anchor candidate, `paired_comparison_7c.py`
computes `delta_mean_target_percentile_vs_anchor`/`delta_top10_vs_anchor`/
`delta_top5_vs_anchor` matched on FORECAST ORIGIN (an origin contributes
only when both C0 and the candidate produced a real per-origin summary
there), plus a paired clustered bootstrap resampling ORIGINS (never grid
cells) for the delta mean percentile, seed=42, 1000 resamples, 95% CI.

## 9. Frozen specification

`protocol_7c.FrozenCheckpoint7CSpecification`,
`parameter_status=FROZEN_AFTER_FIT_DEVELOPMENT_SELECTION` — never
"externally validated." Checkpoint 7D performs the frozen held-out
evaluation.

## 10. Checkpoint 7C.1 — identity hardening (applied as an IDENTITY_ONLY_7C_RESULT_REMAP)

After the real 579-origin run completed, the evaluation-protocol/
candidate identity was hardened to explicitly bind: `parent_7b_frozen_spec_hash`,
`weather_lookback_hours=24` (status `FROZEN_7C_PREDECLARED_WEATHER_LOOKBACK_HOURS`
— set in code before any 7C candidate was ever scored, never tuned
against development performance; changing it in the future requires a
new evaluation-protocol identity, never a silent reuse of these
results), `t0_precision_policy=DATE_ONLY` (proven against the real
579-origin universe — `t0_precision_audit.json`: 579/579 DATE_ONLY, 0
TIMESTAMP, 0 UNKNOWN), `meteorology_spatial_mode=AOI_CENTER_UNIFORM_REAL_PROXY`
(the exact existing `hazard.meteorology.MeteorologySpatialMode` status —
never `SPATIALLY_RESOLVED_REAL`; one real ERA5 observation per origin,
uniform across that origin's domain, while per-source directional
modulation still varies because each source keeps its own
`t_hat_east`/`t_hat_north` geometry), `aoi_center_rule_version`, and
`active_source_window_days` (confirmed NOT already bound inside
`model_development_protocol_hash_7a62` — added explicitly here rather
than assumed transitively covered). The 5km grid, 25km domain, and
frozen 25km EXPONENTIAL kernel ARE already transitively bound via
`parent_7b_frozen_spec_hash`'s own `scientific_grid_config_hash`/
`scientific_domain_protocol_hash` and via each candidate's own kernel
family/scale fields.

None of this changed any numerical computation (lookback was already
24h, t0 precision was already DATE_ONLY, the AOI-center/anisotropy code
is unchanged) — classified as `IDENTITY_ONLY_7C_RESULT_REMAP`. A
deterministic, proven-bijective 9-to-9 mapping from the as-run (7C.1)
candidate ids to the hardened (7C.2) ids was built
(`candidate_registry_7c.build_identity_only_result_remap_7c`) and
applied to relabel the already-persisted real result files —
**the 579-origin scoring pass was never re-run.**

Temporal-role hardening (Part 7): `resolve_origin_wind` now requires
the EXACT `RETROSPECTIVE_REANALYSIS_STATE_PROXY` role for a REAL
primary wind vector; `UNKNOWN` (or any other role) is now explicitly
`WEATHER_TEMPORAL_ROLE_UNAVAILABLE`, never silently admitted. In the
current `era5.py` implementation, `temporal_role=UNKNOWN` only occurs
alongside every feature already `BLOCKED` (unresolved timezone/
unsupported model) — structurally, `UNKNOWN` + `REAL` wind could never
co-occur under the as-run code, so this hardening is proven not to have
changed the real run's outcome (7C-TEMP-01..04).

## 11. Real results (post identity-hardening)

Real 579-origin `FIT_DEVELOPMENT` chronological development-fold
evaluation (never "external validation"). Runtime: 1074.2s (~17.9 min).
5/6 folds usable; 532 intended validation origins, all 532
`VALIDATION_ORIGIN_READY`, 0 blocked. 192 origins had REAL wind, 85 had
`WEATHER_INPUT_UNAVAILABLE` (a real ERA5 data-support gap, ~30.7% of the
277 origins reachable by the selected candidate's own fold set — see the
STOP AND REPORT for the exact denominator). All 8 wind candidates
`PRIMARY_SELECTION_INELIGIBLE_INCOMPLETE_DOMAIN_COVERAGE`; C0 fully
eligible. Selected: `C0_FROZEN_B0_ISOTROPIC` — the only eligible
candidate (`UNIQUE_MAXIMUM_PRIMARY_METRIC` among a pool of one, not a
competitive win over the wind candidates, which were never in the
eligible comparison set). C0's real 7C result is numerically IDENTICAL
(exact Python float equality, not rounded) to the frozen Checkpoint 7B
persisted result: `n_origins=277`, `mean_target_percentile=62.034006257768795`,
`top5_capture_rate=0.11446417040201254`, `top10_capture_rate=0.2024113191944899`,
`1302` unique validation targets. See
`local_data/model_development/7c/checkpoint_7c_audit.json` (gitignored)
and the Checkpoint 7C.1 STOP AND REPORT for the full numbers.
