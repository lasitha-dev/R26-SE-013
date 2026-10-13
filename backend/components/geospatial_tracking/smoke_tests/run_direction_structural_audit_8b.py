"""Checkpoint 8B Part 18: real FIT_DEVELOPMENT-only structural readiness
audit of the C0-derived local geometric relative-risk tendency field.

Not a pytest suite. Real DB access over the REAL, runtime-derived
`FIT_DEVELOPMENT` origin universe -- never hardcoded. Run directly:

    python -m components.geospatial_tracking.smoke_tests.run_direction_structural_audit_8b

**Purpose is NOT predictive performance.** No target outcomes, no
held-out origins, no Sri Lanka origins are touched anywhere in this
script -- only implementation/readiness facts about the direction field
computed over real eligible-source geometry and real scientific grids.

For every scored cell, this script also proves the Part 3 scalar
identity against the REAL C0 candidate scorer
(`wind_scoring_7c.score_origin_candidates_7c`, `wind=None`) -- the
`total_scalar_c0_mass` this module computes must equal the real C0
cell score exactly. Any mismatch is a `n_invariant_failures` count,
never silently ignored.

Per Part 19, this script does NOT persist every source term for every
cell (potentially 100k+ across the full universe) -- only aggregate
distributions, a small number of deterministic example cells, and a
per-origin CSV summary.
"""

from __future__ import annotations

import csv
import json
import statistics
import time
from pathlib import Path

from ..config import DEFAULT_SQLITE_DB_PATH
from ..repositories.sqlite_repository import SQLiteOutbreakRepository
from ..services.direction.c0_geometric_tendency import compute_cell_direction_tendency
from ..services.geospatial.raster import LOCAL_GIS_CACHE_DIR
from ..services.forecast_origin import build_forecast_origin_ledger
from ..services.geospatial.scientific_domain import build_scientific_evaluation_domain
from ..services.geospatial.scientific_grid import DOMAIN_MODE_SOURCE_BUFFER_UNION, ScientificGridConfig
from ..services.model_development.candidate_registry_7c import C0_FAMILY, build_candidate_registry_7c
from ..services.model_development.development_run_7b import _eligible_source_points
from ..services.model_development.development_run_7c import _grid_cell_dicts
from ..services.model_development.direction_protocol_8b import direction_method_protocol_dict_8b, direction_method_protocol_hash_8b, verify_8a1_preflight
from ..services.model_development.evaluation_protocol_7c import ACTIVE_SOURCE_WINDOW_DAYS_7C
from ..services.model_development.wind_scoring_7c import score_origin_candidates_7c
from ..services.model_fitting_exposure import fit_development_origins

DISEASE = "Lumpy skin disease"
# Checkpoint 8B.1 Part 4: reuses the SAME canonical repository-root
# local_data helper `run_host_reference_smoke.py` already established
# (`LOCAL_GIS_CACHE_DIR.parent`) -- the original `parents[1]` here
# resolved to `backend/components/geospatial_tracking/local_data/...`
# (an accidental component-nested directory), never the repository
# root every other checkpoint's real local_data artifacts live under
# (`local_data/model_development/{7b,7c}/...`).
LOCAL_DATA_ROOT = LOCAL_GIS_CACHE_DIR.parent
LOCAL_OUT_DIR = LOCAL_DATA_ROOT / "model_development" / "8b_direction"

_c0_spec = next(c for c in build_candidate_registry_7c() if c.family == C0_FAMILY)


def _grid_config() -> ScientificGridConfig:
    return ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)


def _percentiles(values: list[float]) -> dict:
    if not values:
        return {"min": None, "p25": None, "median": None, "p75": None, "p95": None, "max": None, "n": 0}
    s = sorted(values)
    n = len(s)

    def _pct(p: float) -> float:
        if n == 1:
            return s[0]
        idx = p * (n - 1)
        lo, hi = int(idx), min(int(idx) + 1, n - 1)
        frac = idx - lo
        return s[lo] + (s[hi] - s[lo]) * frac

    return {
        "min": s[0], "p25": _pct(0.25), "median": statistics.median(s), "p75": _pct(0.75),
        "p95": _pct(0.95), "max": s[-1], "n": n,
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


if __name__ == "__main__":
    print("Checkpoint 8B Part 0: 8A.1 pre-flight identity check...")
    verify_8a1_preflight()
    protocol_dict = direction_method_protocol_dict_8b()
    protocol_hash = direction_method_protocol_hash_8b()
    print(f"  8A.1 parent hash / 8B protocol hash verified. direction_method_protocol_hash_8b = {protocol_hash}")

    t_start = time.monotonic()
    db_path = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
    repo = SQLiteOutbreakRepository(db_path)

    all_origins = build_forecast_origin_ledger(repo, disease=DISEASE)
    dev_origins = fit_development_origins(all_origins)  # real, runtime-derived -- never hardcoded
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
    eligible_source_counts_by_origin: list[int] = []
    n_exact_zero_distance_cases = 0
    n_invariant_failures = 0
    invariant_failure_examples: list[dict] = []
    example_cells: list[dict] = []
    per_origin_rows: list[dict] = []

    for i, origin in enumerate(dev_origins):
        source_points = _eligible_source_points(repo, origin, disease=DISEASE, active_window_days=ACTIVE_SOURCE_WINDOW_DAYS_7C)
        if not source_points:
            n_origins_no_eligible_source += 1
            per_origin_rows.append({
                "forecast_origin_id": origin.forecast_origin_id, "n_eligible_sources": 0,
                "n_cells": 0, "status": "NO_ELIGIBLE_SOURCE",
            })
            continue

        eligible_source_counts_by_origin.append(len(source_points))

        evaluation_domain = build_scientific_evaluation_domain(
            forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, sources=source_points,
            grid_config=grid_config, primary_local_evaluation_distance_km=grid_config.domain_distance_km,
        )
        grid_cells = _grid_cell_dicts(evaluation_domain)
        if not grid_cells:
            n_origins_no_grid += 1
            per_origin_rows.append({
                "forecast_origin_id": origin.forecast_origin_id, "n_eligible_sources": len(source_points),
                "n_cells": 0, "status": "NO_GRID",
            })
            continue

        n_origins_processed += 1
        c0_scores = score_origin_candidates_7c(grid_cells=grid_cells, sources=source_points, candidates=(_c0_spec,), wind=None)
        c0_by_cell = {c.grid_cell_id: c.score for c in c0_scores[_c0_spec.candidate_id]}

        origin_clarity_values = []
        for cell in grid_cells:
            result = compute_cell_direction_tendency(cell, source_points)
            n_cells_processed += 1
            direction_status_counts[result.direction_status] = direction_status_counts.get(result.direction_status, 0) + 1
            coverage_status_counts[result.directional_mass_coverage_status] = coverage_status_counts.get(result.directional_mass_coverage_status, 0) + 1
            if result.directional_clarity is not None:
                clarity_values.append(result.directional_clarity)
                origin_clarity_values.append(result.directional_clarity)
            if result.directional_input_coverage is not None:
                coverage_values.append(result.directional_input_coverage)
            n_exact_zero_distance_cases += result.n_zero_distance_undefined_direction_sources

            real_c0_score = c0_by_cell.get(cell["grid_cell_id"])
            if real_c0_score is None or result.total_scalar_c0_mass != real_c0_score:
                n_invariant_failures += 1
                if len(invariant_failure_examples) < 5:
                    invariant_failure_examples.append({
                        "forecast_origin_id": origin.forecast_origin_id, "grid_cell_id": cell["grid_cell_id"],
                        "direction_total_scalar_mass": result.total_scalar_c0_mass, "real_c0_score": real_c0_score,
                    })

            if len(example_cells) < 10 and result.n_total_eligible_sources >= 2:
                example_cells.append(result.as_dict())

        per_origin_rows.append({
            "forecast_origin_id": origin.forecast_origin_id, "n_eligible_sources": len(source_points),
            "n_cells": len(grid_cells),
            "median_clarity": statistics.median(origin_clarity_values) if origin_clarity_values else None,
        })

        if (i + 1) % 100 == 0:
            print(f"  ... {i + 1}/{len(dev_origins)} origins processed, {n_cells_processed} cells so far")

    runtime_seconds = time.monotonic() - t_start

    audit = {
        "protocol_hash_8b": protocol_hash,
        "n_fit_development_origins_total": len(dev_origins),
        "n_origins_processed": n_origins_processed,
        "n_origins_no_eligible_source": n_origins_no_eligible_source,
        "n_origins_no_grid": n_origins_no_grid,
        "n_cells_processed": n_cells_processed,
        "direction_status_counts": direction_status_counts,
        "coverage_status_counts": coverage_status_counts,
        "directional_clarity_distribution": _percentiles(clarity_values),
        "directional_input_coverage_distribution": _percentiles(coverage_values),
        "eligible_source_count_distribution": _percentiles([float(x) for x in eligible_source_counts_by_origin]),
        "n_exact_zero_distance_cases": n_exact_zero_distance_cases,
        "n_invariant_failures": n_invariant_failures,
        "invariant_failure_examples": invariant_failure_examples,
        "runtime_seconds": runtime_seconds,
        "purpose": "STRUCTURAL_IMPLEMENTATION_READINESS_ONLY_NOT_PREDICTIVE_PERFORMANCE",
        "no_target_outcomes_used": True,
        "no_held_out_or_sri_lanka_origins_used": True,
    }

    LOCAL_OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(LOCAL_OUT_DIR / "direction_protocol_8b.json", protocol_dict | {"direction_method_protocol_hash_8b": protocol_hash})
    _write_json(LOCAL_OUT_DIR / "direction_structural_audit_8b.json", audit)
    _write_json(LOCAL_OUT_DIR / "direction_example_source_terms_8b.json", {"example_cells": example_cells})

    with (LOCAL_OUT_DIR / "direction_origin_summary_8b.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["forecast_origin_id", "n_eligible_sources", "n_cells", "median_clarity", "status"])
        writer.writeheader()
        for row in per_origin_rows:
            writer.writerow({**{"status": row.get("status", "PROCESSED")}, **row})

    print(f"\nRuntime: {runtime_seconds:.1f}s")
    print(json.dumps(audit, indent=2, default=str))
    print(f"\nWrote: {LOCAL_OUT_DIR}")
