"""FMD-07A-R1: transparent pre-model protocol amendment and candidate-space
freeze.

**`PRE_MODEL_DEVELOPMENT_PROTOCOL_AMENDMENT`** -- explicitly NOT
preregistered. The current repository did not predeclare every FMD-07
candidate-model hyperparameter space (`fmd_model_development.
build_fmd07a_development_protocol_freeze` recorded four genuine gaps).
This module freezes what CAN be defensibly frozen now -- BEFORE any
predictive score, PR-AUC calculation, model fit, hyperparameter
comparison, or weather-window selection -- and leaves what CANNOT be
honestly frozen explicitly BLOCKED, never fabricated.

No model is trained, no validation metric is computed, and no held-out/
Sri-Lanka outcome is inspected anywhere in this module.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .fmd_calibration import FMD_SPATIAL_EVALUATION_RADIUS_KM
from .fmd_model_development import CHECKPOINT as FMD07A_CHECKPOINT

CHECKPOINT = "FMD-07A-R1"
AMENDMENT_STATUS = "PRE_MODEL_DEVELOPMENT_PROTOCOL_AMENDMENT"

# The two FMD-06 numbers this amendment must never silently reuse as a
# kernel-scale candidate (Section 4's explicit prohibitions).
_FMD06_STDBSCAN_EPS_SPACE_KM = 0.236038
_FMD06_LABEL_DEFINITION_RADIUS_KM = FMD_SPATIAL_EVALUATION_RADIUS_KM  # 200.0

THRESHOLD_VALUE_STATUS = "THRESHOLD_VALUE_NOT_SELECTED_PRE_MODEL"
WEATHER_WINNER_STATUS = "NOT_SELECTED"
FMD07_FEATURE_VALUE_STATUS = "FULL_CORPUS_EXTRACTION_NOT_RUN"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Section 4: spatial-baseline kernel-scale candidate registry
# ---------------------------------------------------------------------------


def build_spatial_baseline_kernel_scale_registry() -> dict:
    """A SMALL, deterministic, finite subset of the pre-existing, disease-
    agnostic `services.model_development.domain_design.
    PREDECLARED_DOMAIN_CANDIDATES_KM = (25, 50, 75, 100, 150, 200)`
    registry -- never new numbers invented here. `200.0` (the FMD-06C-PA
    label-definition radius) and any value tied to
    `stdbscan_eps_space_km=0.236038` are deliberately EXCLUDED, so this
    registry can never be read as automatically reusing either frozen
    FMD-06 number as a model hyperparameter. Classified as a
    COMPUTATIONAL MODEL HYPERPARAMETER only -- never a transmission
    distance, spread radius, or biological claim of any kind."""
    candidates_km = (25.0, 50.0, 100.0)
    assert _FMD06_LABEL_DEFINITION_RADIUS_KM not in candidates_km
    assert _FMD06_STDBSCAN_EPS_SPACE_KM not in candidates_km
    return {
        "status": "FMD07A_R1_FROZEN",
        "candidate_kernel_scale_km": list(candidates_km),
        "baseline_families_source": "services.model_development.baseline_registry.BASELINE_CANDIDATES (B0_DISTANCE_ONLY/B1_HOST_DISTANCE_LOG1P/B2_HOST_DISTANCE_ECDF) -- pre-existing, disease-agnostic, reused unchanged",
        "kernel_families_source": "services.hazard.contracts.KernelFamily (EXPONENTIAL/GAUSSIAN) -- pre-existing, disease-agnostic, reused unchanged",
        "kernel_scale_candidate_source": "subset of services.model_development.domain_design.PREDECLARED_DOMAIN_CANDIDATES_KM=(25.0,50.0,75.0,100.0,150.0,200.0)",
        "excluded_values_and_why": {
            "200.0": "the FMD-06C-PA POST_FEASIBILITY_PROTOCOL_AMENDMENT label-definition radius -- excluded so this registry is never read as automatically reusing that value as a model hyperparameter",
            "150.0": "excluded to keep the candidate set small (panel-defensible), while still spanning short/medium/broad scales via the retained 25/50/100 values",
            f"{_FMD06_STDBSCAN_EPS_SPACE_KM}": "the FMD-06B-R ST-DBSCAN eps_space_km value -- never a member of this list, so it can never be silently reused as a kernel-scale candidate",
        },
        "rationale": (
            "Spans short (25km), medium (50km), and broad (100km) local smoothing scales using ONLY "
            "values already present in the pre-existing, disease-agnostic PREDECLARED_DOMAIN_CANDIDATES_KM "
            "registry (frozen at Checkpoint 7A, before any FMD-06/07 result existed) -- no new number is "
            "invented. Fixed before any FMD candidate score is computed; not chosen for PR-AUC; never "
            "derived from held-out or Sri Lanka outcomes; never derived from stdbscan_eps_space_km; never "
            "equal to the amended 200km label-definition radius. Classified as a COMPUTATIONAL MODEL "
            "HYPERPARAMETER only -- not a spread radius, transmission boundary, or biological claim."
        ),
        "total_candidate_grid": {
            "baseline_families": 3,
            "kernel_families": 2,
            "kernel_scales": len(candidates_km),
            "total": 3 * 2 * len(candidates_km),
        },
        "predictive_metrics_used_to_define": False,
    }


# ---------------------------------------------------------------------------
# Section 5: PISTES / hazard candidate space
# ---------------------------------------------------------------------------


def build_pistes_hazard_candidate_status() -> dict:
    """Inspected FIRST (Section 5): `services/hazard/` (`HAZARD_ENGINE_
    PROTOCOL.md`) structurally requires every usable `CellHazardFactors`/
    `SourceHazardFactors` value to carry `status=SOFTWARE_FIXTURE_ONLY` --
    a `REAL` value is refused outright (Checkpoint 6C.5 sec 3). The real
    feature->factor transformer needed to populate `host_factor`/
    `environmental_suitability_factor`/`water_context_factor`/
    `source_strength_factor` from FMD's own extracted features does not
    exist: `FEATURE_ASSEMBLY_PROTOCOL.md` Checkpoint 6D records all three
    (plus `source_strength_factor`) as `NOT_YET_SCIENTIFICALLY_DEFINED`,
    with only `host_density_total` carrying ANY candidate transform (and
    that transform itself is not scientifically selected). Freezing
    coefficient/kernel-scale candidates (`a`/`b` mixing weights, `kappa`
    anisotropy strength, `distance_scale_km`) for an equation that
    structurally cannot receive real inputs today would not be a
    defensible finite candidate space -- it would pretend the equation
    means something it currently cannot compute. Left BLOCKED, per
    Section 5's own explicit instruction not to force every family to
    become runnable."""
    return {
        "status": "BLOCKED",
        "blocked_reason": (
            "services/hazard/ (HAZARD_ENGINE_PROTOCOL.md sec 3, Checkpoint 6C.5) structurally refuses any "
            "CellHazardFactors/SourceHazardFactors value whose status is not SOFTWARE_FIXTURE_ONLY -- a "
            "REAL value is rejected outright. The real feature->factor transformer required to populate "
            "host_factor/environmental_suitability_factor/water_context_factor/source_strength_factor from "
            "FMD's own extracted features does not exist (FEATURE_ASSEMBLY_PROTOCOL.md Checkpoint 6D: all "
            "three remain NOT_YET_SCIENTIFICALLY_DEFINED; source_strength_factor likewise; only "
            "host_density_total has any candidate transform, itself not scientifically selected). "
            "HazardMixConfig.local_weight/anisotropic_weight, anisotropy kappa, and distance_scale_km are "
            "all structurally forbidden from FROZEN_REFERENCE status. Freezing a coefficient candidate "
            "grid for an equation with no real inputs would not be a defensible finite candidate space."
        ),
        "existing_equation_preserved": (
            "H_j_i = a*L_j_i + b*W_j_i; L_j_i = Host_i*Environmental_i*SourceStrength_j*K_local(d_j_i); "
            "W_j_i = WaterContext_i*Host_i*Environmental_i*SourceStrength_j*anisotropy_j_i*wind_speed_factor*"
            "K_wind(d_j_i); H_i = sum_j H_j_i; R_i = 1-exp(-H_i). No sign, feature, or scientific semantic "
            "was changed or reinterpreted by this amendment -- the equation is read, never rewritten."
        ),
        "source": "HAZARD_ENGINE_PROTOCOL.md secs 3, 9, 20; FEATURE_ASSEMBLY_PROTOCOL.md Checkpoint 6D",
        "unblock_condition": (
            "A future, separately-scoped checkpoint must first build and freeze the real feature->factor "
            "transformer (host/environmental/water/source-strength) before any PISTES coefficient candidate "
            "can be defensibly frozen -- never attempted here."
        ),
        "predictive_metrics_used_to_define": False,
    }


# ---------------------------------------------------------------------------
# Section 6: ML candidate family
# ---------------------------------------------------------------------------


def build_ml_candidate_registry() -> dict:
    """A modest, deterministic, panel-defensible registry of standard
    tabular binary-classification algorithms (Section 6). No candidate is
    chosen for observed FMD performance -- none is evaluated in this
    checkpoint. `scikit-learn` is NOT currently a repository dependency
    (`backend/requirements.txt` has no ML library) -- this is recorded
    honestly as a packaging prerequisite, never silently assumed
    available."""
    candidates = [
        {
            "algorithm_family": "LOGISTIC_REGRESSION",
            "hyperparameter_candidates": {"C": [0.1, 1.0, 10.0], "penalty": "l2", "solver": "lbfgs", "max_iter": 1000},
            "hyperparameter_candidate_count": 3,
            "preprocessing_requirements": ["feature scaling required (standardization)"],
            "missing_value_requirements": "requires imputation -- does not handle missing values directly",
            "probability_output_capability": "native (predict_proba)",
            "random_seed_policy": "fixed seed 42 (reuses the repository's own established convention, BASELINE_MODEL_DEVELOPMENT_PROTOCOL.md sec 8 bootstrap CI), never re-seeded to chase a result",
            "class_weight_imbalance_policy": "supports class_weight='balanced' as an optional, FIT_DEVELOPMENT-derived setting; not applied by default (natural balance 58.9%/41.1% is not severely imbalanced)",
            "why_included": "simple, interpretable, natively-calibrated linear baseline; standard first ML candidate for binary risk classification; probability output suits the frozen PR-AUC/Brier/reliability requirements directly",
        },
        {
            "algorithm_family": "RANDOM_FOREST",
            "hyperparameter_candidates": {"n_estimators": [100, 300], "max_depth": [5, 10]},
            "hyperparameter_candidate_count": 4,
            "preprocessing_requirements": [],
            "missing_value_requirements": "requires imputation -- standard RandomForestClassifier does not accept missing values",
            "probability_output_capability": "native (predict_proba)",
            "random_seed_policy": "fixed seed 42",
            "class_weight_imbalance_policy": "supports class_weight='balanced'; not applied by default",
            "why_included": "robust nonlinear tabular baseline; captures feature interactions without manual engineering; low preprocessing burden (no scaling required); standard comparator family",
        },
        {
            "algorithm_family": "GRADIENT_BOOSTED_TREES",
            "hyperparameter_candidates": {"learning_rate": [0.05, 0.1], "max_depth": [3, 5]},
            "hyperparameter_candidate_count": 4,
            "preprocessing_requirements": [],
            "missing_value_requirements": "handles missing values natively (histogram-based implementation) -- no imputation required",
            "probability_output_capability": "native (predict_proba)",
            "random_seed_policy": "fixed seed 42",
            "class_weight_imbalance_policy": "class weighting via sample_weight only; not applied by default",
            "why_included": "strong standard tabular baseline; native missing-value handling matches this project's never-fabricate-a-value discipline particularly well, since real extracted features will carry genuine MISSING/BLOCKED rows",
        },
    ]
    total_candidates = sum(entry["hyperparameter_candidate_count"] for entry in candidates)
    return {
        "status": "FMD07A_R1_FROZEN_PENDING_DEPENDENCY",
        "dependency_status": (
            "scikit-learn is NOT currently listed in backend/requirements.txt -- no dependency was added by "
            "this amendment. These candidates cannot be instantiated until that dependency is added as a "
            "separate, non-scientific, packaging decision."
        ),
        "candidates": candidates,
        "total_hyperparameter_candidate_count": total_candidates,
        "selection_basis": "none -- no candidate was evaluated against FMD data of any role in this checkpoint",
        "predictive_metrics_used_to_define": False,
    }


# ---------------------------------------------------------------------------
# Section 7: hybrid candidate family
# ---------------------------------------------------------------------------


def build_hybrid_candidate_status(pistes_status: dict) -> dict:
    """`FMD_EVALUATION_PROTOCOL.md` sec 6 item 5 defines hybrid as
    "combining (3) and (4)" -- i.e. the PISTES/hazard family (3) and the
    ML family (4), architecture otherwise unspecified. Since PISTES
    remains BLOCKED (Section 5), the hybrid family structurally inherits
    that block -- never fabricated as an ML-only ensemble or any other
    architecture not described by the repository's own definition."""
    if pistes_status["status"] != "BLOCKED":
        raise AssertionError("build_hybrid_candidate_status: PISTES status changed -- hybrid logic must be re-reviewed")
    return {
        "status": "BLOCKED_BY_PISTES",
        "definition_source": "FMD_EVALUATION_PROTOCOL.md sec 6 item 5: 'hybrid (mathematical/PISTES + ML)', architecture unspecified",
        "blocked_reason": (
            "The repository's own definition of the hybrid candidate is a combination of the PISTES/hazard "
            "family and the ML family. PISTES remains BLOCKED (see PISTES candidate status) because the "
            "real feature->factor transformer it requires does not exist. A hybrid candidate necessarily "
            "inherits that block -- it is never redefined as an ML-only ensemble or any other architecture "
            "not described by FMD_EVALUATION_PROTOCOL.md."
        ),
        "gap_name": "FMD07_PROTOCOL_GAP_HYBRID_CANDIDATE_HYPERPARAMETER_SPACE",
        "predictive_metrics_used_to_define": False,
    }


# ---------------------------------------------------------------------------
# Section 8: threshold policy
# ---------------------------------------------------------------------------


def build_threshold_policy() -> dict:
    return {
        "existing_rule": "decision threshold selected on FIT_DEVELOPMENT/validation folds only (FMD_EVALUATION_PROTOCOL.md sec 5) -- no development SELECTION PROCEDURE was previously specified",
        "development_selection_procedure": (
            "For any candidate that requires a single operating threshold (sensitivity/specificity/"
            "precision/F1 reporting only -- PR-AUC/AUROC/Brier/reliability remain threshold-free), the "
            "threshold is selected via nested chronological validation strictly INSIDE FIT_DEVELOPMENT "
            "development folds (VALIDATION_PROTOCOL.md sec 1), never against held-out or Sri Lanka data: "
            "for each usable outer development fold, evaluate a fixed candidate threshold grid (0.05 to "
            "0.95 in steps of 0.05) against that fold's own validation predictions, select the threshold "
            "maximizing F1 within that fold, then report the equal-fold-weighted median selected threshold "
            "across all usable outer folds as the single frozen operating point -- never selected using "
            "accuracy, never tuned after seeing FMD-08's locked result."
        ),
        "threshold_value_status": THRESHOLD_VALUE_STATUS,
        "predictive_metrics_used_to_define": False,
    }


# ---------------------------------------------------------------------------
# Section 9: probability calibration policy
# ---------------------------------------------------------------------------


def build_probability_calibration_policy() -> dict:
    return {
        "existing_requirement": "Brier score + reliability/calibration curve REQUIRED before any risk score is described as a 'probability' (FMD_EVALUATION_PROTOCOL.md sec 5)",
        "development_only_procedure": (
            "If calibration is applied, it is fit using ONLY FIT_DEVELOPMENT training-fold data, nested "
            "inside the same walk-forward structure (VALIDATION_PROTOCOL.md sec 1) -- never fit on "
            "validation, held-out, or Sri Lanka rows. Allowed methods are restricted to standard, "
            "well-established, monotonic calibration techniques (Platt/sigmoid scaling, isotonic "
            "regression); the choice between them, if made, must be based on the FIT_DEVELOPMENT "
            "reliability-curve SHAPE observed within development folds only, never on downstream PR-AUC/"
            "AUROC improvement. Brier score and the reliability curve are reported both pre- and "
            "post-calibration, on FIT_DEVELOPMENT validation folds only."
        ),
        "calibration_fitted_in_this_checkpoint": False,
        "predictive_metrics_used_to_define": False,
    }


# ---------------------------------------------------------------------------
# Section 10: preprocessing / imbalance policy (responsibilities only)
# ---------------------------------------------------------------------------


def build_preprocessing_imbalance_policy(ml_registry: dict) -> dict:
    per_algorithm = {
        entry["algorithm_family"]: {
            "requires_scaling": "feature scaling required" in " ".join(entry["preprocessing_requirements"]),
            "supports_class_weights": "class_weight" in entry["class_weight_imbalance_policy"],
            "handles_missing_values_directly": entry["missing_value_requirements"].startswith("handles missing values natively"),
            "requires_imputation": entry["missing_value_requirements"].startswith("requires imputation"),
        }
        for entry in ml_registry["candidates"]
    }
    return {
        "fitting_scope_rule": (
            "Any imputation, scaling, encoding, feature selection, dimensionality reduction, class "
            "weighting, or resampling parameter is fit on the relevant TRAINING FOLD only, inside nested "
            "FIT_DEVELOPMENT chronological validation -- never globally across all 3,761 origins, never on "
            "validation/held-out/Sri-Lanka rows (FMD_EVALUATION_PROTOCOL.md sec 2)."
        ),
        "imbalance_default": (
            "No imbalance correction is applied by default -- the natural class balance (2,215/3,761 = "
            "58.9% positive, 1,546/3,761 = 41.1% negative) is not severely imbalanced, and the existing "
            "protocol requires any balancing decision to be motivated from FIT_DEVELOPMENT evidence, never "
            "applied speculatively."
        ),
        "per_algorithm_requirements": per_algorithm,
        "predictive_metrics_used_to_define": False,
    }


# ---------------------------------------------------------------------------
# Section 11: CV / early-fold validity policy
# ---------------------------------------------------------------------------


def build_fold_validity_policy(cv_fold_verification: dict) -> dict:
    """Reuses the pre-existing repository convention verbatim
    (`BASELINE_MODEL_DEVELOPMENT_PROTOCOL.md` sec 3:
    "A fold whose training-origin list is empty is reported as
    `INSUFFICIENT_PRIOR_TRAINING_HISTORY` and excluded from evaluation/
    selection") -- extended with the equally structural (never
    performance-based) single-class-validation criterion FMD-07A's own
    `verify_fmd07a_cv_folds` already computed."""
    insufficient = cv_fold_verification["insufficient_folds"]
    return {
        "rule_name": "INSUFFICIENT_PRIOR_TRAINING_HISTORY_OR_SINGLE_CLASS_VALIDATION_EXCLUDED",
        "rule_source": "BASELINE_MODEL_DEVELOPMENT_PROTOCOL.md sec 3 (empty-training-set exclusion, reused verbatim), extended with a single-class-validation exclusion computed structurally from fmd_calendar_year_folds.json + fmd06_risk_origin_labels.csv -- never from any model's predictive performance",
        "rule_definition": (
            "A development fold is excluded from evaluation/selection iff (a) its training-origin list is "
            "empty (INSUFFICIENT_PRIOR_TRAINING_HISTORY), or (b) its validation set has zero positive-class "
            "or zero negative-class origins (SINGLE_CLASS_VALIDATION -- PR-AUC/AUROC are undefined for a "
            "single-class validation set). Both criteria are computed BEFORE any model is fit or scored -- "
            "never a fabricated training set, never a silently-dropped fold."
        ),
        "excluded_folds": insufficient,
        "excluded_fold_count": len(insufficient),
        "total_fold_count": cv_fold_verification["fold_count"],
        "usable_fold_count": cv_fold_verification["fold_count"] - len(insufficient),
        "predictive_metrics_used_to_define": False,
    }


# ---------------------------------------------------------------------------
# Assembly: the machine-readable amendment (Section 12)
# ---------------------------------------------------------------------------


def build_fmd07a_r1_pre_model_protocol_amendment(existing_protocol: dict) -> dict:
    """Assembles the full `fmd07_pre_model_protocol_amendment.json`
    content. `existing_protocol` is the FMD-07A `fmd07_development_
    protocol.json` dict -- read, never regenerated; its primary/secondary
    metrics, CV scheme, weather candidates, and CV-fold verification are
    reused verbatim."""
    spatial_registry = build_spatial_baseline_kernel_scale_registry()
    pistes_status = build_pistes_hazard_candidate_status()
    ml_registry = build_ml_candidate_registry()
    hybrid_status = build_hybrid_candidate_status(pistes_status)
    threshold_policy = build_threshold_policy()
    calibration_policy = build_probability_calibration_policy()
    cv_fold_verification = existing_protocol["cv_scheme"]["verification"]
    preprocessing_policy = build_preprocessing_imbalance_policy(ml_registry)
    fold_validity_policy = build_fold_validity_policy(cv_fold_verification)

    unresolved_after = []
    if pistes_status["status"] == "BLOCKED":
        unresolved_after.append("FMD07_PROTOCOL_GAP_PISTES_HAZARD_COEFFICIENT_CANDIDATES")
    if hybrid_status["status"] == "BLOCKED_BY_PISTES":
        unresolved_after.append("FMD07_PROTOCOL_GAP_HYBRID_CANDIDATE_HYPERPARAMETER_SPACE")

    return {
        "checkpoint": CHECKPOINT,
        "amendment_status": AMENDMENT_STATUS,
        "created_before_any_predictive_model": True,
        "predictive_metrics_used_to_define_candidates": False,
        "held_out_outcomes_used": False,
        "sri_lanka_outcomes_used": False,
        "amendment_provenance_statement": (
            "This amendment was introduced after the FMD-07A protocol audit found four genuine, "
            "unresolved candidate-model hyperparameter-space gaps; before any FMD-07 predictive model was "
            "trained; before any validation PR-AUC, AUROC, or other predictive metric was calculated; "
            "without using held-out outcomes; without using Sri Lanka outcomes; and without inspecting any "
            "comparative model performance. It is explicitly NOT preregistered."
        ),
        "primary_metric": existing_protocol["primary_selection_metric"]["value"],
        "secondary_metrics": existing_protocol["secondary_metrics"]["value"],
        "development_origin_count": 3761,
        "label_positive_count": 2215,
        "label_negative_count": 1546,
        "cv_scheme": existing_protocol["cv_scheme"]["value"],
        "cv_fold_count": cv_fold_verification["fold_count"],
        "purge_embargo": existing_protocol["purge_embargo"]["value"],
        "weather_candidate_registry": existing_protocol["weather_window_candidates"]["value"],
        "weather_winner_status": WEATHER_WINNER_STATUS,
        "candidate_model_families": {
            "naive_statistical_baseline": {"status": "FULLY_SPECIFIED", "source": "FMD_EVALUATION_PROTOCOL.md sec 6 item 1 (unchanged by this amendment)"},
            "spatial_distance_baseline": spatial_registry,
            "pistes_hazard_model": pistes_status,
            "ml_candidate": ml_registry,
            "hybrid_candidate": hybrid_status,
        },
        "threshold_selection_procedure": threshold_policy["development_selection_procedure"],
        "threshold_value_status": threshold_policy["threshold_value_status"],
        "probability_calibration_policy": calibration_policy["development_only_procedure"],
        "preprocessing_policy": preprocessing_policy["fitting_scope_rule"],
        "imbalance_policy": preprocessing_policy["imbalance_default"],
        "per_algorithm_preprocessing_requirements": preprocessing_policy["per_algorithm_requirements"],
        "cv_validity_policy": fold_validity_policy,
        "unresolved_protocol_gaps_after_amendment": unresolved_after,
        "unresolved_protocol_gap_count": len(unresolved_after),
        "feature_extraction_status": FMD07_FEATURE_VALUE_STATUS,
        "provenance": {
            "fmd07a_checkpoint": FMD07A_CHECKPOINT,
            "sources": [
                "FMD_EVALUATION_PROTOCOL.md", "FMD_EXPERIMENT_REGISTRY.json", "MODEL_DEVELOPMENT_PROTOCOL.md",
                "BASELINE_MODEL_DEVELOPMENT_PROTOCOL.md", "FEATURE_ASSEMBLY_PROTOCOL.md",
                "HAZARD_ENGINE_PROTOCOL.md", "VALIDATION_PROTOCOL.md",
                "services/model_development/baseline_registry.py", "services/model_development/candidate_registry_7b.py",
                "services/hazard/kernels.py", "services/hazard/contracts.py",
                "local_data/processed/fmd/model_development/fmd07_development_protocol.json",
            ],
        },
    }


# ---------------------------------------------------------------------------
# Section 13: update fmd07_development_protocol.json (preserve original gaps)
# ---------------------------------------------------------------------------


def update_fmd07_development_protocol_with_amendment(existing_protocol: dict, amendment: dict) -> dict:
    """Never erases the original FMD-07A gap audit -- `original_protocol_
    gap_count`/each gap's `original_status` are preserved unchanged;
    `post_amendment_protocol_gap_count` and each gap's `amended_status`/
    `amendment_source`/`rationale` are added alongside, never in place
    of, the original record."""
    updated = dict(existing_protocol)
    hyperparameter_candidates = dict(updated["hyperparameter_candidates"])

    gap_updates = {
        "FMD-EXP-02_spatial_distance_baseline": {
            "amended_status": "FMD07A_R1_FROZEN",
            "amendment_source": "FMD-07A-R1 fmd07_pre_model_protocol_amendment.json (spatial_distance_baseline)",
            "rationale": amendment["candidate_model_families"]["spatial_distance_baseline"]["rationale"],
        },
        "FMD-EXP-03_pistes_hazard_model": {
            "amended_status": "BLOCKED",
            "amendment_source": "FMD-07A-R1 fmd07_pre_model_protocol_amendment.json (pistes_hazard_model)",
            "rationale": amendment["candidate_model_families"]["pistes_hazard_model"]["blocked_reason"],
        },
        "FMD-EXP-04_ml_candidate": {
            "amended_status": "FMD07A_R1_FROZEN_PENDING_DEPENDENCY",
            "amendment_source": "FMD-07A-R1 fmd07_pre_model_protocol_amendment.json (ml_candidate)",
            "rationale": amendment["candidate_model_families"]["ml_candidate"]["dependency_status"],
        },
        "FMD-EXP-05_hybrid_candidate": {
            "amended_status": "BLOCKED_BY_PISTES",
            "amendment_source": "FMD-07A-R1 fmd07_pre_model_protocol_amendment.json (hybrid_candidate)",
            "rationale": amendment["candidate_model_families"]["hybrid_candidate"]["blocked_reason"],
        },
    }
    for gap_key, gap_update in gap_updates.items():
        entry = dict(hyperparameter_candidates[gap_key])
        entry["original_status"] = entry.get("status")
        entry.update(gap_update)
        hyperparameter_candidates[gap_key] = entry
    updated["hyperparameter_candidates"] = hyperparameter_candidates

    updated["original_protocol_gap_count"] = existing_protocol["unresolved_protocol_gap_count"]
    updated["post_amendment_protocol_gap_count"] = amendment["unresolved_protocol_gap_count"]
    updated["pre_model_protocol_amendment_applied"] = True
    updated["pre_model_protocol_amendment_status"] = amendment["amendment_status"]
    return updated


def run_fmd07a_r1(model_dev_dir: str | Path) -> dict:
    """Reads the frozen FMD-07A `fmd07_development_protocol.json`, builds
    the amendment, writes `fmd07_pre_model_protocol_amendment.json`, and
    updates `fmd07_development_protocol.json` in place (original gap
    audit preserved, amendment fields added). Never runs feature
    extraction, never trains a model, never computes a predictive
    metric."""
    output = Path(model_dev_dir)
    protocol_path = output / "fmd07_development_protocol.json"
    existing_protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if existing_protocol.get("cv_scheme", {}).get("verification") is None:
        raise ValueError("run_fmd07a_r1: fmd07_development_protocol.json has no cv_scheme.verification -- run FMD-07A first")

    amendment = build_fmd07a_r1_pre_model_protocol_amendment(existing_protocol)
    amendment_path = output / "fmd07_pre_model_protocol_amendment.json"
    amendment_path.write_text(json.dumps(amendment, indent=2, sort_keys=True), encoding="utf-8")

    updated_protocol = update_fmd07_development_protocol_with_amendment(existing_protocol, amendment)
    protocol_path.write_text(json.dumps(updated_protocol, indent=2, sort_keys=True), encoding="utf-8")

    return {"amendment": amendment, "protocol": updated_protocol}
