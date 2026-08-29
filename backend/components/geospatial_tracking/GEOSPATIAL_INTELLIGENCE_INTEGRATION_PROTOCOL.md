# Geospatial Intelligence Integration Protocol (Checkpoint 9C)

Checkpoint 9C performs no model development and no predictive
evaluation. It answers exactly one question: how should the
already-frozen risk score (Checkpoint 7C), descriptive geometric
direction field (Checkpoint 8B.3), and apparent historical rate
(Checkpoint 9B) be represented together — plus one new deterministic
derived quantity, nominal reach — without conflating their scientific
meanings? This is `FROZEN_COMPONENT_INTEGRATION_SEMANTICS`, never model
fitting, validation, forecast-performance evaluation, rate calibration,
direction validation, or new disease modeling.

No FastAPI route and no frontend code exists yet. This document
describes the internal, DB/framework-independent contract only.

## 1. Six hard separations

These are the load-bearing invariants of this checkpoint. Every one is
enforced structurally (AST import scans in
`tests/test_checkpoint_9c_integration.py`), not merely by convention.

1. **25km envelope != nominal reach.** The frozen 25km operational
   local evaluation envelope
   (`services.model_development.local_evaluation_scope.PRIMARY_LOCAL_EVALUATION_DISTANCE_KM`)
   and `nominal_reach_km(day_h) = frozen_S0_rate_km_day * day_h` are two
   different quantities that must coexist. Day 7 nominal reach
   (`27.625` km) exceeds 25km by design — this is expected, never
   clipped, truncated, or reconciled via `min()`/`max()`.
   `nominal_reach_9c.py` structurally never imports
   `local_evaluation_scope`.
2. **Static C0 != day-varying risk.** The frozen C0 baseline is a t0
   static spatial-ranking model. `risk_surface_temporal_semantics =
   STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT` is stated explicitly.
   Nominal reach never modifies the C0 cell score; no D1-D7 risk
   surfaces are fabricated by multiplying C0 with the rate/reach.
   `nominal_reach_9c.py`/`geospatial_intelligence_contract_9c.py`
   structurally never import any C0-scoring module (`baseline_scoring`,
   `wind_scoring_7c`, `candidate_registry_7c`, `hazard.*`).
3. **Direction != speed.** `rate != magnitude(direction vector)`,
   `rate != directional_clarity`, `rate != wind speed`, `rate != C0
   score`. Direction is never scaled into km/day; rate is never used to
   create a new direction. `default_apparent_rate_component_9c()` takes
   zero arguments — it structurally cannot read a bearing/clarity
   value.
4. **Clarity != confidence.** `directional_clarity` is normalized
   geometric resultant coherence, never a confidence/probability. No
   field on `DirectionComponent9C` is named or aliased "confidence"
   (checked by dataclass field-name inspection).
5. **Rate != biological transmission speed.** The apparent rate is a
   frozen development-derived historical geometric rate
   (`rate_status = FROZEN_DEVELOPMENT_HISTORICAL_APPARENT_RATE`), not a
   validated biological transmission speed, and inherits every
   Checkpoint 9B limitation (A-I).
6. **Nominal reach != disease boundary.** `nominal_reach_semantics =
   VISUALIZATION_ONLY_NOT_HARD_DISEASE_BOUNDARY`. It is never a maximum
   LSD transmission distance, infection radius, quarantine boundary,
   risk-surface boundary, probability contour, guaranteed travel
   distance, or biological epidemic-front location.

## 2. Nominal reach

```
nominal_reach_km(day_h) = frozen_S0_rate_km_day * day_h
```

`frozen_S0_rate_km_day = 3.946421443154751` (the already-frozen
Checkpoint 9B point estimate, imported directly — never recomputed),
for `day_h ∈ {1,...,7}` only. D8-D14 exploratory horizons are explicitly
out of scope for this checkpoint's primary contract.

| day | nominal_reach_km | derived interval (km) |
|---|---|---|
| 1 | 3.946421443154751 | [3.549, 4.343] |
| 2 | 7.892842886309502 | [7.098, 8.686] |
| 3 | 11.839264329464253 | [10.647, 13.029] |
| 4 | 15.785685772619004 | [14.196, 17.372] |
| 5 | 19.732107215773755 | [17.746, 21.715] |
| 6 | 23.678528658928506 | [21.295, 26.058] |
| 7 | 27.624950102083258 | [24.844, 30.402] |

The derived interval is a pure multiplication of the two already-frozen
Checkpoint 9B bootstrap endpoints (`3.5491046170907765`/
`4.343077329563724` km/day) — never a new resample.
`services.model_development.rate_s0_bootstrap_9b` (the bootstrap
implementation module) is structurally never imported by any Checkpoint
9C module.

## 3. Internal contract shape

`services/integration/geospatial_intelligence_contract_9c.py` defines
`FrozenGeospatialIntelligenceContract9C`:

- `risk`: `risk_score`, `risk_score_semantics`
  (`RELATIVE_SPATIAL_SCORE_NOT_INFECTION_PROBABILITY`), `candidate_id`,
  `frozen_spec_hash`, `risk_surface_temporal_semantics`.
- `direction`: `direction_method_id`, `direction_method_version`,
  `bearing_deg`, `directional_clarity`, `directional_input_coverage`,
  `direction_status`, `direction_semantics`. Bearing `0.0` is valid
  NORTH; unavailable direction is `None`, never fabricated to `0.0` —
  every check uses `is not None`.
- `apparent_rate`: `apparent_rate_km_day`, `apparent_rate_label`,
  `rate_interval_lower_km_day`, `rate_interval_upper_km_day`,
  `rate_status`, `rate_scope`, `rate_validation_status`,
  `sri_lanka_rate_status`. A single frozen global scalar — never
  per-cell.
- `nominal_reach_by_day`: one entry per D1-D7 (`day`,
  `nominal_reach_km`, optional `derived_interval_lower_km`/
  `derived_interval_upper_km`).
- `operational_evaluation_envelope_km` (`25.0`): always a separate
  top-level field from `nominal_reach_by_day` — never reused for both
  concepts.
- `provenance`: every frozen parent hash plus
  `research_evidence_status` (risk/direction/rate/Sri Lanka evidence
  classification).
- `limitations`: the full inherited limitation set.

The DTO performs no scientific computation. `risk_score` and the
direction tendency are supplied by the caller, already computed by the
frozen 7C/8B.3 services elsewhere; `apparent_rate`/
`nominal_reach_by_day`/`provenance` are pure frozen-constant
transforms, identical across every call.

## 4. Versioned protocol identity

`services/integration/geospatial_intelligence_protocol_9c.py` binds
every frozen parent hash, the nominal-reach formula/D1-D7 range, the
frozen rate point/CI, and every separation rule above into one
deterministic hash, excluding any timestamp, absolute machine path, UI
styling, or HTTP URL:

```
integration_protocol_hash_9c() = cec826a26c860c752d1fa32d94edcdfba2e0186950cdccfc96067fef2ce51a90
```

The 9B protocol hash and both rate-dataset SHA256 values are copied
literally from the already-frozen Checkpoint 9B result — never re-read
from the gitignored `local_data` tree by this module, so the hash stays
computable on a clean clone; verified byte-identical against the real
disk-computed 9B function output in this development environment.

## 5. Firewalls

No 7B-9B rerun, no bootstrap rerun, no `d_min`/`v_obs` rebuild, no C0
recomputation, no held-out/Sri Lanka rate inspection, and no database
query — all verified structurally via AST import scans, not by
convention: none of the three Checkpoint 9C modules import
`heldout_run_7d`, `sri_lanka_run_7e`, `sri_lanka_protocol_7e`,
`rate_s0_bootstrap_9b`, `rate_readiness_9a`, `rate_input_identity_9b`,
or any repository/database module. The one import of
`heldout_protocol_7d` (for the frozen `SELECTED_CANDIDATE_ID`/
`FROZEN_7C_SPEC_HASH` risk-model identity constants only) is the frozen
C0 model's own identity, not a held-out rate evaluation — explicitly
distinct from the forbidden `heldout_run_7d` module.

See `RATE_MODEL_PROTOCOL.md` §22, `MODEL_DEVELOPMENT_PROTOCOL.md` §71,
`VALIDATION_PROTOCOL.md` §16, `DATA_AUDIT.md` §100,
`DIRECTION_8B_PROTOCOL.md` §20.10.

## 6. Checkpoint 9C.1 addendum — rate-scope conditioning (S0 unchanged, interpretation hardened)

A read-only post-freeze diagnostic (`RATE_MODEL_PROTOCOL.md` §23)
established that the frozen 25-km inclusion rule mathematically forces
`v_obs <= 25/lead_days` for every included observation — the D7
theoretical ceiling (`3.571` km/day) is strictly below the frozen S0
(`3.946` km/day). This does not change S0, the 9B interval, the 25km
envelope, or any Checkpoint 9C nominal-reach number — all are
byte/numerically unchanged. It hardens the interpretation only: the
frozen S0 is now stated explicitly as conditional on the 25-km
local-scope inclusion mechanism
(`RATE_ESTIMAND_CONDITIONING = D1_D7_TARGET_EVENT_APPARENT_RATE_CONDITIONAL_ON_AT_LEAST_ONE_VALID_25KM_LOCAL_SCOPE_OBSERVATION_UNDER_RETROSPECTIVE_PROXY`),
and D7 nominal reach (`27.625` km, still correctly > 25km) is
explicitly **not** evidence of an empirically validated epidemic front
beyond 25km — it remains a deterministic visualization extrapolation
from the pooled frozen S0. See `RATE_MODEL_PROTOCOL.md` §23.
