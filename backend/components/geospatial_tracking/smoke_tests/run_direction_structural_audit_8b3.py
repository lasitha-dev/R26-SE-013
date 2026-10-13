"""Checkpoint 8B.3 Part 12: real FIT_DEVELOPMENT-only structural
readiness audit of the ACTIVE cell-local-frame direction field, PLUS an
honest old(8B, source-departure-frame)-vs-new(8B.3, cell-local-frame)
difference audit over the real corpus.

Not a pytest suite. Real DB access over the REAL, runtime-derived
`FIT_DEVELOPMENT` origin universe -- never hardcoded. Run directly:

    python -m components.geospatial_tracking.smoke_tests.run_direction_structural_audit_8b3

**Allowed to rerun** (unlike a risk-model rerun) because this uses no
target outcomes, is FIT_DEVELOPMENT structural evidence only, tunes
nothing, and C0 itself is unchanged -- it is a geometry-only
comparison between two direction-FIELD implementations, not a
predictive re-evaluation.

Writes to a SEPARATE, clearly versioned directory
(`local_data/model_development/8b3_direction/`) -- the historical
Checkpoint 8B artifacts under `local_data/model_development/8b_direction/`
are NEVER touched by this script.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from pathlib import Path

from ..config import DEFAULT_SQLITE_DB_PATH
from ..repositories.sqlite_repository import SQLiteOutbreakRepository
from ..services.direction.c0_cell_local_tendency_8b3 import compute_cell_direction_tendency_8b3
from ..services.direction.c0_geometric_tendency import compute_cell_direction_tendency
from ..services.forecast_origin import build_forecast_origin_ledger
from ..services.geospatial.scientific_domain import build_scientific_evaluation_domain
from ..services.model_development.candidate_registry_7c import C0_FAMILY, build_candidate_registry_7c
from ..services.model_development.development_run_7b import _eligible_source_points
from ..services.model_development.development_run_7c import _grid_cell_dicts
from ..services.model_development.direction_protocol_8b import (
    direction_method_protocol_dict_8b3,
    direction_method_protocol_hash_8b3,
    verify_8a1_preflight,
)
from ..services.model_development.evaluation_protocol_7c import ACTIVE_SOURCE_WINDOW_DAYS_7C
from ..services.model_development.wind_scoring_7c import score_origin_candidates_7c
from ..services.model_fitting_exposure import fit_development_origins
from .run_direction_structural_audit_8b import DISEASE, _grid_config, _percentiles

LOCAL_OUT_DIR_8B3 = Path(__file__).resolve().parents[4] / "local_data" / "model_development" / "8b3_direction"

_c0_spec = next(c for c in build_candidate_registry_7c() if c.family == C0_FAMILY)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


def _circular_bearing_delta(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


if __name__ == "__main__":
    print("Checkpoint 8B.3 Part 0: 8A.1 pre-flight identity check...")
    verify_8a1_preflight()
    protocol_dict = direction_method_protocol_dict_8b3()
    protocol_hash = direction_method_protocol_hash_8b3()
    print(f"  direction_method_protocol_hash_8b3 = {protocol_hash}")

    t_start = time.monotonic()
    db_path = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
    repo = SQLiteOutbreakRepository(db_path)

    all_origins = build_forecast_origin_ledger(repo, disease=DISEASE)
    dev_origins = fit_development_origins(all_origins)
    print(f"Real FIT_DEVELOPMENT universe (runtime-derived): {len(dev_origins)} origins")

    grid_config = _grid_config()

    n_origins_processed = 0
    n_origins_no_eligible_source = 0
    n_origins_no_grid = 0
    n_cells_processed = 0
    direction_status_counts: dict = {}
    coverage_status_counts: dict = {}
    clarity_values: list[float] = []
    coverage_values: list[float] = []
    n_exact_zero_distance_cases = 0
    n_invariant_failures = 0
    invariant_failure_examples: list[dict] = []

    bearing_delta_values: list[float] = []
    resultant_component_delta_values: list[float] = []
    clarity_delta_values: list[float] = []
    n_matched_cells_both_bearing_defined = 0

    for i, origin in enumerate(dev_origins):
        source_points = _eligible_source_points(repo, origin, disease=DISEASE, active_window_days=ACTIVE_SOURCE_WINDOW_DAYS_7C)
        if not source_points:
            n_origins_no_eligible_source += 1
            continue

        evaluation_domain = build_scientific_evaluation_domain(
            forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, sources=source_points,
            grid_config=grid_config, primary_local_evaluation_distance_km=grid_config.domain_distance_km,
        )
        grid_cells = _grid_cell_dicts(evaluation_domain)
        if not grid_cells:
            n_origins_no_grid += 1
            continue

        n_origins_processed += 1
        c0_scores = score_origin_candidates_7c(grid_cells=grid_cells, sources=source_points, candidates=(_c0_spec,), wind=None)
        c0_by_cell = {c.grid_cell_id: c.score for c in c0_scores[_c0_spec.candidate_id]}

        for cell in grid_cells:
            new_result = compute_cell_direction_tendency_8b3(cell, source_points)
            old_result = compute_cell_direction_tendency(cell, source_points)
            n_cells_processed += 1

            direction_status_counts[new_result.direction_status] = direction_status_counts.get(new_result.direction_status, 0) + 1
            coverage_status_counts[new_result.directional_mass_coverage_status] = coverage_status_counts.get(new_result.directional_mass_coverage_status, 0) + 1
            if new_result.directional_clarity is not None:
                clarity_values.append(new_result.directional_clarity)
            if new_result.directional_input_coverage is not None:
                coverage_values.append(new_result.directional_input_coverage)
            n_exact_zero_distance_cases += new_result.n_zero_distance_undefined_direction_sources

            real_c0_score = c0_by_cell.get(cell["grid_cell_id"])
            if real_c0_score is None or new_result.total_scalar_c0_mass != real_c0_score:
                n_invariant_failures += 1
                if len(invariant_failure_examples) < 5:
                    invariant_failure_examples.append({
                        "forecast_origin_id": origin.forecast_origin_id, "grid_cell_id": cell["grid_cell_id"],
                        "direction_total_scalar_mass": new_result.total_scalar_c0_mass, "real_c0_score": real_c0_score,
                    })

            # old-vs-new diff
            comp_delta = math.hypot(new_result.resultant_east - old_result.resultant_east, new_result.resultant_north - old_result.resultant_north)
            resultant_component_delta_values.append(comp_delta)
            if new_result.directional_clarity is not None and old_result.directional_clarity is not None:
                clarity_delta_values.append(abs(new_result.directional_clarity - old_result.directional_clarity))
            if new_result.bearing_deg is not None and old_result.bearing_deg is not None:
                bearing_delta_values.append(_circular_bearing_delta(new_result.bearing_deg, old_result.bearing_deg))
                n_matched_cells_both_bearing_defined += 1

        if (i + 1) % 100 == 0:
            print(f"  ... {i + 1}/{len(dev_origins)} origins processed, {n_cells_processed} cells so far")

    runtime_seconds = time.monotonic() - t_start

    audit = {
        "protocol_hash_8b3": protocol_hash,
        "n_fit_development_origins_total": len(dev_origins),
        "n_origins_processed": n_origins_processed,
        "n_origins_no_eligible_source": n_origins_no_eligible_source,
        "n_origins_no_grid": n_origins_no_grid,
        "n_cells_processed": n_cells_processed,
        "direction_status_counts": direction_status_counts,
        "coverage_status_counts": coverage_status_counts,
        "directional_clarity_distribution": _percentiles(clarity_values),
        "directional_input_coverage_distribution": _percentiles(coverage_values),
        "n_exact_zero_distance_cases": n_exact_zero_distance_cases,
        "n_invariant_failures": n_invariant_failures,
        "invariant_failure_examples": invariant_failure_examples,
        "runtime_seconds": runtime_seconds,
        "purpose": "STRUCTURAL_IMPLEMENTATION_READINESS_ONLY_NOT_PREDICTIVE_PERFORMANCE",
        "no_target_outcomes_used": True,
        "no_held_out_or_sri_lanka_origins_used": True,
    }

    diff_audit = {
        "label": "HISTORICAL_8B_VS_ACTIVE_8B3_DIFFERENCE_AUDIT",
        "n_cells_compared": n_cells_processed,
        "n_matched_cells_both_bearing_defined": n_matched_cells_both_bearing_defined,
        "bearing_delta_deg_distribution": _percentiles(bearing_delta_values),
        "resultant_component_delta_distribution": _percentiles(resultant_component_delta_values),
        "clarity_absolute_delta_distribution": _percentiles(clarity_delta_values),
    }

    LOCAL_OUT_DIR_8B3.mkdir(parents=True, exist_ok=True)
    _write_json(LOCAL_OUT_DIR_8B3 / "direction_protocol_8b3.json", protocol_dict | {"direction_method_protocol_hash_8b3": protocol_hash})
    _write_json(LOCAL_OUT_DIR_8B3 / "direction_structural_audit_8b3.json", audit)
    _write_json(LOCAL_OUT_DIR_8B3 / "historical_8b_vs_active_8b3_diff_audit.json", diff_audit)

    print(f"\nRuntime: {runtime_seconds:.1f}s")
    print(json.dumps(audit, indent=2, default=str))
    print("\n--- OLD (8B) vs NEW (8B.3) diff audit ---")
    print(json.dumps(diff_audit, indent=2, default=str))
    print(f"\nWrote: {LOCAL_OUT_DIR_8B3}")
