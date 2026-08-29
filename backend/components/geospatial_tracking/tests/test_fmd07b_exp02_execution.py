from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from components.geospatial_tracking.services.fmd_calibration import FMD_MODEL_FITTING_CUTOFF
from components.geospatial_tracking.services.fmd_model_development_7b import Fmd07bFoldInput
from components.geospatial_tracking.services.fmd_model_development_7b_exp02_execution import (
    EXP02_ARTIFACT_RELATIVE_DIR,
    EXP02_MANIFEST_FILENAME,
    EXP02_PREDICTIONS_FILENAME,
    Exp02ExecutionIntegrityError,
    Exp02OriginInputs,
    _validate_prediction_coverage,
    execute_exp02_only,
    load_authoritative_fit_development_origins,
    run_exp02_composition,
)
from components.geospatial_tracking.services.fmd_model_development_7b_exp02_origin import (
    aggregate_exp02_origin_cell_scores,
)
from components.geospatial_tracking.services.model_development.baseline_scoring import (
    CellScore,
    MODEL_INPUT_INCOMPLETE,
    SCORED,
)
from components.geospatial_tracking.services.model_fitting_exposure import (
    CalendarYearFold,
    build_calendar_year_folds,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]


def _origin(origin_id: str, t0: str = "2020-01-15"):
    return SimpleNamespace(
        forecast_origin_id=origin_id,
        country="Thailand",
        t0=t0,
    )


def _fold() -> CalendarYearFold:
    return CalendarYearFold(
        fold_id="FOLD:2020",
        validation_year=2020,
        training_date_range_end="2019-12-31",
        validation_date_range_start="2020-01-01",
        validation_date_range_end="2020-12-31",
        training_origin_ids=["ORIGIN:TRAIN"],
        validation_origin_ids=["ORIGIN:V1", "ORIGIN:V2"],
        purged_origin_ids=[],
    )


def _calendar_fold(year: int, validation_origin_ids: list[str]) -> CalendarYearFold:
    return CalendarYearFold(
        fold_id=f"FOLD:{year}",
        validation_year=year,
        training_date_range_end=f"{year}-01-01",
        validation_date_range_start=f"{year}-01-01",
        validation_date_range_end=f"{year}-12-31",
        training_origin_ids=[],
        validation_origin_ids=sorted(validation_origin_ids),
        purged_origin_ids=[],
    )


def _runner(calls: list):
    class Runner:
        experiment_id = "FMD-EXP-02"
        registry_status = "FMD07A_R1_FROZEN"
        candidates = (SimpleNamespace(candidate_id="EXP02:CANDIDATE"),)

        def score_validation_origin(self, fold, **kwargs):
            calls.append((fold.fold_id, kwargs["forecast_origin_id"]))
            origin_id = kwargs["forecast_origin_id"]
            if origin_id == "ORIGIN:V2":
                cell = CellScore(
                    grid_cell_id="CELL:1", scientific_cell_id="SCI:1", area_km2=900.0,
                    domain_overlap_area_km2=1.0, score=None, status=MODEL_INPUT_INCOMPLETE,
                )
            else:
                cell = CellScore(
                    grid_cell_id="CELL:1", scientific_cell_id="SCI:1", area_km2=900.0,
                    domain_overlap_area_km2=1.0, score=0.75, status=SCORED,
                )
            return {"EXP02:CANDIDATE": [cell]}

    return Runner()


def _inputs(_origin, _fold):
    return Exp02OriginInputs(grid_cells=[{"grid_cell_id": "CELL:1"}], sources=[], reference_profile=None)


def _execute(tmp_path: Path, calls: list):
    return execute_exp02_only(
        tmp_path,
        fit_development_origins=[_origin("ORIGIN:TRAIN", "2019-01-15"), _origin("ORIGIN:V1"), _origin("ORIGIN:V2")],
        calendar_folds=[_fold()],
        spatial_runner=_runner(calls),
        origin_inputs=_inputs,
        true_label_for_origin=lambda origin: origin.forecast_origin_id == "ORIGIN:V2",
        expected_origin_count=3,
    )


def _execute_with_coverage(
    tmp_path: Path,
    *,
    origins: list,
    folds: list[CalendarYearFold],
):
    return execute_exp02_only(
        tmp_path,
        fit_development_origins=origins,
        calendar_folds=folds,
        spatial_runner=_runner([]),
        origin_inputs=_inputs,
        true_label_for_origin=lambda _origin: 0,
        expected_origin_count=len(origins),
    )


def test_executes_only_exp02_for_each_validation_origin_and_preserves_status(tmp_path):
    calls = []
    result = _execute(tmp_path, calls)

    assert calls == [("FOLD:2020", "ORIGIN:V1"), ("FOLD:2020", "ORIGIN:V2")]
    assert result.reused_existing is False
    rows = result.predictions_path.read_text(encoding="utf-8").splitlines()
    assert rows[0].split(",") == ["fold_id", "experiment_id", "candidate_id", "forecast_origin_id", "true_label", "predicted_score", "status"]
    assert rows[1].endswith(",0.75,SCORED")
    assert rows[2].endswith(",,MODEL_INPUT_INCOMPLETE")
    assert result.manifest["unavailable_count"] == 1
    assert result.manifest["execution_complete"] is True
    assert result.manifest["fit_development_cutoff"] == FMD_MODEL_FITTING_CUTOFF
    assert result.manifest["candidate_ids"] == ["EXP02:CANDIDATE"]
    assert result.manifest["validation_origin_count"] == 2


def test_artifacts_are_deterministic(tmp_path):
    first = _execute(tmp_path / "one", [])
    second = _execute(tmp_path / "two", [])
    assert first.predictions_path.read_bytes() == second.predictions_path.read_bytes()
    assert first.manifest["predictions_sha256"] == second.manifest["predictions_sha256"]
    assert first.manifest == second.manifest


def test_valid_completed_artifact_prevents_second_execution(tmp_path):
    calls = []
    _execute(tmp_path, calls)
    second = _execute(tmp_path, calls)
    assert second.reused_existing is True
    assert calls == [("FOLD:2020", "ORIGIN:V1"), ("FOLD:2020", "ORIGIN:V2")]


def test_completed_artifact_missing_required_validation_origin_is_rejected(tmp_path):
    origins = [
        _origin("ORIGIN:2023:A", "2023-06-01"),
        _origin("ORIGIN:2023:B", "2023-07-01"),
    ]
    _execute_with_coverage(
        tmp_path,
        origins=origins,
        folds=[_calendar_fold(2023, ["ORIGIN:2023:A"])],
    )

    with pytest.raises(Exp02ExecutionIntegrityError, match="structural coverage"):
        _execute_with_coverage(
            tmp_path,
            origins=origins,
            folds=[_calendar_fold(2023, ["ORIGIN:2023:A", "ORIGIN:2023:B"])],
        )


def test_fold_2023_artifact_is_rejected_when_current_folds_include_2024_and_2025(tmp_path):
    origins = [
        _origin("ORIGIN:2023", "2023-06-01"),
        _origin("ORIGIN:2024", "2024-06-01"),
        _origin("ORIGIN:2025", "2025-06-01"),
    ]
    _execute_with_coverage(
        tmp_path,
        origins=origins,
        folds=[_calendar_fold(2023, ["ORIGIN:2023"])],
    )

    with pytest.raises(Exp02ExecutionIntegrityError, match="structural coverage"):
        _execute_with_coverage(
            tmp_path,
            origins=origins,
            folds=[
                _calendar_fold(2023, ["ORIGIN:2023"]),
                _calendar_fold(2024, ["ORIGIN:2024"]),
                _calendar_fold(2025, ["ORIGIN:2025"]),
            ],
        )


def test_duplicate_candidate_fold_origin_coverage_is_rejected():
    fold = Fmd07bFoldInput(
        fold_id="FOLD:2025",
        training_origin_ids=(),
        validation_origin_ids=("ORIGIN:2025",),
        purged_origin_ids=(),
    )
    row = {
        "fold_id": "FOLD:2025",
        "experiment_id": "FMD-EXP-02",
        "candidate_id": "EXP02:CANDIDATE",
        "forecast_origin_id": "ORIGIN:2025",
    }

    with pytest.raises(Exp02ExecutionIntegrityError, match="duplicate candidate/fold/origin"):
        _validate_prediction_coverage(
            [row, row],
            expected_folds=[fold],
            expected_candidate_ids=["EXP02:CANDIDATE"],
        )


@pytest.mark.parametrize("corruption", ("missing_manifest", "bad_hash", "bad_order", "other_experiment"))
def test_malformed_completed_artifact_fails_closed(tmp_path, corruption):
    _execute(tmp_path, [])
    predictions_path = tmp_path / EXP02_ARTIFACT_RELATIVE_DIR / EXP02_PREDICTIONS_FILENAME
    manifest_path = tmp_path / EXP02_ARTIFACT_RELATIVE_DIR / EXP02_MANIFEST_FILENAME
    if corruption == "missing_manifest":
        manifest_path.unlink()
    elif corruption == "bad_hash":
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["predictions_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif corruption == "bad_order":
        lines = predictions_path.read_text(encoding="utf-8").splitlines()
        predictions_path.write_text("\n".join([lines[0], lines[2], lines[1]]) + "\n", encoding="utf-8")
    else:
        lines = predictions_path.read_text(encoding="utf-8").splitlines()
        lines[1] = lines[1].replace("FMD-EXP-02", "FMD-EXP-04")
        predictions_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(Exp02ExecutionIntegrityError):
        _execute(tmp_path, [])


def test_wrong_origin_universe_size_fails_before_runner(tmp_path):
    calls = []
    with pytest.raises(Exp02ExecutionIntegrityError, match="expected 3761"):
        execute_exp02_only(
            tmp_path,
            fit_development_origins=[_origin("ORIGIN:1")],
            calendar_folds=[_fold()],
            spatial_runner=_runner(calls),
            origin_inputs=_inputs,
            true_label_for_origin=lambda _origin: 0,
        )
    assert calls == []


def test_non_exp02_runner_is_rejected(tmp_path):
    runner = _runner([])
    runner.experiment_id = "FMD-EXP-04"
    with pytest.raises(Exp02ExecutionIntegrityError, match="FMD-EXP-02"):
        _execute_with_runner(tmp_path, runner)


def test_no_finalizer_or_canonical_names_are_used(tmp_path):
    result = _execute(tmp_path, [])
    names = {path.name for path in result.predictions_path.parent.iterdir()}
    assert names == {EXP02_PREDICTIONS_FILENAME, EXP02_MANIFEST_FILENAME}
    assert "fmd07b_manifest.json" not in names


def test_authoritative_origin_resolver_matches_persisted_matrix_without_execution():
    origins, hashes = load_authoritative_fit_development_origins(_REPO_ROOT)
    persisted_manifest = json.loads(
        (
            _REPO_ROOT
            / "local_data/processed/fmd/model_development/fmd07b_partial_exp01_exp04"
            / "fmd07b_partial_development_manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert len(origins) == 3761
    assert len({origin.forecast_origin_id for origin in origins}) == 3761
    assert all(origin.forecast_origin_id == f"ORIGIN:{origin.country}:{origin.t0}" for origin in origins)
    assert hashes == persisted_manifest["input_artifact_sha256"]


def test_legacy_manifest_cannot_substitute_for_authoritative_matrix(monkeypatch):
    import components.geospatial_tracking.services.fmd_model_development_7b_execution as upstream

    monkeypatch.setattr(upstream, "R2B3_MATRIX_REL", "local_data/manifests/historical_forecast_origins.csv")
    with pytest.raises((ValueError, Exp02ExecutionIntegrityError)):
        load_authoritative_fit_development_origins(_REPO_ROOT)


def test_wrong_authoritative_cutoff_fails_closed(monkeypatch):
    import components.geospatial_tracking.services.fmd_model_development_7b_exp02_execution as exp02

    monkeypatch.setattr(exp02, "AUTHORITATIVE_FIT_DEVELOPMENT_CUTOFF", "2024-01-01")
    with pytest.raises(Exp02ExecutionIntegrityError, match="t0 < 2024-01-01"):
        load_authoritative_fit_development_origins(_REPO_ROOT)


def test_composition_wires_existing_helpers_and_mocks_execution(monkeypatch, tmp_path):
    import components.geospatial_tracking.services.fmd_model_development_7b_exp02_execution as exp02

    origins = [_origin("ORIGIN:1", "2020-01-15"), _origin("ORIGIN:2", "2020-02-15")]
    fold = SimpleNamespace(
        fold_id="FOLD:2020",
        training_origin_ids=("ORIGIN:1",),
        validation_origin_ids=("ORIGIN:2",),
    )
    matrix_rows = [
        SimpleNamespace(forecast_origin_id="ORIGIN:1", risk_target_label=0),
        SimpleNamespace(forecast_origin_id="ORIGIN:2", risk_target_label=1),
    ]
    reference = SimpleNamespace(reference_profile="PROFILE", unsafe_component_count=0)
    calls = {}

    monkeypatch.setattr(exp02, "load_authoritative_fit_development_origins", lambda _root: (origins, {"hash": "value"}))
    monkeypatch.setattr(exp02, "load_and_verify_r2b3_inputs", lambda _root: SimpleNamespace(matrix=SimpleNamespace(itertuples=lambda index=False: iter(matrix_rows))))
    def fake_build_calendar_year_folds(_origins, *, cutoff):
        calls["calendar_cutoff"] = cutoff
        return [fold]

    monkeypatch.setattr(exp02, "build_calendar_year_folds", fake_build_calendar_year_folds)
    monkeypatch.setattr(exp02, "build_spatial_distance_runner", lambda: "SPATIAL_RUNNER")
    monkeypatch.setattr(exp02, "build_raw_host_snapshots_cached", lambda *args, **kwargs: ({"ORIGIN:2": {"grid_cells": ["CELL"]}}, {}))
    monkeypatch.setattr(exp02, "build_fold_safe_reference", lambda **kwargs: reference)
    monkeypatch.setattr(exp02, "_eligible_source_points", lambda *args, **kwargs: ["SOURCE"])

    def mocked_execute(repo_root, **kwargs):
        calls.update(repo_root=repo_root, **kwargs)
        prepared = kwargs["origin_inputs"](origins[1], fold)
        assert prepared.grid_cells == ["CELL"]
        assert prepared.sources == ["SOURCE"]
        assert prepared.reference_profile == "PROFILE"
        assert prepared.transform_config is not None
        assert prepared.unsafe_component_count == 0
        assert kwargs["true_label_for_origin"](origins[1]) == 1
        return "MOCKED_RESULT"

    monkeypatch.setattr(exp02, "execute_exp02_only", mocked_execute)

    result = run_exp02_composition(
        tmp_path,
        repo="REPOSITORY",
        disease="FMD",
        active_window_days=30,
        grid_config="GRID_CONFIG",
    )

    assert result == "MOCKED_RESULT"
    assert calls["repo_root"] == tmp_path.resolve()
    assert calls["fit_development_origins"] == origins
    assert calls["calendar_folds"] == [fold]
    assert calls["spatial_runner"] == "SPATIAL_RUNNER"
    assert calls["input_hashes"] == {"hash": "value"}
    assert calls["calendar_cutoff"] == FMD_MODEL_FITTING_CUTOFF


def _execute_with_runner(tmp_path: Path, runner):
    return execute_exp02_only(
        tmp_path,
        fit_development_origins=[_origin("ORIGIN:TRAIN", "2019-01-15"), _origin("ORIGIN:V1"), _origin("ORIGIN:V2")],
        calendar_folds=[_fold()],
        spatial_runner=runner,
        origin_inputs=_inputs,
        true_label_for_origin=lambda _origin: 0,
        expected_origin_count=3,
    )


def test_fmd_cutoff_accepts_2024_and_2025_origins_and_rejects_post_cutoff():
    from components.geospatial_tracking.services.model_fitting_exposure import assert_fit_development_only

    fit_origins = [
        _origin("ORIGIN:2024A", "2024-09-15"),
        _origin("ORIGIN:2025A", "2025-06-01"),
    ]
    assert_fit_development_only(fit_origins, cutoff=FMD_MODEL_FITTING_CUTOFF, caller="test_fmd_cutoff_accepts_2024_and_2025_origins_and_rejects_post_cutoff")

    with pytest.raises(ValueError, match="HELD_OUT_FROM_MODEL_FITTING"):
        assert_fit_development_only([_origin("ORIGIN:POST", "2026-01-01")], cutoff=FMD_MODEL_FITTING_CUTOFF)


def test_fmd_calendar_folds_include_2025_but_exclude_origins_at_cutoff():
    folds = build_calendar_year_folds(
        [
            _origin("ORIGIN:2023", "2023-06-01"),
            _origin("ORIGIN:2024", "2024-06-01"),
            _origin("ORIGIN:2025", "2025-06-01"),
            _origin("ORIGIN:POST", "2026-01-01"),
        ],
        cutoff=FMD_MODEL_FITTING_CUTOFF,
    )

    assert [fold.fold_id for fold in folds] == ["FOLD:2023", "FOLD:2024", "FOLD:2025"]
    validation_ids = {
        origin_id
        for fold in folds
        for origin_id in fold.validation_origin_ids
    }
    assert validation_ids == {"ORIGIN:2023", "ORIGIN:2024", "ORIGIN:2025"}
    assert "ORIGIN:POST" not in validation_ids


def test_generic_default_cutoff_stays_unchanged():
    from components.geospatial_tracking.services.model_fitting_exposure import MODEL_FITTING_CUTOFF, assert_fit_development_only

    assert MODEL_FITTING_CUTOFF == "2024-01-01"
    with pytest.raises(ValueError):
        assert_fit_development_only([_origin("ORIGIN:2024", "2024-01-01")], caller="test_generic_default_cutoff_stays_unchanged")


def test_run_exp02_composition_forwards_fmd_cutoff(monkeypatch, tmp_path):
    import components.geospatial_tracking.services.fmd_model_development_7b_exp02_execution as exp02

    origins = [_origin("ORIGIN:1", "2025-01-15"), _origin("ORIGIN:2", "2025-02-15")]
    fold = SimpleNamespace(
        fold_id="FOLD:2025",
        training_origin_ids=("ORIGIN:1",),
        validation_origin_ids=("ORIGIN:2",),
    )
    matrix_rows = [
        SimpleNamespace(forecast_origin_id="ORIGIN:1", risk_target_label=0),
        SimpleNamespace(forecast_origin_id="ORIGIN:2", risk_target_label=1),
    ]
    captured = {}

    monkeypatch.setattr(exp02, "load_authoritative_fit_development_origins", lambda _root: (origins, {"hash": "value"}))
    monkeypatch.setattr(exp02, "load_and_verify_r2b3_inputs", lambda _root: SimpleNamespace(matrix=SimpleNamespace(itertuples=lambda index=False: iter(matrix_rows))))
    def fake_build_calendar_year_folds(_origins, *, cutoff):
        captured["calendar_cutoff"] = cutoff
        return [fold]

    monkeypatch.setattr(exp02, "build_calendar_year_folds", fake_build_calendar_year_folds)
    monkeypatch.setattr(exp02, "build_spatial_distance_runner", lambda: "SPATIAL_RUNNER")
    def fake_build_raw_host_snapshots_cached(*args, **kwargs):
        captured["raw_cutoff"] = kwargs.get("cutoff")
        return {"ORIGIN:2": {"grid_cells": ["CELL"]}}, {}

    monkeypatch.setattr(exp02, "build_raw_host_snapshots_cached", fake_build_raw_host_snapshots_cached)

    reference = SimpleNamespace(reference_profile="PROFILE", unsafe_component_count=0)

    def fake_build_fold_safe_reference(**kwargs):
        captured["fold_cutoff"] = kwargs.get("cutoff")
        return reference

    monkeypatch.setattr(exp02, "build_fold_safe_reference", fake_build_fold_safe_reference)
    monkeypatch.setattr(exp02, "_eligible_source_points", lambda *args, **kwargs: ["SOURCE"])

    def mocked_execute(repo_root, **kwargs):
        prepared = kwargs["origin_inputs"](origins[1], fold)
        assert prepared.grid_cells == ["CELL"]
        assert prepared.sources == ["SOURCE"]
        assert prepared.reference_profile == "PROFILE"
        assert kwargs["true_label_for_origin"](origins[1]) == 1
        return "MOCKED_RESULT"

    monkeypatch.setattr(exp02, "execute_exp02_only", mocked_execute)

    result = run_exp02_composition(
        tmp_path,
        repo="REPOSITORY",
        disease="FMD",
        active_window_days=30,
        grid_config="GRID_CONFIG",
    )

    assert result == "MOCKED_RESULT"
    assert captured["calendar_cutoff"] == FMD_MODEL_FITTING_CUTOFF
    assert captured["raw_cutoff"] == FMD_MODEL_FITTING_CUTOFF
    assert captured["fold_cutoff"] == FMD_MODEL_FITTING_CUTOFF
