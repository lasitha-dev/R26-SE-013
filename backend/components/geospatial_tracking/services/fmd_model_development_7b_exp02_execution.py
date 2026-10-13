"""FMD-07B EXP-02-only execution and intermediate artifact persistence.

This module owns no scoring mathematics.  It validates the frozen development
universe and folds, delegates each origin to ``Exp02OriginExecutionAdapter``,
and writes a resumable, non-canonical prediction artifact.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .fmd_calibration import FMD_MODEL_FITTING_CUTOFF
from .fmd_model_development_7b import (
    Fmd07bFoldInput,
    MINIMUM_EXECUTABLE_EXPERIMENT_IDS,
    SpatialDistanceRunner,
    assert_fit_development_only,
    build_spatial_distance_runner,
    validate_fmd07b_fold_input,
)
from .fmd_model_development_7b_execution import (
    build_forecast_origins,
    load_and_verify_r2b3_inputs,
)
from .factors.transform_config import FactorTransformConfig
from .fmd_model_development_7b_exp02_origin import (
    EXP02_ORIGIN_SCALAR_RULE,
    FMD07B_EXP02_ENGINEERING_GRID_SIZE_KM,
    Exp02OriginExecutionAdapter,
)
from .model_development.baseline_scoring import SCORED
from .model_development.development_run_7b import _eligible_source_points
from .model_development.fold_reference import build_fold_safe_reference, build_raw_host_snapshots_cached
from .model_fitting_exposure import CalendarYearFold, build_calendar_year_folds


_REPO_ROOT_PARENTS_FROM_THIS_FILE = 4

EXP02_ARTIFACT_RELATIVE_DIR = Path("local_data/processed/fmd/model_development/fmd07b_exp02")
EXP02_PREDICTIONS_FILENAME = "fmd07b_exp02_fold_predictions.csv"
EXP02_MANIFEST_FILENAME = "fmd07b_exp02_manifest.json"
EXP02_PREDICTION_SCHEMA = (
    "fold_id",
    "experiment_id",
    "candidate_id",
    "forecast_origin_id",
    "true_label",
    "predicted_score",
    "status",
)
EXPECTED_FIT_DEVELOPMENT_ORIGIN_COUNT = 3761
AUTHORITATIVE_FIT_DEVELOPMENT_CUTOFF = FMD_MODEL_FITTING_CUTOFF


class Exp02ExecutionIntegrityError(RuntimeError):
    """EXP-02 input or persisted-artifact validation failed."""


def load_authoritative_fit_development_origins(repo_root: Path) -> tuple[list, dict[str, str]]:
    """Resolve the exact frozen origin universe used by persisted FMD-07B."""
    inputs = load_and_verify_r2b3_inputs(Path(repo_root))
    matrix = inputs.matrix
    if len(matrix) != EXPECTED_FIT_DEVELOPMENT_ORIGIN_COUNT:
        raise Exp02ExecutionIntegrityError("authoritative R2B3 origin count mismatch")
    if not (matrix["t0"] < AUTHORITATIVE_FIT_DEVELOPMENT_CUTOFF).all():
        raise Exp02ExecutionIntegrityError(
            f"authoritative origins must satisfy t0 < {AUTHORITATIVE_FIT_DEVELOPMENT_CUTOFF}"
        )
    if (matrix["country"] == "Sri Lanka").any():
        raise Exp02ExecutionIntegrityError("authoritative FIT_DEVELOPMENT origins include Sri Lanka")
    expected_ids = [f"ORIGIN:{row.country}:{row.t0}" for row in matrix.itertuples(index=False)]
    if matrix["forecast_origin_id"].tolist() != expected_ids:
        raise Exp02ExecutionIntegrityError("authoritative forecast_origin_id format mismatch")
    return build_forecast_origins(matrix), {
        "fmd07_r2b3_development_feature_matrix.csv": inputs.manifest[
            "output_artifact_sha256"
        ]["fmd07_r2b3_development_feature_matrix.csv"],
        "fmd07_r2b3_origin_feature_aggregation_audit.csv": inputs.manifest[
            "output_artifact_sha256"
        ]["fmd07_r2b3_origin_feature_aggregation_audit.csv"],
    }


@dataclass(frozen=True)
class Exp02OriginInputs:
    grid_cells: list[dict]
    sources: list
    reference_profile: object
    transform_config: object | None = None
    unsafe_component_count: int = 0


@dataclass(frozen=True)
class Exp02ExecutionResult:
    predictions_path: Path
    manifest_path: Path
    manifest: Mapping[str, object]
    reused_existing: bool


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary_name).replace(path)
    except BaseException:
        try:
            Path(temporary_name).unlink()
        except FileNotFoundError:
            pass
        raise


def _validate_inputs(
    fit_development_origins: Sequence,
    calendar_folds: Sequence[CalendarYearFold],
    *,
    expected_origin_count: int,
) -> tuple[Fmd07bFoldInput, ...]:
    if len(fit_development_origins) != expected_origin_count:
        raise Exp02ExecutionIntegrityError(
            f"expected {expected_origin_count} FIT_DEVELOPMENT origins, observed {len(fit_development_origins)}"
        )
    assert_fit_development_only(
        list(fit_development_origins), cutoff=AUTHORITATIVE_FIT_DEVELOPMENT_CUTOFF, caller="execute_exp02_only"
    )
    if not calendar_folds:
        raise Exp02ExecutionIntegrityError("frozen chronological folds must not be empty")
    try:
        validated = tuple(
            validate_fmd07b_fold_input(fit_development_origins, fold)
            for fold in sorted(calendar_folds, key=lambda item: item.fold_id)
        )
    except (TypeError, ValueError) as exc:
        raise Exp02ExecutionIntegrityError("frozen chronological fold validation failed") from exc
    if any(not fold.validation_origin_ids for fold in validated):
        raise Exp02ExecutionIntegrityError("every frozen fold must have validation origins")
    return validated


def _artifact_paths(repo_root: Path) -> tuple[Path, Path]:
    artifact_dir = Path(repo_root) / EXP02_ARTIFACT_RELATIVE_DIR
    return artifact_dir / EXP02_PREDICTIONS_FILENAME, artifact_dir / EXP02_MANIFEST_FILENAME


def _validate_prediction_coverage(
    rows: Sequence[Mapping[str, str]],
    *,
    expected_folds: Sequence[Fmd07bFoldInput],
    expected_candidate_ids: Sequence[str],
) -> None:
    expected_keys = {
        (fold.fold_id, "FMD-EXP-02", candidate_id, origin_id)
        for fold in expected_folds
        for candidate_id in expected_candidate_ids
        for origin_id in fold.validation_origin_ids
    }
    observed_keys = [
        (row.get("fold_id"), row.get("experiment_id"), row.get("candidate_id"), row.get("forecast_origin_id"))
        for row in rows
    ]
    if len(observed_keys) != len(set(observed_keys)):
        raise Exp02ExecutionIntegrityError(
            "EXP-02 prediction artifact structural coverage contains duplicate candidate/fold/origin rows"
        )
    observed_key_set = set(observed_keys)
    if observed_key_set != expected_keys:
        raise Exp02ExecutionIntegrityError(
            "EXP-02 prediction artifact structural coverage mismatch: "
            f"expected {len(expected_keys)} candidate/fold/origin rows, observed {len(observed_key_set)}; "
            f"missing={len(expected_keys - observed_key_set)}, unexpected={len(observed_key_set - expected_keys)}"
        )


def _load_completed_artifact(
    predictions_path: Path,
    manifest_path: Path,
    *,
    expected_folds: Sequence[Fmd07bFoldInput],
    expected_candidate_ids: Sequence[str],
    expected_input_hashes: Mapping[str, str] | None,
) -> Exp02ExecutionResult | None:
    if not predictions_path.exists() and not manifest_path.exists():
        return None
    if not predictions_path.exists() or not manifest_path.exists():
        raise Exp02ExecutionIntegrityError("incomplete EXP-02 artifact pair exists; refusing duplicate execution")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        prediction_bytes = predictions_path.read_bytes()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Exp02ExecutionIntegrityError("completed EXP-02 artifact is unreadable") from exc
    if not isinstance(manifest, Mapping) or manifest.get("execution_complete") is not True:
        raise Exp02ExecutionIntegrityError("EXP-02 artifact is not marked execution-complete")
    if manifest.get("experiment_id") != "FMD-EXP-02":
        raise Exp02ExecutionIntegrityError("EXP-02 artifact has an unexpected experiment ID")
    if manifest.get("predictions_sha256") != _sha256_bytes(prediction_bytes):
        raise Exp02ExecutionIntegrityError("EXP-02 prediction artifact hash mismatch")
    if manifest.get("grid_size_km") != FMD07B_EXP02_ENGINEERING_GRID_SIZE_KM:
        raise Exp02ExecutionIntegrityError("EXP-02 artifact grid size does not match frozen 30.0 km configuration")
    if manifest.get("origin_scalar_rule") != EXP02_ORIGIN_SCALAR_RULE:
        raise Exp02ExecutionIntegrityError("EXP-02 artifact scalar rule does not match the frozen rule")
    expected_fold_ids = [fold.fold_id for fold in expected_folds]
    expected_validation_origin_count = sum(len(fold.validation_origin_ids) for fold in expected_folds)
    expected_row_count = expected_validation_origin_count * len(expected_candidate_ids)
    if manifest.get("fold_ids") != expected_fold_ids:
        raise Exp02ExecutionIntegrityError("EXP-02 artifact structural coverage does not match current calendar folds")
    if manifest.get("candidate_ids") != list(expected_candidate_ids):
        raise Exp02ExecutionIntegrityError("EXP-02 artifact structural coverage does not match the current candidate grid")
    if manifest.get("validation_origin_count") != expected_validation_origin_count:
        raise Exp02ExecutionIntegrityError("EXP-02 artifact structural coverage has the wrong validation-origin count")
    if manifest.get("row_count") != expected_row_count:
        raise Exp02ExecutionIntegrityError("EXP-02 artifact structural coverage has the wrong expected row count")
    if manifest.get("fit_development_cutoff") != AUTHORITATIVE_FIT_DEVELOPMENT_CUTOFF:
        raise Exp02ExecutionIntegrityError("EXP-02 artifact structural coverage uses another development cutoff")
    if expected_input_hashes is not None and manifest.get("input_artifact_sha256") != dict(
        sorted(expected_input_hashes.items())
    ):
        raise Exp02ExecutionIntegrityError("EXP-02 artifact inputs do not match current authoritative artifacts")
    reader = csv.DictReader(io.StringIO(prediction_bytes.decode("utf-8"), newline=""))
    if tuple(reader.fieldnames or ()) != EXP02_PREDICTION_SCHEMA:
        raise Exp02ExecutionIntegrityError("EXP-02 prediction artifact schema mismatch")
    rows = list(reader)
    if any(row.get("experiment_id") != "FMD-EXP-02" for row in rows):
        raise Exp02ExecutionIntegrityError("EXP-02 prediction artifact contains another experiment")
    if any(row.get("status") != SCORED and row.get("predicted_score") != "" for row in rows):
        raise Exp02ExecutionIntegrityError("unavailable EXP-02 prediction has a numeric score")
    _validate_prediction_coverage(
        rows,
        expected_folds=expected_folds,
        expected_candidate_ids=expected_candidate_ids,
    )
    row_keys = [
        (row["fold_id"], row["experiment_id"], row["candidate_id"], row["forecast_origin_id"])
        for row in rows
    ]
    if row_keys != sorted(row_keys):
        raise Exp02ExecutionIntegrityError("EXP-02 prediction rows are not deterministically ordered")
    if manifest.get("row_count") != len(rows):
        raise Exp02ExecutionIntegrityError("EXP-02 manifest row count does not match the prediction artifact")
    if manifest.get("scored_count") != sum(row.get("status") == SCORED for row in rows):
        raise Exp02ExecutionIntegrityError("EXP-02 manifest scored count does not match the prediction artifact")
    return Exp02ExecutionResult(predictions_path, manifest_path, manifest, True)


def _prediction_rows(
    fold: Fmd07bFoldInput,
    origin_id: str,
    true_label: int | bool,
    predictions,
) -> list[dict[str, str]]:
    if true_label not in (0, 1, False, True):
        raise Exp02ExecutionIntegrityError(f"non-binary true label for {origin_id}")
    rows = []
    for prediction in predictions:
        rows.append(
            {
                "fold_id": fold.fold_id,
                "experiment_id": prediction.experiment_id,
                "candidate_id": prediction.candidate_id,
                "forecast_origin_id": origin_id,
                "true_label": str(int(true_label)),
                "predicted_score": "" if prediction.score is None else format(prediction.score, ".17g"),
                "status": prediction.status,
            }
        )
    return rows


def execute_exp02_only(
    repo_root: Path,
    *,
    fit_development_origins: Sequence,
    calendar_folds: Sequence[CalendarYearFold],
    spatial_runner: SpatialDistanceRunner,
    origin_inputs: Callable[[object, Fmd07bFoldInput], Exp02OriginInputs],
    true_label_for_origin: Callable[[object], int | bool],
    expected_origin_count: int = EXPECTED_FIT_DEVELOPMENT_ORIGIN_COUNT,
    input_hashes: Mapping[str, str] | None = None,
) -> Exp02ExecutionResult:
    """Execute exactly FMD-EXP-02, or reuse one valid completed artifact."""
    predictions_path, manifest_path = _artifact_paths(Path(repo_root))
    if len(fit_development_origins) != expected_origin_count:
        raise Exp02ExecutionIntegrityError(
            f"expected {expected_origin_count} FIT_DEVELOPMENT origins, observed {len(fit_development_origins)}"
        )
    if expected_origin_count == EXPECTED_FIT_DEVELOPMENT_ORIGIN_COUNT:
        authoritative_origins, authoritative_hashes = load_authoritative_fit_development_origins(repo_root)
        if {origin.forecast_origin_id for origin in fit_development_origins} != {
            origin.forecast_origin_id for origin in authoritative_origins
        }:
            raise Exp02ExecutionIntegrityError("provided origins do not match persisted R2B3 provenance")
        if input_hashes is None:
            input_hashes = authoritative_hashes
    if spatial_runner.experiment_id != "FMD-EXP-02":
        raise Exp02ExecutionIntegrityError("EXP-02 orchestrator requires an FMD-EXP-02 runner")
    if set(MINIMUM_EXECUTABLE_EXPERIMENT_IDS) != {"FMD-EXP-01", "FMD-EXP-02", "FMD-EXP-04"}:
        raise Exp02ExecutionIntegrityError("minimum executable experiment registry changed")
    if spatial_runner.registry_status != "FMD07A_R1_FROZEN":
        raise Exp02ExecutionIntegrityError("EXP-02 candidate registry is not frozen")
    folds = _validate_inputs(fit_development_origins, calendar_folds, expected_origin_count=expected_origin_count)
    candidate_ids = tuple(sorted(candidate.candidate_id for candidate in spatial_runner.candidates))
    if not candidate_ids or any(not candidate_id for candidate_id in candidate_ids):
        raise Exp02ExecutionIntegrityError("EXP-02 candidate registry must contain non-empty candidate IDs")
    if len(candidate_ids) != len(set(candidate_ids)):
        raise Exp02ExecutionIntegrityError("EXP-02 candidate registry contains duplicate candidate IDs")
    existing = _load_completed_artifact(
        predictions_path,
        manifest_path,
        expected_folds=folds,
        expected_candidate_ids=candidate_ids,
        expected_input_hashes=input_hashes,
    )
    if existing is not None:
        return existing
    adapter = Exp02OriginExecutionAdapter(spatial_runner)
    origin_by_id = {origin.forecast_origin_id: origin for origin in fit_development_origins}
    rows: list[dict[str, str]] = []
    for fold in folds:
        for origin_id in fold.validation_origin_ids:
            origin = origin_by_id[origin_id]
            inputs = origin_inputs(origin, fold)
            predictions = adapter.execute_validation_origin(
                fold,
                forecast_origin_id=origin_id,
                grid_cells=inputs.grid_cells,
                sources=inputs.sources,
                reference_profile=inputs.reference_profile,
                transform_config=inputs.transform_config,
                unsafe_component_count=inputs.unsafe_component_count,
            )
            rows.extend(_prediction_rows(fold, origin_id, true_label_for_origin(origin), predictions))
    rows.sort(key=lambda row: (row["fold_id"], row["experiment_id"], row["candidate_id"], row["forecast_origin_id"]))
    _validate_prediction_coverage(
        rows,
        expected_folds=folds,
        expected_candidate_ids=candidate_ids,
    )
    scored_count = sum(row["status"] == SCORED for row in rows)
    unavailable_count = len(rows) - scored_count
    csv_buffer = __import__("io").StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=EXP02_PREDICTION_SCHEMA, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    prediction_bytes = csv_buffer.getvalue().encode("utf-8")
    manifest = {
        "experiment_id": "FMD-EXP-02",
        "grid_size_km": FMD07B_EXP02_ENGINEERING_GRID_SIZE_KM,
        "origin_scalar_rule": EXP02_ORIGIN_SCALAR_RULE,
        "fit_development_cutoff": AUTHORITATIVE_FIT_DEVELOPMENT_CUTOFF,
        "fold_ids": [fold.fold_id for fold in folds],
        "candidate_ids": list(candidate_ids),
        "validation_origin_count": sum(len(fold.validation_origin_ids) for fold in folds),
        "row_count": len(rows),
        "scored_count": scored_count,
        "unavailable_count": unavailable_count,
        "input_artifact_sha256": dict(sorted((input_hashes or {}).items())),
        "held_out_used": False,
        "sri_lanka_used": False,
        "locked_test_used": False,
        "execution_complete": True,
        "predictions_sha256": _sha256_bytes(prediction_bytes),
    }
    _atomic_write(predictions_path, prediction_bytes)
    manifest_bytes = _canonical_json(manifest)
    _atomic_write(manifest_path, manifest_bytes)
    return Exp02ExecutionResult(predictions_path, manifest_path, manifest, False)


def run_exp02_composition(
    repo_root: Path,
    *,
    repo,
    disease: str,
    active_window_days: int,
    grid_config,
    transform_config=None,
    raw_snapshot_cache_dir: Path | None = None,
) -> Exp02ExecutionResult:
    """Compose the existing FIT_DEVELOPMENT-only EXP-02 execution pieces."""
    repo_root = Path(repo_root).resolve()
    transform_config = transform_config or FactorTransformConfig()
    authoritative_origins, input_hashes = load_authoritative_fit_development_origins(repo_root)
    verified_inputs = load_and_verify_r2b3_inputs(repo_root)
    matrix = verified_inputs.matrix
    labels_by_origin = {
        row.forecast_origin_id: int(row.risk_target_label)
        for row in matrix.itertuples(index=False)
    }
    calendar_folds = build_calendar_year_folds(
        authoritative_origins,
        cutoff=AUTHORITATIVE_FIT_DEVELOPMENT_CUTOFF,
    )
    spatial_runner = build_spatial_distance_runner()
    cache_dir = raw_snapshot_cache_dir or (
        repo_root / "local_data/processed/fmd/model_development/fmd07b_exp02/raw_host_snapshot_cache"
    )
    raw_snapshots, _cache_stats = build_raw_host_snapshots_cached(
        repo,
        fit_development_origins=authoritative_origins,
        disease=disease,
        active_window_days=active_window_days,
        grid_config=grid_config,
        cache_dir=cache_dir,
        cutoff=AUTHORITATIVE_FIT_DEVELOPMENT_CUTOFF,
    )
    fold_references = {}
    origin_by_id = {origin.forecast_origin_id: origin for origin in authoritative_origins}

    def origin_inputs(origin, fold):
        fold_reference = fold_references.get(fold.fold_id)
        if fold_reference is None:
            fold_reference = build_fold_safe_reference(
                fold_id=fold.fold_id,
                training_origins=[origin_by_id[origin_id] for origin_id in fold.training_origin_ids],
                validation_origins=[origin_by_id[origin_id] for origin_id in fold.validation_origin_ids],
                raw_snapshots_by_origin_id=raw_snapshots,
                transform_config=transform_config,
                generated_at="",
                cutoff=AUTHORITATIVE_FIT_DEVELOPMENT_CUTOFF,
            )
            fold_references[fold.fold_id] = fold_reference
        snapshot = raw_snapshots.get(origin.forecast_origin_id)
        if snapshot is None:
            return Exp02OriginInputs([], [], fold_reference.reference_profile, transform_config, fold_reference.unsafe_component_count)
        return Exp02OriginInputs(
            snapshot.get("grid_cells", []) or [],
            _eligible_source_points(repo, origin, disease=disease, active_window_days=active_window_days),
            fold_reference.reference_profile,
            transform_config,
            fold_reference.unsafe_component_count,
        )

    return execute_exp02_only(
        repo_root,
        fit_development_origins=authoritative_origins,
        calendar_folds=calendar_folds,
        spatial_runner=spatial_runner,
        origin_inputs=origin_inputs,
        true_label_for_origin=lambda origin: labels_by_origin[origin.forecast_origin_id],
        expected_origin_count=len(authoritative_origins),
        input_hashes=input_hashes,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the FMD-07B FMD-EXP-02 development composition.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[_REPO_ROOT_PARENTS_FROM_THIS_FILE])
    parser.add_argument("--disease", default="FMD")
    parser.add_argument("--active-window-days", type=int, default=None)
    parser.add_argument("--cell-size-km", type=float, default=5.0)
    parser.add_argument("--domain-distance-km", type=float, default=25.0)
    args = parser.parse_args(argv)

    from ..config import ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT
    from .geospatial.scientific_grid import ScientificGridConfig
    from .model_development.local_evaluation_scope import (
        PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
        SCIENTIFIC_GRID_CELL_SIZE_KM,
    )
    from ..repositories.provider import create_outbreak_repository
    from .geospatial.scientific_grid import DOMAIN_MODE_SOURCE_BUFFER_UNION

    if args.active_window_days is None:
        args.active_window_days = ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT
    grid_config = ScientificGridConfig(
        cell_size_km=args.cell_size_km or SCIENTIFIC_GRID_CELL_SIZE_KM,
        domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION,
        domain_distance_km=args.domain_distance_km or PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
    )
    repo = create_outbreak_repository()
    try:
        result = run_exp02_composition(
            args.repo_root,
            repo=repo,
            disease=args.disease,
            active_window_days=args.active_window_days,
            grid_config=grid_config,
        )
    finally:
        repo.close()
    print(json.dumps(dict(result.manifest), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
