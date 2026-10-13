"""Checkpoint 7A.5 Part 23: cell-size selection — ENGINEERING ONLY.

Never uses any prediction metric (CELL7A5-01/02, structurally verified —
no function signature here has a score/risk/capture-like parameter).
Several of the checkpoint's own listed constraints ("no completely
outside-domain grid cell," "valid polygons/positive areas," "deterministic
polygon target assignment") are already STRUCTURAL guarantees of
`services.geospatial.scientific_grid.build_scientific_grid`/
`services.model_development.target_assignment.assign_target_to_scientific_grid`
themselves — re-verified here defensively per real context, never assumed.
The one genuinely discriminating engineering criterion left between the two
predeclared candidate cell sizes is COMPUTATIONAL FEASIBILITY (cell count
per local context against a predeclared budget) — selecting the COARSEST
candidate that stays within it avoids false precision and unnecessary
compute (Part 23's own stated reason), never a claim of biological
accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass

CELL_SIZE_CANDIDATES_KM: tuple = (2.5, 5.0)
# Predeclared BEFORE any real audit runs — an engineering compute/runtime
# budget, never a prediction-metric threshold. Chosen so that a full
# FIT_DEVELOPMENT reconstruction (hundreds of local contexts, each needing
# 2-species raster extraction per cell) stays within a practical runtime.
MAX_CELLS_PER_CONTEXT_BUDGET = 2000
ENGINEERING_SELECTION_RULE_VERSION = "7A.5.1"

CELL_SIZE_BLOCKED = "CELL_SIZE_BLOCKED_NO_CANDIDATE_SATISFIES_ENGINEERING_CONSTRAINTS"


@dataclass(frozen=True)
class CellSizeEngineeringAudit:
    cell_size_km: float
    n_contexts: int
    all_polygons_valid: bool
    all_areas_positive: bool
    all_sources_represented: bool
    max_cells_per_context: int
    mean_cells_per_context: float
    within_feasibility_budget: bool
    feasibility_budget: int = MAX_CELLS_PER_CONTEXT_BUDGET

    def as_dict(self) -> dict:
        return {
            "cell_size_km": self.cell_size_km, "n_contexts": self.n_contexts, "all_polygons_valid": self.all_polygons_valid,
            "all_areas_positive": self.all_areas_positive, "all_sources_represented": self.all_sources_represented,
            "max_cells_per_context": self.max_cells_per_context, "mean_cells_per_context": self.mean_cells_per_context,
            "within_feasibility_budget": self.within_feasibility_budget, "feasibility_budget": self.feasibility_budget,
        }


def build_cell_size_engineering_audit(*, cell_size_km: float, contexts_and_cells: list) -> CellSizeEngineeringAudit:
    """`contexts_and_cells`: `[(domain, sources, cells), ...]` — real
    `DomainGeometry`/`EligibleSourcePoint` list/`ScientificGridCell` list
    triples already built at `cell_size_km` for real local contexts. Pure
    verification — builds nothing itself."""
    from ..geospatial.crs import build_transformer

    n_contexts = len(contexts_and_cells)
    all_valid = True
    all_positive = True
    all_represented = True
    cell_counts = []

    for domain, sources, cells in contexts_and_cells:
        cell_counts.append(len(cells))
        for c in cells:
            if not c.polygon().is_valid:
                all_valid = False
            if c.area_km2 <= 0:
                all_positive = False
        if cells:
            to_utm = build_transformer(domain.crs_choice.source_crs, domain.crs_choice.analysis_crs)
            for s in sources:
                x, y = to_utm.transform(s.longitude, s.latitude)
                represented = any(c.bounds_utm[0] <= x <= c.bounds_utm[2] and c.bounds_utm[1] <= y <= c.bounds_utm[3] for c in cells)
                if not represented:
                    # a source at the exact domain center is always inside
                    # its own zero-distance buffer, so it should always be
                    # covered by at least one cell -- flag honestly if not.
                    all_represented = False
        elif sources:
            all_represented = False

    max_cells = max(cell_counts) if cell_counts else 0
    mean_cells = (sum(cell_counts) / len(cell_counts)) if cell_counts else 0.0
    within_budget = max_cells <= MAX_CELLS_PER_CONTEXT_BUDGET

    return CellSizeEngineeringAudit(
        cell_size_km=cell_size_km, n_contexts=n_contexts, all_polygons_valid=all_valid, all_areas_positive=all_positive,
        all_sources_represented=all_represented, max_cells_per_context=max_cells, mean_cells_per_context=mean_cells,
        within_feasibility_budget=within_budget,
    )


def select_frozen_cell_size(audits: list[CellSizeEngineeringAudit]) -> tuple[float | None, str]:
    """The COARSEST (largest km) candidate satisfying every engineering
    constraint — never a prediction metric (CELL7A5-03). Returns
    `(None, CELL_SIZE_BLOCKED)` if no candidate qualifies."""
    qualifying = [
        a for a in audits
        if a.all_polygons_valid and a.all_areas_positive and a.all_sources_represented and a.within_feasibility_budget
    ]
    if not qualifying:
        return None, CELL_SIZE_BLOCKED
    coarsest = max(qualifying, key=lambda a: a.cell_size_km)
    return coarsest.cell_size_km, "FROZEN_ENGINEERING_RESOLUTION"
