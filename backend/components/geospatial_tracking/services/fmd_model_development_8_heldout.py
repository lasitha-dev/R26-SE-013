"""FMD-08 / FMD-EXP-06: locked HELD_OUT_FROM_MODEL_FITTING evaluation.

This module is the held-out-only mirror image of the FIT_DEVELOPMENT-only
label chain in ``fmd_calibration.py`` (``build_fmd06c_pa_local_domain_audit``,
``build_fmd06d_risk_origin_labels``) and of the FIT_DEVELOPMENT-only
extraction/scoring chain in ``model_development/fold_reference.py`` and
``fmd_model_development_7b.py``. Those functions hard-firewall themselves to
FIT_DEVELOPMENT (``assert_fit_development_only`` at their own entry point) by
design -- held-out outcomes must stay unopened until this checkpoint. This
module does not weaken or call into any of those firewalled functions with
held-out data; it re-implements the same deterministic definitions, applying
only the already-frozen radius/window/candidate parameters, firewalled the
opposite way with ``assert_held_out_only``.

No candidate selection, hyperparameter tuning, feature selection, threshold
optimization, calibration fitting, radius tuning, or weather-window tuning
happens anywhere in this module. The candidate is the single FMD-07B winner
frozen in ``fmd07b_frozen_model_spec.json``; the classification threshold
(where used) is that frozen spec's threshold, never re-derived here; the
evaluation radius (200km) and active-window (14 days) are the same frozen
FMD-06 calibration values already used for FIT_DEVELOPMENT, applied
unchanged.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from ..domain.enums import RecordDomainScope
from ..schemas import ValidationMode
from .fmd_calibration import (
    FMD_MODEL_FITTING_CUTOFF,
    FMD_SPATIAL_EVALUATION_RADIUS_KM,
    PRIMARY_TARGET_HORIZON,
    SPATIAL_PROTOCOL_AMENDMENT_STATUS,
    SPATIAL_REFERENCE_SOURCE_SET,
    load_forecast_origins,
)
from .forecast_origin import ForecastOrigin
from .forecast_target import build_forecast_targets
from .geospatial.distance import distance_km
from .geospatial.scientific_domain import build_scientific_evaluation_domain
from .geospatial.scientific_grid import ScientificGridConfig
from .geospatial.source_geometry import EligibleSourcePoint
from .model_fitting_exposure import (
    assert_held_out_only,
    classify_origin_role,
    held_out_from_model_fitting_origins,
)
from .source_selector import get_eligible_sources
from .fmd_model_development_7b import BaselineCandidateSpec, build_fmd_spatial_candidate_specs
from .fmd_model_development_7b_exp02_origin import (
    FMD07B_EXP02_ENGINEERING_GRID_SIZE_KM,
    Exp02OriginCandidatePrediction,
    aggregate_exp02_origin_cell_scores,
)
from .model_development.baseline_scoring import score_origin_all_candidates
from .model_development.domain_design import PREDECLARED_DOMAIN_CANDIDATES_KM, TargetDomainCoverage
from .model_development.fold_reference import (
    _cache_path,
    _load_cache_entry,
    _snapshot_with_unsafe_component_count,
    _write_cache_entry,
    raw_snapshot_cache_identity_hash,
    raw_snapshot_cache_identity_payload,
    snapshot_unsafe_component_count,
)
from .model_development.host_reference_rebuild import DEFAULT_SPECIES, build_scientific_grid_host_only_snapshot

CHECKPOINT_08 = "FMD-08"
EXPERIMENT_ID_06 = "FMD-EXP-06"
LOCKED_EVALUATION_BLOCK_ID = "LOCKED_HELD_OUT_FROM_MODEL_FITTING_SINGLE_BLOCK"
EXPECTED_HELD_OUT_COHORT_COUNT = 541


class Fmd08IntegrityError(RuntimeError):
    """FMD-08 held-out evaluation verification failed."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def compute_cohort_sha256(forecast_origin_ids: Sequence[str]) -> str:
    ids = sorted(set(forecast_origin_ids))
    if len(ids) != len(forecast_origin_ids):
        raise Fmd08IntegrityError("held-out cohort contains a duplicate forecast_origin_id")
    return hashlib.sha256(_canonical_json(ids)).hexdigest()


# ---------------------------------------------------------------------------
# B. Cohort firewall + identity verification
# ---------------------------------------------------------------------------


def load_locked_held_out_origins(
    repo_root: Path,
    *,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
    expected_count: int = EXPECTED_HELD_OUT_COHORT_COUNT,
) -> tuple[tuple[ForecastOrigin, ...], str]:
    """Load and firewall the exact HELD_OUT_FROM_MODEL_FITTING cohort.

    Fails closed if the observed count disagrees with the caller-supplied
    ``expected_count`` (the caller is responsible for cross-checking that
    value against the current FMD_EXPERIMENT_REGISTRY.json /
    FMD_COHORT_MANIFEST.json before calling this). Sri Lanka and
    FIT_DEVELOPMENT origins can never be returned here.
    """
    origins_path = Path(repo_root) / "local_data/processed/fmd/cohort/fmd_historical_forecast_origins.csv"
    all_origins = load_forecast_origins(origins_path)
    held_out = held_out_from_model_fitting_origins(all_origins, cutoff=cutoff)
    assert_held_out_only(held_out, cutoff=cutoff, caller="load_locked_held_out_origins")

    ids = [o.forecast_origin_id for o in held_out]
    if len(ids) != len(set(ids)):
        raise Fmd08IntegrityError("held-out cohort contains a duplicate forecast_origin_id")
    if len(held_out) != expected_count:
        raise Fmd08IntegrityError(
            f"held-out cohort count mismatch: observed {len(held_out)}, expected {expected_count}"
        )
    cohort_sha256 = compute_cohort_sha256(ids)
    return tuple(sorted(held_out, key=lambda o: o.forecast_origin_id)), cohort_sha256


def verify_frozen_model_identity(repo_root: Path, *, canon_dir: Path | None = None) -> dict:
    """Load and verify FMD-07B's frozen model spec against its own manifest
    provenance hash. Raises if the selected candidate is inconsistent across
    the canonical selection summary / frozen spec / manifest, or if the
    frozen spec file's SHA-256 does not match what the manifest recorded at
    write time (FMD-07B was already validated in Phase A; this only re-checks
    that the on-disk files were not altered since).

    ``canon_dir`` defaults to the original FMD-07B canonical directory
    (unchanged behavior); FMD-10A's procedural correction (fold-retention
    fix) wrote a superseding frozen spec under a separate
    ``fmd10a_corrected_selection`` directory rather than overwriting the
    original, so FMD-10B passes that directory explicitly here to bind the
    held-out evaluation to the corrected candidate instead."""
    if canon_dir is None:
        canon_dir = Path(repo_root) / "local_data/processed/fmd/model_development"
    spec_path = canon_dir / "fmd07b_frozen_model_spec.json"
    manifest_path = canon_dir / "fmd07b_manifest.json"
    summary_path = canon_dir / "fmd07b_candidate_selection_summary.json"

    spec_bytes = spec_path.read_bytes()
    spec = json.loads(spec_bytes.decode("utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    recorded_sha256 = manifest.get("output_artifact_sha256", {}).get("fmd07b_frozen_model_spec.json")
    observed_sha256 = _sha256_bytes(spec_bytes)
    if recorded_sha256 != observed_sha256:
        raise Fmd08IntegrityError(
            "fmd07b_frozen_model_spec.json SHA-256 does not match fmd07b_manifest.json's recorded provenance "
            f"(recorded={recorded_sha256!r}, observed={observed_sha256!r})"
        )
    if manifest.get("held_out_used") is not False or manifest.get("sri_lanka_used") is not False:
        raise Fmd08IntegrityError("fmd07b_manifest.json does not record held_out_used=False/sri_lanka_used=False")

    candidate_id = spec.get("selected_candidate_id")
    if not candidate_id or candidate_id != summary.get("selected_candidate_id"):
        raise Fmd08IntegrityError(
            "selected_candidate_id mismatch between fmd07b_frozen_model_spec.json and "
            "fmd07b_candidate_selection_summary.json"
        )
    threshold = spec.get("threshold")
    if not isinstance(threshold, (int, float)):
        raise Fmd08IntegrityError("fmd07b_frozen_model_spec.json threshold is not a number")

    return {
        "selected_candidate_id": candidate_id,
        "threshold": float(threshold),
        "frozen_model_spec_sha256": observed_sha256,
        "primary_selection_metric_value": summary.get("selected_primary_metric_value"),
    }


def resolve_frozen_candidate_spec(candidate_id: str) -> BaselineCandidateSpec:
    """The one frozen candidate's math spec, from the same frozen registry
    builder real EXP-02 execution used -- never a hand-built substitute."""
    for candidate in build_fmd_spatial_candidate_specs():
        if candidate.candidate_id == candidate_id:
            return candidate
    raise Fmd08IntegrityError(f"frozen candidate_id {candidate_id!r} not found in the frozen EXP-02 spatial registry")


# ---------------------------------------------------------------------------
# D. Held-out label chain (mirrors fmd_calibration.py's FIT_DEVELOPMENT chain)
# ---------------------------------------------------------------------------


def build_heldout_target_domain_coverage(
    repo,
    *,
    held_out_origins: Sequence[ForecastOrigin],
    disease: str,
    active_window_days: int,
    radius_km: float = FMD_SPATIAL_EVALUATION_RADIUS_KM,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
) -> list[TargetDomainCoverage]:
    """Held-out mirror of ``domain_design.build_development_domain_candidate_audit``,
    restricted to the single already-frozen evaluation radius (never a
    candidate sweep -- the radius was selected once, from FIT_DEVELOPMENT
    only, and is only ever applied here)."""
    assert_held_out_only(held_out_origins, cutoff=cutoff, caller="build_heldout_target_domain_coverage")
    if radius_km not in PREDECLARED_DOMAIN_CANDIDATES_KM:
        raise Fmd08IntegrityError(f"radius_km={radius_km} is not one of the predeclared candidates")

    rows: list[TargetDomainCoverage] = []
    for origin in sorted(held_out_origins, key=lambda o: o.forecast_origin_id):
        result = get_eligible_sources(
            repo, disease=disease, t0=origin.t0, active_window_days=active_window_days,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, country_scope=origin.country,
            domain_scope=RecordDomainScope.HISTORICAL_ONLY,
        )
        sources = result.sources
        targets = build_forecast_targets(repo, origin, disease=disease, source_ids_at_origin={s.source_id for s in sources})
        for t in sorted(targets, key=lambda t: t.target_id):
            if not t.risk_target_eligible:
                continue
            if sources:
                min_d = min(distance_km(s.latitude, s.longitude, t.latitude, t.longitude) for s in sources)
            else:
                min_d = None
            covered = {radius_km: (min_d is not None and min_d <= radius_km)}
            rows.append(TargetDomainCoverage(
                forecast_origin_id=origin.forecast_origin_id, target_id=t.target_id, target_event_id=t.target_event_id,
                lead_days=t.lead_days, min_distance_to_eligible_source_km=min_d, covered_by_candidate_km=covered,
            ))
    return rows


def build_heldout_local_domain_audit(
    held_out_origins: Sequence[ForecastOrigin],
    coverage_rows: Sequence[TargetDomainCoverage],
    *,
    radius_km: float = FMD_SPATIAL_EVALUATION_RADIUS_KM,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
) -> list[dict]:
    """Held-out mirror of ``fmd_calibration.build_fmd06c_pa_local_domain_audit``:
    identical per-origin projection rule, firewalled to held-out instead."""
    assert_held_out_only(held_out_origins, cutoff=cutoff, caller="build_heldout_local_domain_audit")

    by_origin: dict[str, list[TargetDomainCoverage]] = {}
    for row in coverage_rows:
        by_origin.setdefault(row.forecast_origin_id, []).append(row)

    rows: list[dict] = []
    for origin in sorted(held_out_origins, key=lambda o: o.forecast_origin_id):
        target_rows = by_origin.get(origin.forecast_origin_id, [])
        n_within = sum(1 for row in target_rows if row.covered_by_candidate_km[radius_km])
        n_outside = len(target_rows) - n_within
        rows.append({
            "forecast_origin_id": origin.forecast_origin_id,
            "country": origin.country,
            "t0": origin.t0,
            "has_eligible_d1_d7_target": bool(target_rows),
            "n_eligible_d1_d7_targets": len(target_rows),
            "n_targets_within_local_domain": n_within,
            "n_targets_outside_local_domain": n_outside,
            "local_domain_positive": n_within > 0,
            "outside_domain_target_present": n_outside > 0,
        })
    return rows


def build_heldout_risk_origin_labels(
    held_out_origins: Sequence[ForecastOrigin],
    local_domain_audit_rows: Sequence[Mapping],
    *,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
    radius_km: float = FMD_SPATIAL_EVALUATION_RADIUS_KM,
) -> list[dict]:
    """Held-out mirror of ``fmd_calibration.build_fmd06d_risk_origin_labels``:
    identical one-row-per-origin label projection, firewalled to held-out."""
    assert_held_out_only(held_out_origins, cutoff=cutoff, caller="build_heldout_risk_origin_labels")

    origin_by_id = {o.forecast_origin_id: o for o in held_out_origins}
    audit_by_id = {row["forecast_origin_id"]: row for row in local_domain_audit_rows}
    origin_ids = set(origin_by_id)
    audit_ids = set(audit_by_id)
    if origin_ids != audit_ids:
        missing = sorted(origin_ids - audit_ids)
        extra = sorted(audit_ids - origin_ids)
        raise Fmd08IntegrityError(
            "build_heldout_risk_origin_labels: held-out origins do not exactly match the local-domain audit rows -- "
            f"{len(missing)} missing (e.g. {missing[:5]}), {len(extra)} extra (e.g. {extra[:5]})"
        )

    def _as_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() == "true"
        return bool(value)

    rows: list[dict] = []
    for origin_id in sorted(origin_ids):
        origin = origin_by_id[origin_id]
        audit_row = audit_by_id[origin_id]
        positive = _as_bool(audit_row["local_domain_positive"])
        rows.append({
            "forecast_origin_id": origin_id,
            "country": origin.country,
            "t0": origin.t0,
            "model_fitting_role": classify_origin_role(origin, cutoff=cutoff),
            "risk_target_label": 1 if positive else 0,
            "has_eligible_d1_d7_target": _as_bool(audit_row["has_eligible_d1_d7_target"]),
            "outside_domain_target_present": _as_bool(audit_row["outside_domain_target_present"]),
            "local_evaluation_radius_km": radius_km,
            "target_horizon": PRIMARY_TARGET_HORIZON,
            "spatial_reference_source_set": SPATIAL_REFERENCE_SOURCE_SET,
            "spatial_protocol_amendment_status": SPATIAL_PROTOCOL_AMENDMENT_STATUS,
        })
    return rows


# ---------------------------------------------------------------------------
# Held-out raw host snapshot extraction (mirrors fold_reference.py, cache-resumable)
# ---------------------------------------------------------------------------


def build_heldout_raw_host_snapshots_cached(
    repo,
    *,
    held_out_origins: Sequence[ForecastOrigin],
    disease: str,
    active_window_days: int,
    grid_config: ScientificGridConfig,
    cache_dir: Path,
    species: tuple = DEFAULT_SPECIES,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
) -> tuple[dict, dict]:
    """Held-out mirror of ``model_development.fold_reference.build_raw_host_snapshots_cached``:
    identical per-origin extraction and disk-cache identity/validation logic,
    firewalled to held-out and using a dedicated FMD-08 cache directory (never
    the FIT_DEVELOPMENT-scoped LSD cache or the EXP-02 cache). Origins are
    processed and cached one at a time so a partial run resumes from disk on
    retry without recomputing already-cached entries or holding the full
    541-origin snapshot set in memory at once beyond what the caller retains."""
    assert_held_out_only(held_out_origins, cutoff=cutoff, caller="build_heldout_raw_host_snapshots_cached")
    cache_dir.mkdir(parents=True, exist_ok=True)

    snapshots: dict = {}
    n_hits = n_misses = n_no_sources = n_identity_mismatches = n_with_unsafe = 0
    unsafe_component_count = 0
    for origin in sorted(held_out_origins, key=lambda o: o.forecast_origin_id):
        result = get_eligible_sources(
            repo, disease=disease, t0=origin.t0, active_window_days=active_window_days,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, country_scope=origin.country,
            domain_scope=RecordDomainScope.HISTORICAL_ONLY,
        )
        if not result.sources:
            n_no_sources += 1
            continue
        source_points = [EligibleSourcePoint(source_id=s.source_id, latitude=s.latitude, longitude=s.longitude) for s in result.sources]
        evaluation_domain = build_scientific_evaluation_domain(
            forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, sources=source_points, grid_config=grid_config,
            primary_local_evaluation_distance_km=grid_config.domain_distance_km,
        )
        identity = raw_snapshot_cache_identity_payload(
            forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, country=origin.country, disease=disease,
            active_window_days=active_window_days, species=species,
            scientific_evaluation_domain_id=evaluation_domain.scientific_evaluation_domain_id,
        )
        path = _cache_path(cache_dir, raw_snapshot_cache_identity_hash(identity))
        cached_snapshot, outcome = _load_cache_entry(path, expected_identity=identity)
        if outcome == "HIT":
            snapshots[origin.forecast_origin_id] = cached_snapshot
            cached_unsafe = snapshot_unsafe_component_count(cached_snapshot)
            unsafe_component_count += cached_unsafe
            n_with_unsafe += int(cached_unsafe > 0)
            n_hits += 1
            continue
        if outcome == "CACHE_IDENTITY_MISMATCH":
            n_identity_mismatches += 1

        snap, n_unsafe = build_scientific_grid_host_only_snapshot(
            repo, origin=origin, disease=disease, active_window_days=active_window_days, grid_config=grid_config, species=species,
        )
        if snap is not None:
            snap = _snapshot_with_unsafe_component_count(snap, n_unsafe)
            snapshots[origin.forecast_origin_id] = snap
            _write_cache_entry(path, snapshot=snap, identity=identity)
            unsafe_component_count += n_unsafe
            n_with_unsafe += int(n_unsafe > 0)
        n_misses += 1

    return snapshots, {
        "n_cache_hits": n_hits, "n_cache_misses": n_misses, "n_origins_no_eligible_source": n_no_sources,
        "n_cache_identity_mismatches": n_identity_mismatches,
        "n_origins_with_unsafe_components": n_with_unsafe,
        "unsafe_component_count": unsafe_component_count,
    }


# ---------------------------------------------------------------------------
# E. Single frozen-candidate scoring (no selection, no reference-profile
#    fitting -- the frozen candidate's own math never reads reference_profile
#    when host_factor_candidate is None, verified structurally below)
# ---------------------------------------------------------------------------


def score_heldout_origin_frozen_candidate(
    *,
    forecast_origin_id: str,
    grid_cells: list[dict],
    sources: list,
    frozen_candidate: BaselineCandidateSpec,
    unsafe_component_count: int = 0,
) -> Exp02OriginCandidatePrediction:
    """Score exactly one origin against the single frozen candidate, reusing
    the unchanged EXP-02 cell-scoring and origin-aggregation math directly
    (bypassing only the FIT_DEVELOPMENT-only ``Fmd07bFoldInput``/
    ``SpatialDistanceRunner.score_validation_origin`` wrapper, which is a
    role firewall around this same math, not the math itself)."""
    if frozen_candidate.host_factor_candidate is not None:
        raise Fmd08IntegrityError(
            "score_heldout_origin_frozen_candidate: this module never builds a held-out reference profile; "
            "the frozen candidate must have host_factor_candidate=None"
        )
    per_cell_by_candidate = score_origin_all_candidates(
        grid_cells=grid_cells, sources=sources, candidates=(frozen_candidate,),
        reference_profile=None, transform_config=None, unsafe_component_count=unsafe_component_count,
    )
    cell_scores = per_cell_by_candidate[frozen_candidate.candidate_id]
    return aggregate_exp02_origin_cell_scores(
        fold_id=LOCKED_EVALUATION_BLOCK_ID,
        candidate_id=frozen_candidate.candidate_id,
        forecast_origin_id=forecast_origin_id,
        cell_scores=cell_scores,
        unsafe_component_count=unsafe_component_count,
        engineering_grid_size_km=FMD07B_EXP02_ENGINEERING_GRID_SIZE_KM,
    )


# ---------------------------------------------------------------------------
# F. Locked metrics -- frozen threshold only, never searched/optimized here
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LockedEvaluationMetrics:
    n_scored: int
    n_unscored: int
    pr_auc: float | None
    auroc: float | None
    brier_score: float | None
    threshold: float
    f1_at_threshold: float | None
    precision_at_threshold: float | None
    recall_at_threshold: float | None
    specificity_at_threshold: float | None

    def as_dict(self) -> dict:
        return {
            "n_scored": self.n_scored, "n_unscored": self.n_unscored,
            "pr_auc": self.pr_auc, "auroc": self.auroc, "brier_score": self.brier_score,
            "threshold": self.threshold, "f1_at_threshold": self.f1_at_threshold,
            "precision_at_threshold": self.precision_at_threshold,
            "recall_at_threshold": self.recall_at_threshold,
            "specificity_at_threshold": self.specificity_at_threshold,
        }


def compute_locked_evaluation_metrics(
    y_true: Sequence[int], y_score: Sequence[float], *, threshold: float, n_unscored: int,
) -> LockedEvaluationMetrics:
    """PR-AUC/AUROC/Brier (calibration diagnostic) + confusion-matrix metrics
    AT the frozen development threshold only -- no threshold grid, no search,
    no re-derivation from held-out outcomes anywhere in this function."""
    n_scored = len(y_true)
    if n_scored < 2 or len(set(y_true)) < 2:
        return LockedEvaluationMetrics(
            n_scored=n_scored, n_unscored=n_unscored, pr_auc=None, auroc=None, brier_score=None,
            threshold=threshold, f1_at_threshold=None, precision_at_threshold=None,
            recall_at_threshold=None, specificity_at_threshold=None,
        )

    pr_auc = float(average_precision_score(y_true, y_score))
    auroc = float(roc_auc_score(y_true, y_score))
    try:
        brier = float(brier_score_loss(y_true, y_score))
    except ValueError:
        # The frozen candidate emits an unbounded ranking score, not a
        # [0, 1] probability -- Brier is mathematically undefined for it,
        # exactly as already established (and left undefined, never
        # rescaled) for this same candidate family in FMD-07B Phase A.
        brier = None

    y_pred = [1 if s >= threshold else 0 for s in y_score]
    precision = float(precision_score(y_true, y_pred, zero_division=0))
    recall = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    specificity = (tn / (tn + fp)) if (tn + fp) > 0 else None

    return LockedEvaluationMetrics(
        n_scored=n_scored, n_unscored=n_unscored, pr_auc=pr_auc, auroc=auroc, brier_score=brier,
        threshold=threshold, f1_at_threshold=f1, precision_at_threshold=precision,
        recall_at_threshold=recall, specificity_at_threshold=specificity,
    )
