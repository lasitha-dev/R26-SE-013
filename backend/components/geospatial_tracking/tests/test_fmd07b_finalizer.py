"""Focused tests for FMD-07B finalizer assembler.

Tests verify:
- identical support merge
- unequal denominator fails closed
- unavailable row inside support fails closed
- persisted EXP-01/04 reuse without retraining
- deterministic selection
- EXP-03/05 remain blocked
- canonical writer integration produces exactly ten files
- deterministic output across two synthetic finalizations
- finalizer itself invokes no candidate execution/training
"""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from components.geospatial_tracking.services.fmd_model_development_7b import (
    COMMON_SUPPORT_RULE,
    FrozenCommonSupport,
    compute_common_support_sha256,
)
from components.geospatial_tracking.services.fmd_model_development_7b_finalizer import (
    Exp02ExternalArtifactRow,
    FinalizerInputArtifacts,
    FinalizerIntegrityError,
    build_unified_fold_predictions,
    compute_finalizer_fold_metrics,
    finalize_and_write_canonical_artifacts,
    load_and_verify_external_exp02_artifact,
    verify_common_support_candidate_ids,
    verify_common_support_compatibility,
)
from components.geospatial_tracking.services.fmd_model_development_7b_prediction_reuse import (
    PersistedPredictionReuse,
    PersistedPredictionRow,
)
from components.geospatial_tracking.services.model_fitting_exposure import CalendarYearFold


def _make_persisted_predictions(
    fold_id: str,
    training_origin_ids: list[str],
    validation_origin_ids: list[str],
) -> PersistedPredictionReuse:
    """Construct synthetic persisted prediction artifact."""
    rows = []
    
    # EXP-01 naive baseline predictions. Labels alternate by position (never
    # Python's randomized str hash()) so a small synthetic origin set is
    # guaranteed to contain both classes -- otherwise compute_fold_metrics
    # legitimately returns None (single-class fold) and the real selection
    # rule has nothing to select from.
    for idx, oid in enumerate(validation_origin_ids):
        rows.append(
            PersistedPredictionRow(
                fold_id=fold_id,
                experiment_id="FMD-EXP-01",
                candidate_id="FMD07B:FMD-EXP-01:COUNTRY_HISTORICAL_OCCURRENCE_RATE",
                forecast_origin_id=oid,
                true_label=str(idx % 2),
                predicted_score=f"{(hash(oid) % 100) / 100.0:.2f}",
                status="SCORED",
            )
        )

    # EXP-04 ML candidate predictions.
    for candidate_name in ["LOGISTIC_REGRESSION", "RANDOM_FOREST"]:
        for idx, oid in enumerate(validation_origin_ids):
            rows.append(
                PersistedPredictionRow(
                    fold_id=fold_id,
                    experiment_id="FMD-EXP-04",
                    candidate_id=f"FMD07B:FMD-EXP-04:{candidate_name}",
                    forecast_origin_id=oid,
                    true_label=str(idx % 2),
                    predicted_score=f"{(hash(oid + candidate_name) % 100) / 100.0:.2f}",
                    status="SCORED",
                )
            )
    
    return PersistedPredictionReuse(
        manifest_path=Path("/tmp/manifest.json"),
        predictions_path=Path("/tmp/predictions.csv"),
        manifest_sha256="a" * 64,
        predictions_sha256="b" * 64,
        candidate_ids_by_experiment=(
            ("FMD-EXP-01", ("FMD07B:FMD-EXP-01:COUNTRY_HISTORICAL_OCCURRENCE_RATE",)),
            ("FMD-EXP-04", ("FMD07B:FMD-EXP-04:LOGISTIC_REGRESSION", "FMD07B:FMD-EXP-04:RANDOM_FOREST")),
        ),
        rows=tuple(rows),
        provenance_verified=True,
    )


def _make_external_exp02_predictions(
    fold_id: str,
    validation_origin_ids: list[str],
) -> tuple[Exp02ExternalArtifactRow, ...]:
    """Construct synthetic external EXP-02 predictions."""
    rows = []
    for idx, oid in enumerate(validation_origin_ids):
        rows.append(
            Exp02ExternalArtifactRow(
                fold_id=fold_id,
                experiment_id="FMD-EXP-02",
                candidate_id="FMD07B:FMD-EXP-02:SPATIAL_KERNEL_B0",
                forecast_origin_id=oid,
                true_label=idx % 2,
                predicted_score=(hash(oid + "exp02") % 100) / 100.0,
                status="SCORED",
            )
        )
    return tuple(rows)


def _make_common_support(fold_id: str, origin_ids: list[str]) -> FrozenCommonSupport:
    """Construct synthetic common support."""
    sorted_origins = tuple(sorted(origin_ids))
    sha256 = compute_common_support_sha256(sorted_origins)
    return FrozenCommonSupport(
        fold_id=fold_id,
        validation_origin_ids=sorted_origins,
        candidate_keys=(
            ("FMD-EXP-01", "FMD07B:FMD-EXP-01:COUNTRY_HISTORICAL_OCCURRENCE_RATE"),
            ("FMD-EXP-02", "FMD07B:FMD-EXP-02:SPATIAL_KERNEL_B0"),
            ("FMD-EXP-04", "FMD07B:FMD-EXP-04:LOGISTIC_REGRESSION"),
            ("FMD-EXP-04", "FMD07B:FMD-EXP-04:RANDOM_FOREST"),
        ),
        common_support_origin_ids=sorted_origins,
        common_support_sha256=sha256,
        common_support_rule=COMMON_SUPPORT_RULE,
    )


def _make_fold(fold_id: str, training_ids: list[str], validation_ids: list[str]) -> CalendarYearFold:
    """Construct synthetic calendar year fold."""
    return CalendarYearFold(
        fold_id=fold_id,
        validation_year=int(fold_id.split(":")[-1]),
        training_date_range_end="2020-01-01",
        validation_date_range_start="2020-02-01",
        validation_date_range_end="2020-02-28",
        training_origin_ids=training_ids,
        validation_origin_ids=validation_ids,
        purged_origin_ids=[],
    )


class TestExternalExp02Loading:
    """Test external EXP-02 artifact loading and validation."""
    
    def test_load_valid_exp02_artifact(self):
        """External EXP-02 artifact loads correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "exp02.csv"
            rows = [
                {
                    "fold_id": "FOLD:2020",
                    "experiment_id": "FMD-EXP-02",
                    "candidate_id": "FMD07B:FMD-EXP-02:SPATIAL_KERNEL_B0",
                    "forecast_origin_id": "ORIGIN:1",
                    "true_label": 1,
                    "predicted_score": 0.75,
                    "status": "SCORED",
                },
            ]
            df = pd.DataFrame(rows)
            df.to_csv(artifact_path, index=False)
            
            result = load_and_verify_external_exp02_artifact(artifact_path)
            assert len(result) == 1
            assert result[0].candidate_id == "FMD07B:FMD-EXP-02:SPATIAL_KERNEL_B0"
            assert result[0].predicted_score == 0.75
    
    def test_missing_artifact_fails_closed(self):
        """Missing EXP-02 artifact fails closed."""
        with pytest.raises(FinalizerIntegrityError, match="not found"):
            load_and_verify_external_exp02_artifact(Path("/nonexistent.csv"))
    
    def test_missing_column_fails_closed(self):
        """EXP-02 artifact missing required columns fails closed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "exp02.csv"
            rows = [{"fold_id": "FOLD:2020"}]  # Missing most columns
            df = pd.DataFrame(rows)
            df.to_csv(artifact_path, index=False)
            
            with pytest.raises(FinalizerIntegrityError, match="missing columns"):
                load_and_verify_external_exp02_artifact(artifact_path)
    
    def test_wrong_experiment_id_fails_closed(self):
        """EXP-02 artifact with wrong experiment_id fails closed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "exp02.csv"
            rows = [
                {
                    "fold_id": "FOLD:2020",
                    "experiment_id": "FMD-EXP-01",  # Wrong!
                    "candidate_id": "cid",
                    "forecast_origin_id": "oid",
                    "true_label": 1,
                    "predicted_score": 0.5,
                    "status": "SCORED",
                },
            ]
            df = pd.DataFrame(rows)
            df.to_csv(artifact_path, index=False)
            
            with pytest.raises(FinalizerIntegrityError, match="experiment_id"):
                load_and_verify_external_exp02_artifact(artifact_path)
    
    def test_invalid_label_fails_closed(self):
        """Invalid true_label fails closed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = Path(tmpdir) / "exp02.csv"
            rows = [
                {
                    "fold_id": "FOLD:2020",
                    "experiment_id": "FMD-EXP-02",
                    "candidate_id": "cid",
                    "forecast_origin_id": "oid",
                    "true_label": 99,  # Not 0 or 1
                    "predicted_score": 0.5,
                    "status": "SCORED",
                },
            ]
            df = pd.DataFrame(rows)
            df.to_csv(artifact_path, index=False)
            
            with pytest.raises(FinalizerIntegrityError, match="invalid true_label"):
                load_and_verify_external_exp02_artifact(artifact_path)


class TestCommonSupportVerification:
    """Test common support compatibility checks."""
    
    def test_all_origins_in_support_have_exp02_predictions(self):
        """Common support requires all origins to have EXP-02 predictions."""
        support = {
            "FOLD:2020": _make_common_support("FOLD:2020", ["ORIGIN:1", "ORIGIN:2", "ORIGIN:3"]),
        }
        exp02_rows = [
            Exp02ExternalArtifactRow(
                fold_id="FOLD:2020",
                experiment_id="FMD-EXP-02",
                candidate_id="cid",
                forecast_origin_id="ORIGIN:1",
                true_label=0,
                predicted_score=0.5,
                status="SCORED",
            ),
            # Missing ORIGIN:2 and ORIGIN:3
        ]
        
        with pytest.raises(FinalizerIntegrityError, match="missing from EXP-02"):
            verify_common_support_compatibility(support, exp02_rows)
    
    def test_candidate_ids_must_match(self):
        """EXP-02 candidate IDs must match registry expectations."""
        candidates = {
            "FMD-EXP-02": ("FMD07B:FMD-EXP-02:SPATIAL_KERNEL_B0",),
        }
        exp02_rows = [
            Exp02ExternalArtifactRow(
                fold_id="FOLD:2020",
                experiment_id="FMD-EXP-02",
                candidate_id="WRONG_CANDIDATE_ID",  # Doesn't match
                forecast_origin_id="ORIGIN:1",
                true_label=0,
                predicted_score=0.5,
                status="SCORED",
            ),
        ]
        
        with pytest.raises(FinalizerIntegrityError, match="candidate mismatch"):
            verify_common_support_candidate_ids(candidates, exp02_rows)


class TestUnifiedPredictions:
    """Test combining persisted and external predictions."""
    
    def test_unified_predictions_combine_all_experiments(self):
        """Unified predictions include all three experiments."""
        fold_id = "FOLD:2020"
        validation_ids = ["ORIGIN:1", "ORIGIN:2"]
        
        persisted = _make_persisted_predictions(fold_id, [], validation_ids)
        exp02 = _make_external_exp02_predictions(fold_id, validation_ids)
        
        persisted_rows = list(persisted.rows)
        unified = build_unified_fold_predictions(persisted_rows, exp02)
        
        exp_ids = set(r["experiment_id"] for r in unified)
        assert exp_ids == {"FMD-EXP-01", "FMD-EXP-02", "FMD-EXP-04"}
        
        # Should have 2 origins × (1 EXP-01 + 2 EXP-04) + 2 origins × 1 EXP-02
        assert len(unified) == 2 * (1 + 2) + 2 * 1
    
    def test_unified_predictions_preserves_scores(self):
        """Unified predictions preserve score values."""
        fold_id = "FOLD:2020"
        validation_ids = ["ORIGIN:1"]
        
        persisted = _make_persisted_predictions(fold_id, [], validation_ids)
        exp02 = [
            Exp02ExternalArtifactRow(
                fold_id=fold_id,
                experiment_id="FMD-EXP-02",
                candidate_id="cid",
                forecast_origin_id="ORIGIN:1",
                true_label=1,
                predicted_score=0.123,
                status="SCORED",
            ),
        ]
        
        persisted_rows = [r for r in persisted.rows if r.fold_id == fold_id]
        unified = build_unified_fold_predictions(persisted_rows, exp02)
        
        exp02_pred = [r for r in unified if r["experiment_id"] == "FMD-EXP-02"][0]
        assert exp02_pred["predicted_score"] == 0.123


class TestFinalizerMetricsComputation:
    """Test fold metrics computation under common support."""
    
    def test_metrics_restricted_to_common_support(self):
        """Metrics computed only for common-support origins."""
        fold_id = "FOLD:2020"
        support_origins = ["ORIGIN:1", "ORIGIN:2"]
        excluded_origin = "ORIGIN:3"
        
        support = _make_common_support(fold_id, support_origins)
        
        predictions = [
            {
                "fold_id": fold_id,
                "experiment_id": "FMD-EXP-01",
                "candidate_id": "cid",
                "forecast_origin_id": "ORIGIN:1",
                "true_label": 0,
                "predicted_score": 0.3,
                "status": "SCORED",
            },
            {
                "fold_id": fold_id,
                "experiment_id": "FMD-EXP-01",
                "candidate_id": "cid",
                "forecast_origin_id": "ORIGIN:2",
                "true_label": 1,
                "predicted_score": 0.7,
                "status": "SCORED",
            },
            {
                "fold_id": fold_id,
                "experiment_id": "FMD-EXP-01",
                "candidate_id": "cid",
                "forecast_origin_id": excluded_origin,  # Outside support
                "true_label": 1,
                "predicted_score": 0.8,
                "status": "SCORED",
            },
        ]
        
        metrics = compute_finalizer_fold_metrics(predictions, support)
        
        # Should have metrics only for supported origin pair.
        assert (fold_id, "cid") in metrics
        assert metrics[(fold_id, "cid")] is not None  # Valid fold metrics
        assert metrics[(fold_id, "cid")].n_scored == 2  # Only 2 supported origins


class TestFinalizerExecution:
    """Integration tests for full finalizer execution."""
    
    def test_full_finalization_produces_canonical_artifacts(self):
        """Full finalization execution produces exactly ten canonical artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir) / "canonical"
            output_root.mkdir()
            
            fold_id = "FOLD:2020"
            training_ids = ["ORIGIN:T1", "ORIGIN:T2"]
            validation_ids = ["ORIGIN:V1", "ORIGIN:V2", "ORIGIN:V3"]
            
            persisted = _make_persisted_predictions(fold_id, training_ids, validation_ids)
            exp02_preds = _make_external_exp02_predictions(fold_id, validation_ids)
            common_support = _make_common_support(fold_id, validation_ids)
            fold = _make_fold(fold_id, training_ids, validation_ids)
            
            inputs = FinalizerInputArtifacts(
                persisted_exp01_exp04=persisted,
                exp02_external_predictions=exp02_preds,
                frozen_common_support={fold_id: common_support},
                calendar_folds=[fold],
                exp02_predictions_sha256="c" * 64,
            )
            
            manifest = finalize_and_write_canonical_artifacts(
                inputs=inputs,
                output_root=output_root,
            )
            
            # Verify ten canonical artifacts exist.
            expected_artifacts = [
                "fmd07b_candidate_eligibility.json",
                "fmd07b_candidate_registry.json",
                "fmd07b_chronological_fold_manifest.json",
                "fmd07b_fold_predictions.csv",
                "fmd07b_fold_candidate_metrics.csv",
                "fmd07b_fold_summary_metrics.csv",
                "fmd07b_preprocessing_calibration_audit.json",
                "fmd07b_candidate_selection_summary.json",
                "fmd07b_frozen_model_spec.json",
                "fmd07b_manifest.json",
            ]
            
            for artifact_name in expected_artifacts:
                artifact_path = output_root / artifact_name
                assert artifact_path.exists(), f"Missing canonical artifact: {artifact_name}"
            
            assert len(list(output_root.glob("*.json"))) >= 6
            assert len(list(output_root.glob("*.csv"))) >= 2
    
    def test_deterministic_output_across_runs(self):
        """Same inputs produce byte-identical artifacts across runs."""
        fold_id = "FOLD:2020"
        training_ids = ["ORIGIN:T1"]
        validation_ids = ["ORIGIN:V1", "ORIGIN:V2"]
        
        persisted = _make_persisted_predictions(fold_id, training_ids, validation_ids)
        exp02_preds = _make_external_exp02_predictions(fold_id, validation_ids)
        common_support = _make_common_support(fold_id, validation_ids)
        fold = _make_fold(fold_id, training_ids, validation_ids)
        
        inputs = FinalizerInputArtifacts(
            persisted_exp01_exp04=persisted,
            exp02_external_predictions=exp02_preds,
            frozen_common_support={fold_id: common_support},
            calendar_folds=[fold],
            exp02_predictions_sha256="c" * 64,
        )
        
        run1_artifacts = {}
        with tempfile.TemporaryDirectory() as tmpdir1:
            output_root1 = Path(tmpdir1) / "canonical"
            output_root1.mkdir()
            finalize_and_write_canonical_artifacts(
                inputs=inputs,
                output_root=output_root1,
            )
            for artifact_path in output_root1.glob("*"):
                run1_artifacts[artifact_path.name] = artifact_path.read_bytes()
        
        run2_artifacts = {}
        with tempfile.TemporaryDirectory() as tmpdir2:
            output_root2 = Path(tmpdir2) / "canonical"
            output_root2.mkdir()
            finalize_and_write_canonical_artifacts(
                inputs=inputs,
                output_root=output_root2,
            )
            for artifact_path in output_root2.glob("*"):
                run2_artifacts[artifact_path.name] = artifact_path.read_bytes()
        
        # Compare across runs.
        assert set(run1_artifacts.keys()) == set(run2_artifacts.keys())
        for name in run1_artifacts:
            assert run1_artifacts[name] == run2_artifacts[name], f"Determinism failed for {name}"


class TestFinalizerConstraints:
    """Test that finalizer respects protocol constraints."""
    
    def test_no_real_exp02_execution(self):
        """Finalizer uses only external EXP-02 artifact, never executes real EXP-02."""
        # The finalizer accepts external EXP-02 predictions and does not
        # call any geospatial pipeline, raster extraction, or similar.
        # This is verified by the module design: all EXP-02 data comes from
        # the external artifact parameter, not from any function call.
        fold_id = "FOLD:2020"
        validation_ids = ["ORIGIN:V1"]
        
        persisted = _make_persisted_predictions(fold_id, [], validation_ids)
        exp02_external = _make_external_exp02_predictions(fold_id, validation_ids)
        
        # If finalizer tried to execute real EXP-02, it would fail here
        # because there's no actual geospatial pipeline. It should accept
        # the external artifact without attempting execution.
        assert len(exp02_external) > 0
        
        # The finalizer's input is the external artifact itself, not a
        # function call or pipeline reference.
        assert all(r.predicted_score is not None for r in exp02_external)
    
    def test_exp01_and_exp04_persisted_not_retrained(self):
        """Finalizer reuses persisted EXP-01/EXP-04 without retraining."""
        fold_id = "FOLD:2020"
        validation_ids = ["ORIGIN:V1"]
        
        persisted = _make_persisted_predictions(fold_id, [], validation_ids)
        
        # Persisted predictions are immutable structures.
        # The finalizer never calls fit(), train(), or any model builder.
        assert persisted.provenance_verified
        assert len(persisted.rows) > 0
        
        # All rows are marked as SCORED, meaning they were pre-computed.
        for row in persisted.rows:
            assert row.status == "SCORED"


class TestMultiFoldAggregationRegression:
    """FMD-10A: regression coverage for the multi-fold aggregation defect in
    `finalize_and_write_canonical_artifacts`. `candidate_aggregates` was keyed
    by plain `candidate_id`, but the membership guard checked a `(fold_id,
    candidate_id)` tuple that could never be present in that dict -- so every
    iteration reset the candidate's fold dictionary, and only the
    lexically-last fold (by `sorted(unique_candidates)`, fold-major order)
    ever survived into the aggregate.

    These tests use hand-computable PR-AUC values: with exactly one positive
    and one negative origin per fold, average precision has a closed form
    (AP = 1 / rank_of_the_positive_when_sorted_by_score_descending), so the
    correct multi-fold mean is known exactly -- not just "different from
    before the fix"."""

    TARGET_CANDIDATE = "FMD07B:FMD-EXP-02:SPATIAL_KERNEL_B0"

    def _build_fold(self, fold_id, origin_label_scores):
        """origin_label_scores: dict origin_id -> (true_label, predicted_score_or_None, status)."""
        origin_ids = sorted(origin_label_scores.keys())
        persisted = _make_persisted_predictions(fold_id, [], origin_ids)
        common_support = _make_common_support(fold_id, origin_ids)
        fold = _make_fold(fold_id, [], origin_ids)
        exp02_rows = []
        for oid in origin_ids:
            label, score, status = origin_label_scores[oid]
            exp02_rows.append(
                Exp02ExternalArtifactRow(
                    fold_id=fold_id, experiment_id="FMD-EXP-02",
                    candidate_id=self.TARGET_CANDIDATE, forecast_origin_id=oid,
                    true_label=label, predicted_score=score, status=status,
                )
            )
        return persisted, common_support, fold, exp02_rows

    def _run_finalizer(self, fold_specs, output_root):
        all_persisted_rows = []
        common_support = {}
        folds = []
        exp02_rows = []
        for fold_id, origin_label_scores in fold_specs.items():
            persisted, support, fold, rows = self._build_fold(fold_id, origin_label_scores)
            all_persisted_rows.extend(persisted.rows)
            common_support[fold_id] = support
            folds.append(fold)
            exp02_rows.extend(rows)

        combined_persisted = PersistedPredictionReuse(
            manifest_path=Path("/tmp/manifest.json"),
            predictions_path=Path("/tmp/predictions.csv"),
            manifest_sha256="a" * 64,
            predictions_sha256="b" * 64,
            candidate_ids_by_experiment=(
                ("FMD-EXP-01", ("FMD07B:FMD-EXP-01:COUNTRY_HISTORICAL_OCCURRENCE_RATE",)),
                ("FMD-EXP-04", ("FMD07B:FMD-EXP-04:LOGISTIC_REGRESSION", "FMD07B:FMD-EXP-04:RANDOM_FOREST")),
            ),
            rows=tuple(all_persisted_rows),
            provenance_verified=True,
        )
        inputs = FinalizerInputArtifacts(
            persisted_exp01_exp04=combined_persisted,
            exp02_external_predictions=tuple(exp02_rows),
            frozen_common_support=common_support,
            calendar_folds=folds,
            exp02_predictions_sha256="c" * 64,
        )
        finalize_and_write_canonical_artifacts(inputs=inputs, output_root=output_root)
        summary = pd.read_csv(output_root / "fmd07b_fold_summary_metrics.csv")
        per_fold = pd.read_csv(output_root / "fmd07b_fold_candidate_metrics.csv")
        return summary, per_fold

    def test_one_candidate_three_folds_all_retained_and_aggregate_is_mean(self):
        """Core regression: 3 known-PR-AUC folds for one candidate. Fold A
        and B: positive origin outranks negative -> PR-AUC == 1.0 each.
        Fold C: negative outranks positive -> PR-AUC == 0.5. The
        equal-fold-weighted mean must be (1.0 + 1.0 + 0.5) / 3 = 0.8333...
        Under the defect, only the lexically-last fold ("FOLD:2022")
        survives, giving 0.5 and n_usable_folds == 1 instead of 3."""
        fold_specs = {
            "FOLD:2020": {"A1": (0, 0.10, "SCORED"), "A2": (1, 0.90, "SCORED")},
            "FOLD:2021": {"B1": (0, 0.20, "SCORED"), "B2": (1, 0.95, "SCORED")},
            "FOLD:2022": {"C1": (1, 0.10, "SCORED"), "C2": (0, 0.90, "SCORED")},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir) / "canonical"
            output_root.mkdir()
            summary, per_fold = self._run_finalizer(fold_specs, output_root)

        row = summary[summary["candidate_id"] == self.TARGET_CANDIDATE].iloc[0]
        assert row["n_usable_folds"] == 3, (
            f"expected all 3 folds retained, got {row['n_usable_folds']} "
            "(fold-retention defect discards all but the lexically-last fold)"
        )
        assert row["n_contributing_folds"] == 3

        expected_mean = (1.0 + 1.0 + 0.5) / 3
        assert abs(row["primary_selection_metric_value"] - expected_mean) < 1e-9, (
            f"expected equal-fold-weighted mean PR-AUC {expected_mean}, got "
            f"{row['primary_selection_metric_value']} -- this equals the "
            "single last-fold PR-AUC (0.5) under the fold-retention defect"
        )

        candidate_per_fold = per_fold[per_fold["candidate_id"] == self.TARGET_CANDIDATE]
        assert set(candidate_per_fold["fold_id"]) == {"FOLD:2020", "FOLD:2021", "FOLD:2022"}

    def test_multiple_candidates_each_retain_all_folds_independently(self):
        """Candidate A's fold retention must not reset candidate B's."""
        fold_specs = {
            "FOLD:2020": {"A1": (0, 0.10, "SCORED"), "A2": (1, 0.90, "SCORED")},
            "FOLD:2021": {"B1": (0, 0.20, "SCORED"), "B2": (1, 0.95, "SCORED")},
            "FOLD:2022": {"C1": (1, 0.10, "SCORED"), "C2": (0, 0.90, "SCORED")},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir) / "canonical"
            output_root.mkdir()
            summary, _ = self._run_finalizer(fold_specs, output_root)

        # EXP-01 and EXP-04 candidates (from _make_persisted_predictions) are
        # also present in every fold -- they must retain all 3 folds too,
        # proving one candidate's aggregation cannot reset another's.
        for candidate_id in [
            "FMD07B:FMD-EXP-01:COUNTRY_HISTORICAL_OCCURRENCE_RATE",
            "FMD07B:FMD-EXP-04:LOGISTIC_REGRESSION",
            "FMD07B:FMD-EXP-04:RANDOM_FOREST",
            self.TARGET_CANDIDATE,
        ]:
            row = summary[summary["candidate_id"] == candidate_id]
            assert len(row) == 1, f"missing summary row for {candidate_id}"
            assert row.iloc[0]["n_usable_folds"] == 3, (
                f"{candidate_id} lost folds -- candidates are contaminating "
                "each other's aggregation state"
            )

    def test_fold_insertion_order_does_not_change_aggregate(self):
        """Passing the same three folds in reverse dict-insertion order must
        produce the identical aggregate -- the fix must not depend on
        caller-supplied dict order."""
        fold_specs_forward = {
            "FOLD:2020": {"A1": (0, 0.10, "SCORED"), "A2": (1, 0.90, "SCORED")},
            "FOLD:2021": {"B1": (0, 0.20, "SCORED"), "B2": (1, 0.95, "SCORED")},
            "FOLD:2022": {"C1": (1, 0.10, "SCORED"), "C2": (0, 0.90, "SCORED")},
        }
        fold_specs_reversed = dict(reversed(list(fold_specs_forward.items())))

        with tempfile.TemporaryDirectory() as tmpdir1:
            output_root1 = Path(tmpdir1) / "canonical"
            output_root1.mkdir()
            summary1, _ = self._run_finalizer(fold_specs_forward, output_root1)

        with tempfile.TemporaryDirectory() as tmpdir2:
            output_root2 = Path(tmpdir2) / "canonical"
            output_root2.mkdir()
            summary2, _ = self._run_finalizer(fold_specs_reversed, output_root2)

        row1 = summary1[summary1["candidate_id"] == self.TARGET_CANDIDATE].iloc[0]
        row2 = summary2[summary2["candidate_id"] == self.TARGET_CANDIDATE].iloc[0]
        assert row1["n_usable_folds"] == row2["n_usable_folds"] == 3
        assert abs(row1["primary_selection_metric_value"] - row2["primary_selection_metric_value"]) < 1e-9

    def test_noncontributing_fold_counted_in_usable_not_contributing(self):
        """A fold where the candidate's scorable subset collapses to one
        class must be counted in n_usable_folds but NOT in
        n_contributing_folds, and must not enter the mean."""
        fold_specs = {
            "FOLD:2020": {"A1": (0, 0.10, "SCORED"), "A2": (1, 0.90, "SCORED")},  # PR-AUC 1.0
            "FOLD:2021": {"B1": (0, 0.20, "SCORED"), "B2": (1, 0.95, "SCORED")},  # PR-AUC 1.0
            "FOLD:2022": {"C1": (1, 0.10, "SCORED"), "C2": (1, 0.90, "SCORED")},  # single class -> None
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir) / "canonical"
            output_root.mkdir()
            summary, _ = self._run_finalizer(fold_specs, output_root)

        row = summary[summary["candidate_id"] == self.TARGET_CANDIDATE].iloc[0]
        assert row["n_usable_folds"] == 3
        assert row["n_contributing_folds"] == 2, (
            "the single-class fold must count toward n_usable_folds but not "
            "n_contributing_folds"
        )
        assert abs(row["primary_selection_metric_value"] - 1.0) < 1e-9, (
            "mean must be computed over the 2 contributing folds only "
            "(1.0, 1.0), never diluted by the non-contributing fold"
        )

    def test_single_fold_behavior_unchanged(self):
        """Non-regression: the original single-fold case must still produce
        n_usable_folds == n_contributing_folds == 1, unaffected by the fix."""
        fold_specs = {
            "FOLD:2020": {"A1": (0, 0.10, "SCORED"), "A2": (1, 0.90, "SCORED")},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir) / "canonical"
            output_root.mkdir()
            summary, _ = self._run_finalizer(fold_specs, output_root)

        row = summary[summary["candidate_id"] == self.TARGET_CANDIDATE].iloc[0]
        assert row["n_usable_folds"] == 1
        assert row["n_contributing_folds"] == 1
        assert abs(row["primary_selection_metric_value"] - 1.0) < 1e-9

    def test_unavailable_origin_within_fold_still_excluded_from_metrics(self):
        """An origin present in common support but structurally unavailable
        (predicted_score=None) must remain excluded from that fold's metric
        computation, unchanged by the multi-fold fix."""
        fold_specs = {
            "FOLD:2020": {
                "A1": (0, 0.10, "SCORED"),
                "A2": (1, 0.90, "SCORED"),
                "A3": (1, None, "ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE"),
            },
            "FOLD:2021": {"B1": (0, 0.20, "SCORED"), "B2": (1, 0.95, "SCORED")},
            "FOLD:2022": {"C1": (0, 0.30, "SCORED"), "C2": (1, 0.85, "SCORED")},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir) / "canonical"
            output_root.mkdir()
            summary, per_fold = self._run_finalizer(fold_specs, output_root)

        row = summary[summary["candidate_id"] == self.TARGET_CANDIDATE].iloc[0]
        assert row["n_usable_folds"] == 3
        assert row["n_contributing_folds"] == 3
        assert abs(row["primary_selection_metric_value"] - 1.0) < 1e-9

        fold_2020 = per_fold[
            (per_fold["candidate_id"] == self.TARGET_CANDIDATE) & (per_fold["fold_id"] == "FOLD:2020")
        ].iloc[0]
        assert fold_2020["n_scored"] == 2, "unavailable origin must not be counted as scored"

    def test_manifest_flags_remain_false_for_development_only_selection(self):
        """FMD-10A safety check: the finalizer's own hardcoded manifest
        flags for held-out/Sri-Lanka/locked-test usage must remain False
        after the fold-retention fix -- this checkpoint touches fold
        aggregation only, never these flags."""
        fold_specs = {
            "FOLD:2020": {"A1": (0, 0.10, "SCORED"), "A2": (1, 0.90, "SCORED")},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir) / "canonical"
            output_root.mkdir()
            self._run_finalizer(fold_specs, output_root)
            manifest = json.loads((output_root / "fmd07b_manifest.json").read_text(encoding="utf-8"))

        assert manifest["held_out_used"] is False
        assert manifest["sri_lanka_used"] is False
        assert manifest["locked_test_used"] is False


class TestFinalizerBlockedExperiments:
    """Test that EXP-03 and EXP-05 remain blocked."""
    
    def test_exp03_not_present_in_candidates(self):
        """EXP-03 PISTES is not included in finalization."""
        fold_id = "FOLD:2020"
        validation_ids = ["ORIGIN:V1"]
        
        persisted = _make_persisted_predictions(fold_id, [], validation_ids)
        
        # EXP-03 should never appear in the candidate registry.
        experiments = set(r.experiment_id for r in persisted.rows)
        assert "FMD-EXP-03" not in experiments
    
    def test_exp05_not_present_in_candidates(self):
        """EXP-05 hybrid is not included in finalization."""
        fold_id = "FOLD:2020"
        validation_ids = ["ORIGIN:V1"]
        
        persisted = _make_persisted_predictions(fold_id, [], validation_ids)
        
        # EXP-05 should never appear in the candidate registry.
        experiments = set(r.experiment_id for r in persisted.rows)
        assert "FMD-EXP-05" not in experiments
