"""Pre-exposure gate for FMD-08 / FMD-EXP-06 locked held-out evaluation.

Synthetic-fixture tests only -- no real held-out label or outcome is read
here. Proves: (B) the held-out cohort firewall rejects FIT_DEVELOPMENT,
Sri Lanka, mixed, and duplicate input; (C) frozen parameters (candidate
math, threshold) are never re-derived; (D) the held-out label chain
reproduces the exact same per-origin projection rule as the FIT_DEVELOPMENT
chain in fmd_calibration.py, on identical synthetic coverage input; (E) no
selection/tuning/threshold-optimization/calibration-fitting path exists in
this module; (F) artifact-identity primitives (cohort SHA, frozen-spec SHA
verification) are deterministic and fail closed.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from components.geospatial_tracking.services.fmd_calibration import (
    build_fmd06c_pa_local_domain_audit,
    build_fmd06d_risk_origin_labels,
)
from components.geospatial_tracking.services.fmd_model_development_7b import BaselineCandidateSpec
from components.geospatial_tracking.services.fmd_model_development_8_heldout import (
    Fmd08IntegrityError,
    build_heldout_local_domain_audit,
    build_heldout_risk_origin_labels,
    build_heldout_target_domain_coverage,
    compute_cohort_sha256,
    compute_locked_evaluation_metrics,
    resolve_frozen_candidate_spec,
    score_heldout_origin_frozen_candidate,
    verify_frozen_model_identity,
)
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.model_development.baseline_scoring import CellScore
from components.geospatial_tracking.services.model_development.domain_design import TargetDomainCoverage

_CUTOFF = "2026-01-01"


def _origin(oid: str, *, country: str, t0: str) -> ForecastOrigin:
    return ForecastOrigin(
        forecast_origin_id=oid, country=country, t0=t0, temporal_mode="RETROSPECTIVE_PROXY",
        trigger_source_ids_at_t0=["S1"], trigger_source_count=1,
    )


def _fit_dev_origin(oid: str) -> ForecastOrigin:
    return _origin(oid, country="Kenya", t0="2020-01-01")


def _held_out_origin(oid: str) -> ForecastOrigin:
    return _origin(oid, country="Kenya", t0="2026-06-01")


def _sri_lanka_origin(oid: str) -> ForecastOrigin:
    return _origin(oid, country="Sri Lanka", t0="2020-01-01")


# ---------------------------------------------------------------------------
# B. Cohort firewall
# ---------------------------------------------------------------------------


class TestCohortFirewall:
    def test_target_domain_coverage_rejects_fit_development(self):
        with pytest.raises(ValueError, match="FIT_DEVELOPMENT"):
            build_heldout_target_domain_coverage(
                repo=None, held_out_origins=[_fit_dev_origin("O1")],
                disease="FMD", active_window_days=14, cutoff=_CUTOFF,
            )

    def test_target_domain_coverage_rejects_sri_lanka(self):
        with pytest.raises(ValueError, match="SRI_LANKA_TRANSFER_CASE_STUDY"):
            build_heldout_target_domain_coverage(
                repo=None, held_out_origins=[_sri_lanka_origin("O1")],
                disease="FMD", active_window_days=14, cutoff=_CUTOFF,
            )

    def test_target_domain_coverage_rejects_mixed_roles(self):
        with pytest.raises(ValueError):
            build_heldout_target_domain_coverage(
                repo=None, held_out_origins=[_held_out_origin("O1"), _fit_dev_origin("O2")],
                disease="FMD", active_window_days=14, cutoff=_CUTOFF,
            )

    def test_local_domain_audit_rejects_fit_development(self):
        with pytest.raises(ValueError, match="FIT_DEVELOPMENT"):
            build_heldout_local_domain_audit([_fit_dev_origin("O1")], [], cutoff=_CUTOFF)

    def test_risk_labels_reject_fit_development(self):
        with pytest.raises(ValueError, match="FIT_DEVELOPMENT"):
            build_heldout_risk_origin_labels([_fit_dev_origin("O1")], [], cutoff=_CUTOFF)

    def test_cohort_sha_fails_closed_on_duplicate(self):
        with pytest.raises(Fmd08IntegrityError, match="duplicate"):
            compute_cohort_sha256(["ORIGIN:1", "ORIGIN:2", "ORIGIN:1"])

    def test_cohort_sha_deterministic_and_order_independent(self):
        a = compute_cohort_sha256(["ORIGIN:2", "ORIGIN:1", "ORIGIN:3"])
        b = compute_cohort_sha256(["ORIGIN:1", "ORIGIN:3", "ORIGIN:2"])
        assert a == b
        assert len(a) == 64


# ---------------------------------------------------------------------------
# A. Frozen model identity
# ---------------------------------------------------------------------------


class TestFrozenModelIdentity:
    def _write_canon(self, tmp_path: Path, *, spec_payload: dict, tamper_manifest_sha: bool = False, mismatch_candidate: bool = False):
        canon = tmp_path / "local_data/processed/fmd/model_development"
        canon.mkdir(parents=True)
        spec_bytes = json.dumps(spec_payload, sort_keys=True).encode("utf-8")
        (canon / "fmd07b_frozen_model_spec.json").write_bytes(spec_bytes)
        recorded_sha = hashlib.sha256(spec_bytes).hexdigest()
        if tamper_manifest_sha:
            recorded_sha = "0" * 64
        manifest = {
            "held_out_used": False, "sri_lanka_used": False,
            "output_artifact_sha256": {"fmd07b_frozen_model_spec.json": recorded_sha},
        }
        (canon / "fmd07b_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        summary_candidate = "OTHER_CANDIDATE" if mismatch_candidate else spec_payload["selected_candidate_id"]
        summary = {"selected_candidate_id": summary_candidate, "selected_primary_metric_value": 0.5}
        (canon / "fmd07b_candidate_selection_summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return tmp_path

    def test_valid_identity_verifies(self, tmp_path):
        repo_root = self._write_canon(tmp_path, spec_payload={"selected_candidate_id": "CID:X", "threshold": 0.8})
        result = verify_frozen_model_identity(repo_root)
        assert result["selected_candidate_id"] == "CID:X"
        assert result["threshold"] == 0.8

    def test_tampered_spec_sha_fails_closed(self, tmp_path):
        repo_root = self._write_canon(
            tmp_path, spec_payload={"selected_candidate_id": "CID:X", "threshold": 0.8}, tamper_manifest_sha=True,
        )
        with pytest.raises(Fmd08IntegrityError, match="SHA-256"):
            verify_frozen_model_identity(repo_root)

    def test_candidate_mismatch_fails_closed(self, tmp_path):
        repo_root = self._write_canon(
            tmp_path, spec_payload={"selected_candidate_id": "CID:X", "threshold": 0.8}, mismatch_candidate=True,
        )
        with pytest.raises(Fmd08IntegrityError, match="mismatch"):
            verify_frozen_model_identity(repo_root)

    def test_canon_dir_override_binds_to_a_different_directory(self, tmp_path):
        """FMD-10B: verify_frozen_model_identity must read from an explicitly
        passed canon_dir (e.g. FMD-10A's fmd10a_corrected_selection/) instead
        of the default original FMD-07B directory, so held-out evaluation can
        be bound to a superseding frozen spec without overwriting the
        original one."""
        default_root = self._write_canon(tmp_path, spec_payload={"selected_candidate_id": "CID:DEFAULT", "threshold": 0.8})
        corrected_dir = tmp_path / "corrected"
        corrected_dir.mkdir()
        spec_payload = {"selected_candidate_id": "CID:CORRECTED", "threshold": 0.05}
        spec_bytes = json.dumps(spec_payload, sort_keys=True).encode("utf-8")
        (corrected_dir / "fmd07b_frozen_model_spec.json").write_bytes(spec_bytes)
        manifest = {
            "held_out_used": False, "sri_lanka_used": False,
            "output_artifact_sha256": {"fmd07b_frozen_model_spec.json": hashlib.sha256(spec_bytes).hexdigest()},
        }
        (corrected_dir / "fmd07b_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (corrected_dir / "fmd07b_candidate_selection_summary.json").write_text(
            json.dumps({"selected_candidate_id": "CID:CORRECTED", "selected_primary_metric_value": 0.44}), encoding="utf-8",
        )

        default_result = verify_frozen_model_identity(default_root)
        corrected_result = verify_frozen_model_identity(default_root, canon_dir=corrected_dir)

        assert default_result["selected_candidate_id"] == "CID:DEFAULT"
        assert corrected_result["selected_candidate_id"] == "CID:CORRECTED"
        assert corrected_result["threshold"] == 0.05

    def test_resolve_frozen_candidate_spec_unknown_id_fails_closed(self):
        with pytest.raises(Fmd08IntegrityError):
            resolve_frozen_candidate_spec("NOT_A_REAL_CANDIDATE_ID")

    def test_resolve_frozen_candidate_spec_returns_real_frozen_spec(self):
        spec = resolve_frozen_candidate_spec(
            "FMD07B:SPATIAL:B0_DISTANCE_ONLY:EXPONENTIAL:25KM:NONE:dc158733d9d94c2c"
        )
        assert spec.host_factor_candidate is None
        assert spec.kernel_scale_km == 25.0


# ---------------------------------------------------------------------------
# D. Held-out label chain reproduces the exact FIT_DEVELOPMENT projection rule
# ---------------------------------------------------------------------------


class TestLabelChainEquivalence:
    def test_local_domain_audit_matches_development_rule(self):
        radius_km = 200.0
        dev_origins = [_fit_dev_origin("O1"), _fit_dev_origin("O2")]
        held_origins = [_held_out_origin("O1"), _held_out_origin("O2")]

        # Identical coverage geometry for both roles -- only the origin
        # objects (and therefore roles) differ.
        def _coverage(origin_id):
            return [
                TargetDomainCoverage(
                    forecast_origin_id=origin_id, target_id=f"{origin_id}:T1", target_event_id="E1",
                    lead_days=3, min_distance_to_eligible_source_km=50.0,
                    covered_by_candidate_km={radius_km: True},
                ),
                TargetDomainCoverage(
                    forecast_origin_id=origin_id, target_id=f"{origin_id}:T2", target_event_id="E2",
                    lead_days=5, min_distance_to_eligible_source_km=500.0,
                    covered_by_candidate_km={radius_km: False},
                ),
            ]

        coverage_rows = _coverage("O1") + _coverage("O2")

        dev_rows = build_fmd06c_pa_local_domain_audit(dev_origins, coverage_rows, radius_km=radius_km, cutoff=_CUTOFF)
        held_rows = build_heldout_local_domain_audit(held_origins, coverage_rows, radius_km=radius_km, cutoff=_CUTOFF)

        dev_by_id = {r["forecast_origin_id"]: r for r in dev_rows}
        held_by_id = {r["forecast_origin_id"]: r for r in held_rows}
        assert set(dev_by_id) == set(held_by_id) == {"O1", "O2"}
        computed_fields = (
            "has_eligible_d1_d7_target", "n_eligible_d1_d7_targets", "n_targets_within_local_domain",
            "n_targets_outside_local_domain", "local_domain_positive", "outside_domain_target_present",
        )
        for oid in dev_by_id:
            dev_row, held_row = dev_by_id[oid], held_by_id[oid]
            for field in computed_fields:
                assert dev_row[field] == held_row[field], field

    def test_risk_labels_match_development_rule(self):
        radius_km = 200.0
        dev_origins = [_fit_dev_origin("O1")]
        held_origins = [_held_out_origin("O1")]
        audit_row = [{
            "forecast_origin_id": "O1", "local_domain_positive": "True", "has_eligible_d1_d7_target": "True",
            "outside_domain_target_present": "False",
        }]

        dev_labels = build_fmd06d_risk_origin_labels(dev_origins, audit_row, cutoff=_CUTOFF, radius_km=radius_km)
        held_labels = build_heldout_risk_origin_labels(held_origins, audit_row, cutoff=_CUTOFF, radius_km=radius_km)

        dev_row, held_row = dev_labels[0], held_labels[0]
        assert dev_row["risk_target_label"] == held_row["risk_target_label"] == 1
        assert dev_row["model_fitting_role"] == "FIT_DEVELOPMENT"
        assert held_row["model_fitting_role"] == "HELD_OUT_FROM_MODEL_FITTING"
        # Every other field (the actual label-projection math) is identical.
        for key in ("has_eligible_d1_d7_target", "outside_domain_target_present", "local_evaluation_radius_km",
                     "target_horizon", "spatial_reference_source_set", "spatial_protocol_amendment_status"):
            assert dev_row[key] == held_row[key]

    def test_risk_labels_fail_closed_on_incomplete_audit_coverage(self):
        held_origins = [_held_out_origin("O1"), _held_out_origin("O2")]
        audit_row = [{"forecast_origin_id": "O1", "local_domain_positive": "False",
                       "has_eligible_d1_d7_target": "False", "outside_domain_target_present": "False"}]
        with pytest.raises(Fmd08IntegrityError, match="missing"):
            build_heldout_risk_origin_labels(held_origins, audit_row, cutoff=_CUTOFF, radius_km=200.0)


# ---------------------------------------------------------------------------
# E. No held-out selection/tuning/threshold-optimization/calibration-fitting
# ---------------------------------------------------------------------------


class TestNoHeldOutOptimization:
    def test_scorer_refuses_a_reference_dependent_candidate(self):
        """A candidate with host_factor_candidate set would need a fitted
        reference profile; this module never builds one from held-out data,
        so scoring must refuse rather than silently building one."""
        candidate = BaselineCandidateSpec(
            candidate_id="CID:REFERENCE_DEPENDENT", baseline_family="B1_HOST_DISTANCE_LOG1P",
            host_factor_candidate="LOG1P_ROBUST_REFERENCE_SCALE", kernel_family="EXPONENTIAL",
            kernel_scale_km=25.0, source_weighting="UNWEIGHTED", output_label="B1",
        )
        with pytest.raises(Fmd08IntegrityError, match="reference profile"):
            score_heldout_origin_frozen_candidate(
                forecast_origin_id="O1", grid_cells=[], sources=[], frozen_candidate=candidate,
            )

    def test_frozen_candidate_scores_without_any_reference_profile(self):
        candidate = BaselineCandidateSpec(
            candidate_id="CID:B0", baseline_family="B0_DISTANCE_ONLY", host_factor_candidate=None,
            kernel_family="EXPONENTIAL", kernel_scale_km=25.0, source_weighting="UNWEIGHTED", output_label="B0",
        )

        class _Source:
            def __init__(self, lat, lon):
                self.latitude, self.longitude, self.source_id = lat, lon, "S1"

        grid_cells = [{
            "grid_cell_id": "C1", "scientific_cell_id": "C1", "centroid_lat": 0.0, "centroid_lon": 0.0,
            "area_km2": 25.0, "domain_overlap_area_km2": 25.0,
        }]
        prediction = score_heldout_origin_frozen_candidate(
            forecast_origin_id="O1", grid_cells=grid_cells, sources=[_Source(0.01, 0.01)], frozen_candidate=candidate,
        )
        assert prediction.status == "SCORED"
        assert prediction.score is not None

    def test_metrics_take_threshold_as_explicit_input_never_search_it(self):
        y_true = [0, 1, 0, 1, 1]
        y_score = [0.1, 0.9, 0.4, 0.6, 5.0]
        low = compute_locked_evaluation_metrics(y_true, y_score, threshold=0.5, n_unscored=0)
        high = compute_locked_evaluation_metrics(y_true, y_score, threshold=4.0, n_unscored=0)
        assert low.threshold == 0.5
        assert high.threshold == 4.0
        # Different explicit thresholds legitimately give different confusion
        # matrices -- proving the function applies exactly what it's given,
        # never an internally searched "best" threshold.
        assert low.f1_at_threshold != high.f1_at_threshold
        # PR-AUC/AUROC are threshold-independent rank metrics.
        assert low.pr_auc == high.pr_auc
        assert low.auroc == high.auroc

    def test_brier_undefined_for_unbounded_score_never_rescaled(self):
        y_true = [0, 1, 0, 1]
        y_score = [0.5, 12.3, 0.2, 7.9]  # unbounded, like the real frozen spatial-kernel candidate
        metrics = compute_locked_evaluation_metrics(y_true, y_score, threshold=1.0, n_unscored=0)
        assert metrics.brier_score is None
        assert metrics.pr_auc is not None  # rank metrics remain valid


# ---------------------------------------------------------------------------
# F. Determinism / fail-closed on degenerate input
# ---------------------------------------------------------------------------


class TestDeterminismAndFailClosed:
    def test_metrics_degenerate_single_class_returns_none_not_crash(self):
        metrics = compute_locked_evaluation_metrics([1, 1, 1], [0.1, 0.5, 0.9], threshold=0.5, n_unscored=0)
        assert metrics.pr_auc is None
        assert metrics.auroc is None
        assert metrics.n_scored == 3

    def test_metrics_repeated_call_is_byte_identical(self):
        y_true = [0, 1, 0, 1, 1, 0]
        y_score = [0.2, 0.8, 0.3, 0.9, 0.6, 0.1]
        a = compute_locked_evaluation_metrics(y_true, y_score, threshold=0.5, n_unscored=2).as_dict()
        b = compute_locked_evaluation_metrics(y_true, y_score, threshold=0.5, n_unscored=2).as_dict()
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
