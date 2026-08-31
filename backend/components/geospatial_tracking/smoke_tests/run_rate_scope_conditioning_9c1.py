"""Checkpoint 9C.1: real post-freeze rate-scope conditioning diagnostic
run.

Not a pytest suite. READ-ONLY over the already-persisted Checkpoint 9A
CSVs -- no DB access, no geodesic recomputation, no 9B bootstrap
rerun. Run directly:

    python -m components.geospatial_tracking.smoke_tests.run_rate_scope_conditioning_9c1

Writes diagnostic-only output to
`local_data/model_development/9c1_rate_scope/`. Never modifies any
Checkpoint 9A/9B/9C artifact. STOPs (raises `SystemExit`) if the input
CSV SHA256 doesn't match the previously evidenced 9A artifact identity,
if any observed within-scope v_obs exceeds its theoretical ceiling
beyond tolerance, or if the WITHIN target-event set doesn't exactly
match the frozen `rate_target_level_readiness_9a.csv` target set.
"""

from __future__ import annotations

import hashlib
import json

from ..services.geospatial.raster import LOCAL_GIS_CACHE_DIR
from ..services.model_development.rate_protocol_9b import DEFAULT_9A_TARGET_LEVEL_CSV_PATH, EXPOSED_ESTIMATOR_VALUE_9B
from ..services.model_development.rate_scope_conditioning_9c1 import (
    GPS_QUALITY_LIMITATION_9C1,
    NOMINAL_REACH_D7_INTERPRETATION_NOTE_9C1,
    RATE_ESTIMAND_CONDITIONING_9C1,
    RATE_ESTIMAND_STATEMENT_9C1,
    field_completeness_by_scope,
    gps_quality_by_lead_audit,
    load_csv_rows,
    load_target_level_ids,
    reconcile_by_lead_day,
    s0_vs_theoretical_ceiling,
    target_event_inclusion_audit,
    theoretical_ceiling_table,
    within_rate_distribution_by_lead,
)
from ..services.model_development.rate_scope_conditioning_protocol_9c1 import (
    INPUT_OBSERVATION_CSV_SHA256_9C1,
    rate_scope_conditioning_protocol_dict_9c1,
    rate_scope_conditioning_protocol_hash_9c1,
)

_9A_DIR = DEFAULT_9A_TARGET_LEVEL_CSV_PATH.parent
_OBS_CSV = _9A_DIR / "rate_origin_target_observations_9a.csv"
LOCAL_OUT_DIR = LOCAL_GIS_CACHE_DIR.parent / "model_development" / "9c1_rate_scope"

# Historical/verbatim reference only (Part 10) -- copied from the
# already-frozen Checkpoint 9C result, never recomputed here.
HISTORICAL_9C_NOMINAL_REACH_BY_DAY_KM = {
    "1": 3.946421443154751, "2": 7.892842886309502, "3": 11.839264329464253,
    "4": 15.785685772619004, "5": 19.732107215773755, "6": 23.678528658928506, "7": 27.624950102083258,
}
HISTORICAL_9C_OPERATIONAL_ENVELOPE_KM = 25.0

BOOTSTRAP_INTERPRETATION_9C1 = (
    "The frozen 9B interval [3.5491046170907765, 4.343077329563724] quantifies empirical target-event "
    "resampling uncertainty CONDITIONAL ON the frozen selected 371-target rate dataset. It does NOT account "
    "for 25-km scope-selection uncertainty, the lead-dependent truncation mechanism, GPS/reporting "
    "measurement error, or country/spatial/temporal higher-level dependence. The existing 9B higher-level "
    "dependence and finite-Monte-Carlo limitations remain unchanged."
)


def main() -> None:
    LOCAL_OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Part 3: SHA256 verification BEFORE any diagnostic computation.
    actual_sha256 = hashlib.sha256(_OBS_CSV.read_bytes()).hexdigest()
    if actual_sha256 != INPUT_OBSERVATION_CSV_SHA256_9C1:
        raise SystemExit(
            f"9C.1 Part 3 STOP: {_OBS_CSV.name} SHA256 mismatch -- expected {INPUT_OBSERVATION_CSV_SHA256_9C1}, "
            f"got {actual_sha256}"
        )

    rows = load_csv_rows(_OBS_CSV)
    print(f"Loaded {len(rows)} origin-target observation rows (SHA256 verified).")

    # Part 4
    completeness = field_completeness_by_scope(rows)

    # Part 5
    lead_recon = reconcile_by_lead_day(rows)
    pooled_total = sum(v["n_total_origin_target_rows"] for v in lead_recon.values())
    pooled_within = sum(v["n_within_25km"] for v in lead_recon.values())
    pooled_outside = sum(v["n_outside_25km"] for v in lead_recon.values())
    pooled_unresolved = sum(v["n_unresolved"] for v in lead_recon.values())
    if (pooled_total, pooled_within, pooled_outside, pooled_unresolved) != (3947, 1387, 2560, 0):
        raise SystemExit(
            f"9C.1 Part 5 STOP: pooled per-lead reconciliation does not match the frozen 3947/1387/2560/0 "
            f"population -- got total={pooled_total} within={pooled_within} outside={pooled_outside} "
            f"unresolved={pooled_unresolved}"
        )
    print(f"Per-lead reconciliation: total={pooled_total} within={pooled_within} outside={pooled_outside} unresolved={pooled_unresolved}")

    # Part 6/7 -- raises SystemExit-equivalent AssertionError internally on violation
    ceiling_table = theoretical_ceiling_table()
    rate_dist = within_rate_distribution_by_lead(rows)
    s0_vs_ceiling = s0_vs_theoretical_ceiling(EXPOSED_ESTIMATOR_VALUE_9B)
    d7_ceiling_below_s0 = ceiling_table["7"] < EXPOSED_ESTIMATOR_VALUE_9B
    print(f"D7 theoretical ceiling={ceiling_table['7']:.6f} < frozen S0={EXPOSED_ESTIMATOR_VALUE_9B}: {d7_ceiling_below_s0}")

    # Part 8
    frozen_target_ids = load_target_level_ids(DEFAULT_9A_TARGET_LEVEL_CSV_PATH)
    target_audit = target_event_inclusion_audit(rows, frozen_target_ids)
    print(
        f"Target-event inclusion: all={target_audit['n_unique_target_event_id_all_rows']} "
        f"with>=1 WITHIN={target_audit['n_unique_target_event_id_with_at_least_one_WITHIN']} "
        f"only_OUTSIDE={target_audit['n_unique_target_event_id_only_OUTSIDE']} "
        f"mixed={target_audit['n_unique_target_event_id_mixed_WITHIN_and_OUTSIDE']} "
        f"only_WITHIN={target_audit['n_unique_target_event_id_only_WITHIN']}"
    )

    # Part 11
    gps_audit = gps_quality_by_lead_audit(rows)

    protocol_dict = rate_scope_conditioning_protocol_dict_9c1()
    protocol_hash = rate_scope_conditioning_protocol_hash_9c1()

    (LOCAL_OUT_DIR / "rate_scope_conditioning_protocol_9c1.json").write_text(
        json.dumps({
            "protocol": protocol_dict,
            "protocol_hash": protocol_hash,
            "input_observation_csv_sha256_verified": actual_sha256,
            "field_completeness_by_scope": completeness,
            "pooled_reconciliation": {
                "n_total_origin_target_rows": pooled_total, "n_within_25km": pooled_within,
                "n_outside_25km": pooled_outside, "n_unresolved": pooled_unresolved,
            },
        }, indent=2), encoding="utf-8",
    )

    (LOCAL_OUT_DIR / "lead_day_rate_scope_conditioning_audit.json").write_text(
        json.dumps({
            "theoretical_ceiling_table_km_day": ceiling_table,
            "frozen_s0_km_day": EXPOSED_ESTIMATOR_VALUE_9B,
            "d7_theoretical_ceiling_below_frozen_s0": d7_ceiling_below_s0,
            "reconciliation_by_lead_day": lead_recon,
            "within_rate_distribution_by_lead": rate_dist,
            "s0_vs_theoretical_ceiling_by_lead": s0_vs_ceiling,
        }, indent=2), encoding="utf-8",
    )

    (LOCAL_OUT_DIR / "target_event_scope_participation_audit.json").write_text(
        json.dumps(target_audit, indent=2), encoding="utf-8",
    )

    (LOCAL_OUT_DIR / "gps_quality_by_lead_rate_audit.json").write_text(
        json.dumps({**gps_audit, "limitation": GPS_QUALITY_LIMITATION_9C1}, indent=2), encoding="utf-8",
    )

    (LOCAL_OUT_DIR / "rate_scope_interpretation_9c1.json").write_text(
        json.dumps({
            "rate_estimand_conditioning": RATE_ESTIMAND_CONDITIONING_9C1,
            "rate_estimand_statement": RATE_ESTIMAND_STATEMENT_9C1,
            "nominal_reach_interpretation_note": NOMINAL_REACH_D7_INTERPRETATION_NOTE_9C1,
            "historical_9c_nominal_reach_by_day_km_unchanged": HISTORICAL_9C_NOMINAL_REACH_BY_DAY_KM,
            "historical_9c_operational_envelope_km_unchanged": HISTORICAL_9C_OPERATIONAL_ENVELOPE_KM,
            "bootstrap_interpretation": BOOTSTRAP_INTERPRETATION_9C1,
            "final_classification": "RATE_SCOPE_CONDITIONING_AUDIT_COMPLETE_PRIMARY_S0_RETAINED_WITH_EXPLICIT_CONDITIONAL_INTERPRETATION",
        }, indent=2), encoding="utf-8",
    )

    print(f"Wrote 9C.1 diagnostic artifacts to {LOCAL_OUT_DIR}")
    print(f"rate_scope_conditioning_protocol_hash_9c1 = {protocol_hash}")


if __name__ == "__main__":
    main()
