"""Checkpoint 9B Parts 12-20: the ONE-TIME real S0 percentile-bootstrap
runner.

Not a pytest suite. Run directly:

    python -m components.geospatial_tracking.smoke_tests.run_s0_bootstrap_9b

**No DB, no geospatial, no direction/weather dependency** -- this
script starts from the already-persisted Checkpoint 9A
`rate_target_level_readiness_9a.csv` (371 target-level values) and the
already-persisted `rate_origin_target_observations_9a.csv` (read only
for the historical 12-zero-distance provenance count, never to
recompute any rate). It never calls `SQLiteOutbreakRepository`,
`build_forecast_targets`, `get_eligible_sources`,
`derive_origin_rate_observations`, `classify_target_primary_scope`,
`distance_km`, or `pyproj.Geod`.

Sequence (Parts 12-16), each step reading back what the previous step
wrote to disk rather than trusting in-process memory:

1. Compute the frozen 9B protocol dict/hash (reads the 9A CSV only for
   its SHA256/canonical-payload identity).
2. Write `pre_bootstrap_freeze_manifest_9b.json` (scientific fields
   only; `generated_at` is provenance, never part of the protocol hash).
3. Close the write handle, RE-OPEN and re-read the manifest file bytes
   from disk, compute its SHA256, and write the sidecar
   `pre_bootstrap_freeze_manifest_9b.sha256`.
4. RE-LOAD both the manifest and the sidecar from disk and verify:
   manifest file SHA matches the sidecar, the embedded protocol hash
   matches a freshly recomputed `s0_bootstrap_protocol_hash_9b()`, the
   embedded dataset identity matches a freshly recomputed one, and
   371/371 row/target counts hold.
5. ONLY after every check passes: execute exactly one legitimate
   1000-replicate bootstrap.
6. Persist all result artifacts (Part 18) and their own SHA256 values
   (Part 20) for later immutable read-only verification.

Refuses to run if any final 9B result artifact already exists (Part
16) -- never silently overwrites a real prior result.
"""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..services.model_development.rate_input_identity_9b import compute_dataset_identity
from ..services.model_development.rate_protocol_9b import (
    DEFAULT_9A_TARGET_LEVEL_CSV_PATH,
    EXPOSED_ESTIMATOR_VALUE_9B,
    N_ZERO_DISTANCE_ORIGIN_TARGET_9B,
    N_ZERO_TARGET_LEVEL_MEDIAN_9B,
    RATE_LABEL_9B,
    RESULT_INTERPRETATION_LIMITATIONS_9B,
    bootstrap_implementation_source_sha256,
    s0_bootstrap_protocol_dict_9b,
    s0_bootstrap_protocol_hash_9b,
)
from ..services.model_development.rate_s0_bootstrap_9b import (
    BOOTSTRAP_CI_TYPE_9B,
    BOOTSTRAP_N_RESAMPLES_9B,
    BOOTSTRAP_SEED_9B,
    BOOTSTRAP_UNIT_9B,
    compute_bootstrap_uncertainty,
)

LOCAL_OUT_DIR = DEFAULT_9A_TARGET_LEVEL_CSV_PATH.parent.parent / "9b_rate"
_OBS_CSV_9A = DEFAULT_9A_TARGET_LEVEL_CSV_PATH.parent / "rate_origin_target_observations_9a.csv"

_MANIFEST_PATH = LOCAL_OUT_DIR / "pre_bootstrap_freeze_manifest_9b.json"
_MANIFEST_SHA_SIDECAR_PATH = LOCAL_OUT_DIR / "pre_bootstrap_freeze_manifest_9b.sha256"
_RESULT_FILES = (
    "rate_input_dataset_identity_9b.json",
    "s0_bootstrap_draws_9b.csv",
    "s0_bootstrap_uncertainty_9b.json",
    "frozen_s0_apparent_rate_spec_9b.json",
    "bootstrap_execution_record_9b.json",
    "checkpoint_9b_audit.json",
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _count_zero_distance_origin_target_rows() -> int:
    with _OBS_CSV_9A.open(encoding="utf-8") as f:
        return sum(1 for row in csv.DictReader(f) if row["is_zero_distance"] == "True")


if __name__ == "__main__":
    for filename in _RESULT_FILES:
        existing = LOCAL_OUT_DIR / filename
        if existing.exists():
            raise SystemExit(
                f"REFUSING TO RUN: 9B result artifact already exists ({existing}). "
                "This is a one-time runner -- it never silently overwrites a real prior result. "
                "If a genuine correction is needed, create a versioned correction artifact instead."
            )

    print("Checkpoint 9B Step 1: computing frozen protocol identity from the already-persisted 9A dataset...")
    protocol_dict = s0_bootstrap_protocol_dict_9b()
    protocol_hash = s0_bootstrap_protocol_hash_9b()
    dataset_identity, rows = compute_dataset_identity(DEFAULT_9A_TARGET_LEVEL_CSV_PATH)
    bootstrap_source_sha = bootstrap_implementation_source_sha256()
    n_zero_origin_target = _count_zero_distance_origin_target_rows()

    if dataset_identity.n_rows != 371 or dataset_identity.n_unique_target_event_id != 371:
        raise SystemExit(f"STOP: expected 371/371, got {dataset_identity.n_rows}/{dataset_identity.n_unique_target_event_id}")
    if n_zero_origin_target != N_ZERO_DISTANCE_ORIGIN_TARGET_9B:
        raise SystemExit(f"STOP: expected {N_ZERO_DISTANCE_ORIGIN_TARGET_9B} zero-distance origin-target rows, got {n_zero_origin_target}")
    target_level_rates = [r.rate_value for r in rows]
    n_zero_target_level = sum(1 for v in target_level_rates if v == 0.0)
    if n_zero_target_level != N_ZERO_TARGET_LEVEL_MEDIAN_9B:
        raise SystemExit(f"STOP: expected {N_ZERO_TARGET_LEVEL_MEDIAN_9B} zero target-level medians, got {n_zero_target_level}")

    point_estimate_preview = statistics.median(target_level_rates)
    if point_estimate_preview != EXPOSED_ESTIMATOR_VALUE_9B:
        raise SystemExit(
            f"STOP: recomputed point median {point_estimate_preview!r} does not exactly match the already-exposed "
            f"9A.1 value {EXPOSED_ESTIMATOR_VALUE_9B!r} -- do NOT proceed, do NOT 'correct' the dataset"
        )

    print(f"  9B protocol hash = {protocol_hash}")
    print(f"  input_csv_sha256 = {dataset_identity.input_csv_sha256}")
    print(f"  canonical_payload_hash = {dataset_identity.canonical_payload_hash_from_persisted_text}")
    print(f"  point estimate (preview, matches exposed 9A.1 value) = {point_estimate_preview}")

    print("\nStep 2: writing pre_bootstrap_freeze_manifest_9b.json (BEFORE any real bootstrap)...")
    manifest_written_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "checkpoint": "9B",
        "formal_purpose": "FORMAL_FREEZE_OF_PREDECLARED_S0_ESTIMATOR_WITH_PRE_9B_NUMERIC_VALUE_EXPOSURE_DISCLOSED_AND_BOOTSTRAP_UNCERTAINTY",
        "s0_bootstrap_protocol_hash_9b": protocol_hash,
        "s0_bootstrap_protocol_dict_9b": protocol_dict,
        "dataset_identity": dataset_identity.as_dict(),
        "n_zero_distance_origin_target_observations": n_zero_origin_target,
        "n_zero_target_level_median_rates": n_zero_target_level,
        "point_estimate_preview_km_day": point_estimate_preview,
        "bootstrap_implementation_source_sha256": bootstrap_source_sha,
        "rate_label": RATE_LABEL_9B,
        "result_interpretation_limitations": RESULT_INTERPRETATION_LIMITATIONS_9B,
        "generated_at": manifest_written_at,  # provenance only -- NOT part of protocol_hash above
    }
    _write_json(_MANIFEST_PATH, manifest)
    print(f"  wrote {_MANIFEST_PATH}")

    print("\nStep 3: closing write handle, re-reading manifest bytes from disk, hashing, writing sidecar...")
    manifest_file_sha256 = _sha256_file(_MANIFEST_PATH)
    _MANIFEST_SHA_SIDECAR_PATH.write_text(manifest_file_sha256, encoding="utf-8")
    print(f"  pre_bootstrap_manifest_file_sha256 = {manifest_file_sha256}")

    print("\nStep 4: re-loading manifest + sidecar from disk and verifying BEFORE execution...")
    reloaded_manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    reloaded_sidecar_sha = _MANIFEST_SHA_SIDECAR_PATH.read_text(encoding="utf-8").strip()
    recomputed_manifest_sha = _sha256_file(_MANIFEST_PATH)
    assert reloaded_sidecar_sha == recomputed_manifest_sha, "STOP: manifest sidecar SHA does not match the manifest file on disk"
    assert reloaded_manifest["s0_bootstrap_protocol_hash_9b"] == s0_bootstrap_protocol_hash_9b(), "STOP: protocol hash drifted between write and verify"
    assert reloaded_manifest["dataset_identity"]["input_csv_sha256"] == dataset_identity.input_csv_sha256
    assert reloaded_manifest["dataset_identity"]["n_rows"] == 371
    assert reloaded_manifest["dataset_identity"]["n_unique_target_event_id"] == 371
    print("  ALL PRE-EXECUTION CHECKS PASSED.")

    print("\nStep 5: executing the ONE legitimate 1000-replicate bootstrap...")
    execution_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()
    t_start = time.monotonic()
    result, draws = compute_bootstrap_uncertainty(target_level_rates, seed=BOOTSTRAP_SEED_9B, n_resamples=BOOTSTRAP_N_RESAMPLES_9B)
    completed_at = datetime.now(timezone.utc).isoformat()
    runtime_seconds = time.monotonic() - t_start
    print(f"  point_estimate={result.point_estimate}, ci=({result.ci_lower}, {result.ci_upper}), runtime={runtime_seconds:.3f}s")

    assert result.point_estimate == EXPOSED_ESTIMATOR_VALUE_9B, "STOP: bootstrap point estimate does not match the exposed 9A.1 value"

    print("\nStep 6: persisting result artifacts...")
    LOCAL_OUT_DIR.mkdir(parents=True, exist_ok=True)

    _write_json(LOCAL_OUT_DIR / "rate_input_dataset_identity_9b.json", dataset_identity.as_dict())

    draws_csv_path = LOCAL_OUT_DIR / "s0_bootstrap_draws_9b.csv"
    with draws_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["replicate_index", "bootstrap_median_km_day"])
        for i, d in enumerate(draws):
            writer.writerow([i, d])
    result_draws_sha256 = _sha256_file(draws_csv_path)

    uncertainty = {
        "point_estimate_km_day": result.point_estimate,
        "ci_lower_km_day": result.ci_lower,
        "ci_upper_km_day": result.ci_upper,
        "bootstrap_interval_type": "TARGET_EVENT_LEVEL_PERCENTILE_BOOTSTRAP_INTERVAL",
        "n_target_events": result.n_target_events,
        "n_resamples": result.n_resamples,
        "seed": result.seed,
        "bootstrap_unit": BOOTSTRAP_UNIT_9B,
        "draws_min": result.draws_min,
        "draws_median": result.draws_median,
        "draws_max": result.draws_max,
        "result_draws_sha256": result_draws_sha256,
    }
    _write_json(LOCAL_OUT_DIR / "s0_bootstrap_uncertainty_9b.json", uncertainty)

    frozen_spec = {
        "label": RATE_LABEL_9B,
        "estimator": "median across unique target-level apparent rates",
        "development_dataset_n_target_events": 371,
        "point_estimate_km_day": result.point_estimate,
        "bootstrap_interval_lower_km_day": result.ci_lower,
        "bootstrap_interval_upper_km_day": result.ci_upper,
        "bootstrap_interval_type": "TARGET_EVENT_LEVEL_PERCENTILE_BOOTSTRAP_INTERVAL",
        "bootstrap_seed": BOOTSTRAP_SEED_9B,
        "bootstrap_n_resamples": BOOTSTRAP_N_RESAMPLES_9B,
        "primary_horizon": "D1_D7",
        "local_scope": "25_KM_OPERATIONAL_LOCAL_EVALUATION_ENVELOPE",
        "temporal_semantics": "RECORDED_HISTORICAL_EVENT_DATE_TARGET_OCCURRENCE_PROXY",
        "availability_semantics": "RETROSPECTIVE_PROXY",
        "nearest_source_semantics": "NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE",
        "pre_9b_numeric_exposure": "DISCLOSED",
        "heldout_rate_validation_status": "NOT_EVALUATED_IN_9B",
        "sri_lanka_rate_status": "NOT_EVALUATED_IN_9B",
        "s1_status": "NOT_SELECTED",
        "nominal_reach_status": "NOT_COMPUTED_IN_9B",
        "n_zero_distance_origin_target_observations": n_zero_origin_target,
        "n_zero_target_level_median_rates": n_zero_target_level,
        "result_interpretation_limitations": RESULT_INTERPRETATION_LIMITATIONS_9B,
        "s0_bootstrap_protocol_hash_9b": protocol_hash,
    }
    _write_json(LOCAL_OUT_DIR / "frozen_s0_apparent_rate_spec_9b.json", frozen_spec)

    execution_record = {
        "execution_id": execution_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "manifest_file_sha256_loaded_before_execution": recomputed_manifest_sha,
        "s0_bootstrap_protocol_hash_9b": protocol_hash,
        "input_target_level_csv_sha256": dataset_identity.input_csv_sha256,
        "canonical_dataset_identity_hash": dataset_identity.canonical_payload_hash_from_persisted_text,
        "bootstrap_implementation_source_sha256": bootstrap_source_sha,
        "n_target_events": result.n_target_events,
        "n_resamples": result.n_resamples,
        "seed": result.seed,
        "exit_status": "COMPLETED_SUCCESSFULLY",
        "result_draws_sha256": result_draws_sha256,
        "runtime_seconds": runtime_seconds,
    }
    _write_json(LOCAL_OUT_DIR / "bootstrap_execution_record_9b.json", execution_record)

    # Part 20: compute and persist immutability hashes for every result artifact,
    # INCLUDING this audit file's own sibling artifacts (never a self-referential cycle).
    result_artifact_sha256 = {}
    for filename in ("rate_input_dataset_identity_9b.json", "s0_bootstrap_draws_9b.csv", "s0_bootstrap_uncertainty_9b.json", "frozen_s0_apparent_rate_spec_9b.json", "bootstrap_execution_record_9b.json"):
        result_artifact_sha256[filename] = _sha256_file(LOCAL_OUT_DIR / filename)

    audit = {
        "checkpoint": "9B",
        "classification": "FROZEN_DEVELOPMENT_DERIVED_S0_ESTIMATED_APPARENT_LOCAL_SPREAD_FRONT_RATE_WITH_PRE_9B_NUMERIC_EXPOSURE_DISCLOSED_AND_TARGET_EVENT_BOOTSTRAP_UNCERTAINTY",
        "parent_historical_9a_protocol_hash": "326427b08f5c43b9708409ae112460e8f0804db0c972a007caaae8ffca3b58ac",
        "nine_a1_exposure_classification": "PRE_9B_S0_NUMERIC_ESTIMATOR_EXPOSURE_IN_9A_DIAGNOSTIC_DISCLOSED",
        "s0_bootstrap_protocol_hash_9b": protocol_hash,
        "pre_bootstrap_manifest_file_sha256": recomputed_manifest_sha,
        "point_estimate_km_day": result.point_estimate,
        "bootstrap_interval_lower_km_day": result.ci_lower,
        "bootstrap_interval_upper_km_day": result.ci_upper,
        "n_target_events": result.n_target_events,
        "n_resamples": result.n_resamples,
        "seed": result.seed,
        "result_artifact_sha256": result_artifact_sha256,
        "heldout_rate_status": "NOT_EVALUATED_IN_9B",
        "sri_lanka_rate_status": "NOT_EVALUATED_IN_9B",
        "s1_status": "NOT_SELECTED",
        "nominal_reach_status": "NOT_COMPUTED_IN_9B",
    }
    _write_json(LOCAL_OUT_DIR / "checkpoint_9b_audit.json", audit)

    print(f"\nRuntime: {runtime_seconds:.3f}s")
    print(json.dumps(uncertainty, indent=2, default=str))
    print(f"\nWrote: {LOCAL_OUT_DIR}")
