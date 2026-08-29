"""Checkpoint 7C Parts 3, 8-9, 13: candidate scoring.

C0 (Part 3): `score_i = sum_j K_EXPONENTIAL(d_j_i; 25km)` -- byte-for-byte
the same formula as the frozen Checkpoint 7B B0 baseline (7C-MATH-01
proves this numerically against real 7B output).

CW(mode, kappa) (Part 8-9, 13): each source's kernel contribution is
multiplied by that SOURCE's own anisotropy factor BEFORE the sources are
summed (7C-MATH-03) --

    score_i = sum_j [ K_EXPONENTIAL(d_j_i; 25km) * A(alignment_j_i, kappa; mode) ]

`alignment_j_i` comes from `services.hazard.anisotropy.compute_meteorological_alignment`,
fed the SAME per-source `t_hat_east`/`t_hat_north` geometry
(`services.geospatial.distance.source_to_cell_unit_vector`) every other
per-source computation in this repository already uses -- never a
"nearest source" shortcut (7C-MATH-04), never gated by ST cluster
membership (7C-MATH-05). `A` itself comes from
`services.hazard.anisotropy.compute_anisotropy_factor` -- no second
anisotropy formula is written here (Part 9).

A cell's wind-candidate score is `MODEL_INPUT_INCOMPLETE` for every
source only when the ORIGIN's own wind vector could not be resolved at
all (`WEATHER_INPUT_UNAVAILABLE`, Part 18) -- never replaced with a
fabricated calm/neutral/previous-day value. A genuinely resolved
real-but-calm wind reading is a scientifically different state (handled
by `compute_meteorological_alignment` itself, `CALM_NEUTRAL`, factor
exactly `1.0`) and still produces a real `SCORED` cell.
"""

from __future__ import annotations

from ..geospatial.distance import distance_km, source_to_cell_unit_vector
from ..geospatial.source_geometry import EligibleSourcePoint
from ..hazard.anisotropy import compute_anisotropy_factor, compute_meteorological_alignment
from ..hazard.contracts import WindVector
from ..hazard.kernels import evaluate_kernel
from .baseline_scoring import SCORED, CellScore
from .candidate_registry_7c import C0_FAMILY, CW_FAMILY, FROZEN_KERNEL_FAMILY, FROZEN_KERNEL_SCALE_KM, Candidate7CSpec

MODEL_INPUT_INCOMPLETE = "MODEL_INPUT_INCOMPLETE"


def _cell_dict_fields(cell: dict) -> dict:
    return {
        "grid_cell_id": cell["grid_cell_id"], "scientific_cell_id": cell.get("scientific_cell_id"),
        "area_km2": cell["area_km2"], "domain_overlap_area_km2": cell["domain_overlap_area_km2"],
    }


def score_origin_candidates_7c(
    *, grid_cells: list[dict], sources: list[EligibleSourcePoint], candidates: tuple[Candidate7CSpec, ...],
    wind: WindVector | None,
) -> dict[str, list[CellScore]]:
    """`grid_cells`: dicts with `grid_cell_id`, `centroid_lat/lon`,
    `area_km2`, `domain_overlap_area_km2` (from
    `scientific_domain.ScientificEvaluationDomain.all_cells()`).
    `wind`: the origin's REAL AOI-center wind vector, or `None` if
    unresolved (`WEATHER_INPUT_UNAVAILABLE`) -- every wind candidate is
    `MODEL_INPUT_INCOMPLETE` for every cell in that case; C0 is entirely
    unaffected (it never reads `wind` at all)."""
    # distances/kernel sum computed ONCE per cell, shared by C0 and every
    # wind candidate (all frozen at the same EXPONENTIAL/25km kernel).
    per_cell_kernel_sum: dict[str, float] = {}
    per_cell_source_terms: dict[str, list[tuple[float, float, float]]] = {}  # (kernel_value, t_hat_east, t_hat_north)
    for cell in grid_cells:
        gcid = cell["grid_cell_id"]
        terms = []
        ksum = 0.0
        for s in sources:
            vec = source_to_cell_unit_vector(s.latitude, s.longitude, cell["centroid_lat"], cell["centroid_lon"])
            k = evaluate_kernel(vec.distance_km, family=FROZEN_KERNEL_FAMILY, distance_scale_km=FROZEN_KERNEL_SCALE_KM)
            ksum += k
            terms.append((k, vec.t_hat_east, vec.t_hat_north))
        per_cell_kernel_sum[gcid] = ksum
        per_cell_source_terms[gcid] = terms

    results: dict[str, list[CellScore]] = {}
    for candidate in candidates:
        cell_scores: list[CellScore] = []
        for cell in grid_cells:
            gcid = cell["grid_cell_id"]
            if candidate.family == C0_FAMILY:
                score, status = per_cell_kernel_sum[gcid], SCORED
            elif wind is None:
                score, status = None, MODEL_INPUT_INCOMPLETE
            else:
                total = 0.0
                for k, t_hat_east, t_hat_north in per_cell_source_terms[gcid]:
                    alignment = compute_meteorological_alignment(t_hat_east=t_hat_east, t_hat_north=t_hat_north, wind=wind)
                    aniso = compute_anisotropy_factor(alignment, kappa=candidate.anisotropy_kappa, mode=candidate.anisotropy_mode)
                    total += k * aniso.anisotropy_factor
                score, status = total, SCORED
            cell_scores.append(CellScore(status=status, score=score, **_cell_dict_fields(cell)))
        results[candidate.candidate_id] = cell_scores
    return results
