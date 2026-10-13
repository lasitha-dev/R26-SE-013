"""FMD-07A-R2: forecast-origin feature-assembly preflight.

**Section 0's critical rule, applied**: before any high-volume remote
extraction, this module proves (or honestly fails to prove) the exact
pre-existing rule that maps event/source-level feature values into one
predictor row per forecast origin. It performs NO network access and NO
remote extraction -- it only reads already-inspected repository source
files and documents, and reports whether that mapping rule already
exists.

**Real, repository-sourced finding: the rule does NOT exist.**
`data_processing/build_fmd_features.py`'s own module docstring states
FMD-04 "is explicitly forbidden from building forecast origins, grids, or
anything tied to a future forecasting/clustering checkpoint" and instead
extracts a POINT-level feature attached directly to each canonical
EVENT's own `(latitude, longitude, onset_date)` -- never a forecast
origin. The one place in this repository that DOES define an
origin-level spatial reference (`services/features/assembler.py`'s
`AOI_CENTER` convention, `FEATURE_ASSEMBLY_PROTOCOL.md` sec 4) is
Checkpoint 6A/6C/7C machinery built for LSD's grid/hazard-model workflow
-- the exact machinery FMD-04 was told to avoid -- and even that
convention only resolves WEATHER to one value per origin; it never
defines a multi-source aggregation rule for elevation/host-density/
land-cover/hydrology. `ENVIRONMENTAL_FEATURE_PROTOCOL.md` itself states,
of the closest related question (pre-t0 environmental HISTORY
summarization for a single point), that "the freeze ... fixes the cutoff
safety rule, not the aggregation strategy" and lists multiple candidate
formulations explicitly marked "not yet chosen." No FMD-05/06/07 document
ever revisits or resolves this for FMD's own forecast origins.

Per this checkpoint's own explicit instruction, this finding blocks any
remote extraction in FMD-07A-R2 -- no semantics are invented here.
"""

from __future__ import annotations

import json
from pathlib import Path

CHECKPOINT = "FMD-07A-R2"

RULE_STATUS_UNDEFINED = "UNDEFINED"
BLOCK_NAME = "FORECAST_ORIGIN_FEATURE_ASSEMBLY_RULE_UNDEFINED"


def build_origin_feature_assembly_audit() -> dict:
    """Section 3's exact required audit content. Every field is answered
    from directly-inspected repository source, never guessed. `rule_status
    = "UNDEFINED"` for the fields with no existing repository answer --
    the honest result of the audit, not a placeholder."""
    return {
        "checkpoint": CHECKPOINT,
        "audit_purpose": (
            "Determine whether the repository already contains a sufficiently explicit, scientifically "
            "defensible rule mapping event/source-level feature values into ONE predictor row per forecast "
            "origin, BEFORE any high-volume remote extraction is attempted."
        ),
        "forecast_origin_feature_reference_rule": {
            "status": RULE_STATUS_UNDEFINED,
            "finding": (
                "No FMD document or module defines which spatial location(s) represent a forecast origin's "
                "environmental predictors. FMD-04's own feature pipeline (build_fmd_features.py) operates "
                "purely at the canonical-EVENT level -- one row per event, at that event's own "
                "(latitude, longitude, onset_date) point -- and its module docstring explicitly states FMD-04 "
                "'is explicitly forbidden from building forecast origins, grids, or anything tied to a future "
                "forecasting/clustering checkpoint.'"
            ),
        },
        "source_event_selection_rule": {
            "status": RULE_STATUS_UNDEFINED,
            "finding": (
                "Section 0's open question ('trigger source only? all eligible active sources at t0?') has no "
                "existing FMD-specific answer. The only precedent in this repository -- "
                "services/features/assembler.py's AOI_CENTER definition ('the centroid of the forecast "
                "origin's own TRIGGER sources ... falling back to the centroid of the full active-source set') "
                "-- is Checkpoint 6A/6C/7C machinery built for LSD's grid/hazard-model workflow, the exact "
                "machinery FMD-04's own docstring says FMD must avoid. No FMD-05/06/07 document adopts, "
                "extends, or even references this rule for FMD's own forecast origins."
            ),
        },
        "source_set_semantics": {
            "status": "PARTIALLY_ESTABLISHED",
            "finding": (
                "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0 is frozen as the reference SOURCE SET for FMD's spatial-"
                "domain/target-coverage work (FMD-05R SPATIAL_TARGET_REFERENCE_SOURCE_SET, reused unchanged "
                "through FMD-06). This answers 'which sources are eligible' for spatial-domain purposes, but "
                "no document extends this frozen source SET into an environmental-feature AGGREGATION rule -- "
                "knowing which sources are eligible does not by itself say how their individual feature "
                "values should combine into one origin-level number."
            ),
        },
        "multi_source_aggregation_rule_per_feature_family": {
            "status": RULE_STATUS_UNDEFINED,
            "finding": (
                "No mean/max/min/weighted-mean/nearest-source rule is frozen anywhere in the repository for "
                "any feature family, for FMD forecast origins. ENVIRONMENTAL_FEATURE_PROTOCOL.md, the closest "
                "related document, states explicitly (of the analogous single-point pre-t0 HISTORY "
                "summarization question, not even the multi-source question): 'the freeze above fixes the "
                "cutoff safety rule, not the aggregation strategy' and lists multiple 'Candidate primary "
                "formulations (not yet chosen)' -- confirming this exact class of decision is explicitly, "
                "deliberately still open in this repository, even for the simpler single-point case."
            ),
        },
        "weather_temporal_reference_rule": {
            "status": "PARTIALLY_ESTABLISHED",
            "finding": (
                "For a single EVENT point, FMD-04's build_pre_t0_weather_summary strictly backward-looking "
                "window ending at t0 is frozen and safe (never queries post-t0 data). This has never been "
                "extended to a forecast-origin AOI point or to a multi-source aggregation -- it answers 'what "
                "time window' for one point, not 'which point(s) represent an origin.'"
            ),
        },
        "static_feature_spatial_reference_rule": {
            "status": RULE_STATUS_UNDEFINED,
            "finding": (
                "FMD-04 computes elevation/host-density/land-cover/hydrology at a single EVENT point only. "
                "services/features/assembler.py computes these PER GRID CELL across a spatial grid (LSD's "
                "hazard-model workflow) -- never as a single scalar per origin, and never adopted for FMD. No "
                "rule exists for collapsing either representation into one forecast-origin value for any of "
                "these four families."
            ),
        },
        "missing_source_aggregation_rule": {
            "status": RULE_STATUS_UNDEFINED,
            "finding": "No rule exists, because no source-aggregation rule of any kind exists to have a missing-source case within.",
        },
        "status_aggregation_rule": {
            "status": RULE_STATUS_UNDEFINED,
            "finding": (
                "FMD-04's per-event status taxonomy (SOURCE_VALUE_AVAILABLE/MISSING/OUTSIDE_SOURCE_COVERAGE/"
                "FEATURE_NOT_AVAILABLE/etc., fmd_feature_status.py) is well-defined per EVENT, but no rule "
                "exists for combining several source events' individual statuses into one origin-level status "
                "(e.g. worst-status-wins? majority? per-source list preserved?)."
            ),
        },
        "availability_at_t0_rule": {
            "status": "ESTABLISHED",
            "finding": (
                "source_selector.get_eligible_sources' <=t0 eligibility gate (reused unmodified throughout "
                "FMD-06) and FMD-04's backward-only weather window both independently guarantee no post-t0 "
                "information can enter a predictor. This rule is real and sufficient on its own terms, but "
                "does not by itself resolve which point(s)/sources/aggregation an origin's predictors use."
            ),
        },
        "provenance_source_files_inspected": [
            "data_processing/build_fmd_features.py (module docstring + build_event_feature_row)",
            "data_processing/fmd_feature_registry.py",
            "ENVIRONMENTAL_FEATURE_PROTOCOL.md",
            "FEATURE_ASSEMBLY_PROTOCOL.md (sec 4, AOI_CENTER)",
            "FMD_FEATURE_ELIGIBILITY.csv",
            "FMD_EVALUATION_PROTOCOL.md",
            "FMD_STUDY_PROTOCOL.md sec 7",
            "FMD07_PRE_MODEL_PROTOCOL_AMENDMENT.md",
            "services/fmd_model_development.py",
            "services/fmd_model_development_r1.py",
            "services/source_selector.py",
        ],
        "modelling_row_unit_preserved": "FORECAST_ORIGIN (never converted to source-event rows anywhere in this audit)",
        "overall_rule_status": RULE_STATUS_UNDEFINED,
        "blocking": True,
        "block_name": BLOCK_NAME,
        "recommendation": (
            "A future, separately-scoped checkpoint must explicitly design and freeze the forecast-origin "
            "environmental-feature reference/aggregation rule -- including the spatial reference point(s), "
            "the qualifying source set, the per-family aggregation method, and missing-source/status handling "
            "-- BEFORE any full-corpus remote extraction is attempted for FMD. This must be done deliberately, "
            "never inferred implicitly from extraction convenience, and never invented inside a remote-"
            "extraction checkpoint itself."
        ),
        "predictive_metrics_used_to_define": False,
        "held_out_outcomes_used": False,
        "sri_lanka_outcomes_used": False,
    }


def run_fmd07a_r2_preflight(out_dir: str | Path) -> dict:
    """Writes the Section-3 audit artifact. Performs NO network access.
    Does not proceed to Sections 5+ (extraction planning/canary/full
    extraction) because the audit's own `overall_rule_status` is
    `UNDEFINED` -- per Section 4's explicit instruction, this checkpoint
    stops here."""
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    audit = build_origin_feature_assembly_audit()
    audit_path = output / "fmd07a_r2_origin_feature_assembly_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
    return {"audit": audit, "audit_path": str(audit_path)}
