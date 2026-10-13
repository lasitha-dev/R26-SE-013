"""FMD-06A: temporal snapshots and the development-only firewall."""

from __future__ import annotations

import csv
import hashlib
import inspect
import json
from collections import Counter
from pathlib import Path

import pytest

from components.geospatial_tracking.data_processing.build_fmd_cohort import (
    FMD_DISEASE,
    FMD_MODEL_FITTING_CUTOFF,
)
from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import (
    SQLiteOutbreakRepository,
)
from components.geospatial_tracking.schemas import (
    AvailabilityQuality,
    DedupStatus,
    GpsQuality,
)
from components.geospatial_tracking.services.development_snapshot import (
    build_fit_development_source_snapshots,
)
from components.geospatial_tracking.services.fmd_calibration import (
    ACTIVE_WINDOW_SELECTION_RULE,
    ACTIVE_WINDOW_ZERO_SOURCE_NON_DISCRIMINATIVE,
    ACTIVE_WINDOW_DAY_CANDIDATES,
    AMENDED_SPATIAL_DOMAIN_STATUS,
    AMENDED_SPATIAL_PARAMETER_CLASSIFICATION,
    AMENDED_SPATIAL_SELECTION_RATIONALE,
    AMENDED_SPATIAL_SELECTION_RULE,
    DIRECTION_SPEED_STATUS,
    FMD06_OVERALL_STATUS_GO,
    FMD_SPATIAL_EVALUATION_RADIUS_KM,
    OUTSIDE_LOCAL_EVALUATION_DOMAIN,
    PA_LOCAL_DOMAIN_AUDIT_FIELDNAMES,
    PRIMARY_TARGET_HORIZON,
    RISK_LABEL_FIELDNAMES,
    SPATIAL_DOMAIN_STATUS_GO,
    SPATIAL_DOMAIN_STATUS_NO_GO,
    SPATIAL_PROTOCOL_AMENDMENT_REASON,
    SPATIAL_PROTOCOL_AMENDMENT_STATUS,
    SPATIAL_RADIUS_CANDIDATE_SOURCE,
    SPATIAL_RADIUS_CANDIDATES_KM,
    SPATIAL_RADIUS_SELECTION_RULE,
    SPATIAL_REFERENCE_SOURCE_SET,
    TEMPORAL_THRESHOLD_ELIGIBLE,
    TEMPORAL_THRESHOLD_NON_BINDING,
    WEATHER_WINDOW_SELECTION_STATUS,
    FMD_MODEL_FITTING_CUTOFF as CALIBRATION_CUTOFF,
    STDBSCAN_SELECTION_RULE,
    build_active_window_sensitivity,
    build_country_balanced_preceding_source_gap_audit,
    build_fmd06_development_source_universe,
    build_fmd06c_domain_candidate_audit,
    build_fmd06c_pa_local_domain_audit,
    build_fmd06c_spatial_target_distance_audit,
    build_fmd06d_risk_origin_labels,
    build_stdbscan_sensitivity,
    derive_stdbscan_candidates,
    run_fmd06c_pa,
    run_fmd06d,
    select_active_window,
    select_frozen_domain_distance,
    summarize_fmd06c_pa_local_domain_audit,
    summarize_fmd06d_risk_origin_labels,
    temporal_threshold_eligibility,
)
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.model_development.domain_design import (
    MODEL_FITTING_CUTOFF as GENERIC_MODEL_FITTING_CUTOFF,
    PREDECLARED_DOMAIN_CANDIDATES_KM,
    build_development_domain_candidate_audit,
)
from components.geospatial_tracking.services.model_fitting_exposure import (
    FIT_DEVELOPMENT,
    HELD_OUT_FROM_MODEL_FITTING,
    SRI_LANKA_TRANSFER_CASE_STUDY,
    fit_development_origins,
)
from components.geospatial_tracking.services.stdbscan.development_source_universe import DevelopmentSource

_REPO_ROOT = Path(__file__).resolve().parents[4]
_COHORT_DIR = _REPO_ROOT / "local_data/processed/fmd/cohort"
_MANIFEST = _COHORT_DIR / "FMD_COHORT_MANIFEST.json"
_ORIGINS = _COHORT_DIR / "fmd_historical_forecast_origins.csv"
_TARGETS = _COHORT_DIR / "fmd_historical_forecast_targets.csv"
_EXPOSURE = _COHORT_DIR / "fmd_model_fitting_exposure_manifest.csv"
_FOLDS = _COHORT_DIR / "fmd_calendar_year_folds.json"
_AUDIT = _COHORT_DIR / "FMD_COHORT_AUDIT.csv"
_CALIBRATION_DIR = _REPO_ROOT / "local_data/processed/fmd/calibration"
_CALIBRATION_FREEZE = _CALIBRATION_DIR / "fmd06_calibration_freeze.json"
_PA_LOCAL_DOMAIN_AUDIT = _CALIBRATION_DIR / "fmd06_pa_local_domain_audit.csv"
_PA_AMENDMENT_SUMMARY = _CALIBRATION_DIR / "fmd06_pa_amendment_summary.json"
_RISK_ORIGIN_LABELS = _CALIBRATION_DIR / "fmd06_risk_origin_labels.csv"
_FMD06_MANIFEST = _CALIBRATION_DIR / "fmd06_calibration_manifest.json"

_EXPECTED_ORIGIN_ROLE_COUNTS = {
    FIT_DEVELOPMENT: 3761,
    HELD_OUT_FROM_MODEL_FITTING: 541,
    SRI_LANKA_TRANSFER_CASE_STUDY: 20,
}


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _forecast_origin(row: dict[str, str]) -> ForecastOrigin:
    trigger_ids = [value for value in row["trigger_source_ids_at_t0"].split(";") if value]
    return ForecastOrigin(
        forecast_origin_id=row["forecast_origin_id"],
        country=row["country"],
        t0=row["t0"],
        temporal_mode=row["temporal_mode"],
        trigger_source_ids_at_t0=trigger_ids,
        trigger_source_count=int(row["trigger_source_count"]),
    )


def _origin(**overrides) -> ForecastOrigin:
    fields = {
        "forecast_origin_id": "ORIGIN:Example:2025-06-10",
        "country": "Example",
        "t0": "2025-06-10",
        "temporal_mode": "RETROSPECTIVE_PROXY",
        "trigger_source_ids_at_t0": ["AT_T0"],
        "trigger_source_count": 1,
    }
    fields.update(overrides)
    return ForecastOrigin(**fields)


def _historical(source_id: str, availability_date: str) -> HistoricalOutbreakRecord:
    return HistoricalOutbreakRecord(
        source_record_id=source_id,
        country="Example",
        disease=FMD_DISEASE,
        outbreak_start_date=availability_date,
        proxy_availability_date=availability_date,
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        proxy_availability_source_field="outbreak_start_date",
        latitude=7.0,
        longitude=80.0,
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.SINGLETON.value,
        model_candidate=True,
    )


def _historical_at(source_id: str, availability_date: str, *, latitude: float = 7.0, longitude: float = 80.0) -> HistoricalOutbreakRecord:
    return HistoricalOutbreakRecord(
        source_record_id=source_id,
        country="Example",
        disease=FMD_DISEASE,
        outbreak_start_date=availability_date,
        proxy_availability_date=availability_date,
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        proxy_availability_source_field="outbreak_start_date",
        latitude=latitude,
        longitude=longitude,
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.SINGLETON.value,
        model_candidate=True,
    )


def _development_source(source_id: str, availability_date: str, *, latitude: float = 7.0) -> DevelopmentSource:
    return _development_source_for_country(source_id, availability_date, country="Example", latitude=latitude)


def _development_source_for_country(
    source_id: str,
    availability_date: str,
    *,
    country: str,
    latitude: float = 7.0,
) -> DevelopmentSource:
    return DevelopmentSource(
        source_id=source_id,
        country=country,
        first_fit_origin_t0_seen=availability_date,
        last_fit_origin_t0_seen=availability_date,
        effective_availability_date=availability_date,
        availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        cluster_event_date=availability_date,
        cluster_event_date_quality="HIGH",
        cluster_event_date_source_field="outbreak_start_date",
        latitude=latitude,
        longitude=80.0,
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.SINGLETON.value,
        model_candidate=True,
    )


@pytest.fixture
def repo(tmp_path):
    repository = SQLiteOutbreakRepository(tmp_path / "fmd06a.db")
    repository.init_schema()
    yield repository
    repository.close()


class _RepositoryAccessMustNotOccur:
    def __getattr__(self, name):
        raise AssertionError(f"repository was accessed through {name!r} before the development firewall")


def test_fmd06a_structured_artifacts_preserve_origin_and_source_event_counts():
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    origin_rows = _csv_rows(_ORIGINS)
    exposure_rows = _csv_rows(_EXPOSURE)
    audit_rows = _csv_rows(_AUDIT)

    origin_ids = {row["forecast_origin_id"] for row in origin_rows}
    exposure_by_origin = {row["forecast_origin_id"]: row["role"] for row in exposure_rows}
    origin_role_counts = Counter(exposure_by_origin.values())
    fit_source_event_rows = [
        row
        for row in audit_rows
        if row["containing_origin_model_fitting_role"] == FIT_DEVELOPMENT
    ]

    assert manifest["forecast_origin_count"] == len(origin_rows) == len(origin_ids) == 4322
    assert len(exposure_rows) == len(exposure_by_origin) == 4322
    assert set(exposure_by_origin) == origin_ids
    assert dict(origin_role_counts) == _EXPECTED_ORIGIN_ROLE_COUNTS
    assert manifest["forecast_origin_role_counts"] == _EXPECTED_ORIGIN_ROLE_COUNTS

    assert len(fit_source_event_rows) == 6799
    assert manifest["included_source_event_role_counts"][FIT_DEVELOPMENT] == 6799
    assert len({row["source_record_id"] for row in fit_source_event_rows}) == 6799
    assert all(exposure_by_origin[row["forecast_origin_id"]] == FIT_DEVELOPMENT for row in fit_source_event_rows)

    fit_trigger_event_count = sum(
        int(row["trigger_source_count"])
        for row in origin_rows
        if exposure_by_origin[row["forecast_origin_id"]] == FIT_DEVELOPMENT
    )
    assert fit_trigger_event_count == 6799
    assert fit_trigger_event_count != origin_role_counts[FIT_DEVELOPMENT]


def test_fmd06a_existing_role_helper_selects_exact_development_origin_rows():
    origin_rows = _csv_rows(_ORIGINS)
    exposure_rows = _csv_rows(_EXPOSURE)
    expected_ids = {
        row["forecast_origin_id"]
        for row in exposure_rows
        if row["role"] == FIT_DEVELOPMENT
    }

    selected = fit_development_origins(
        [_forecast_origin(row) for row in origin_rows],
        cutoff=FMD_MODEL_FITTING_CUTOFF,
    )

    assert len(selected) == 3761
    assert {origin.forecast_origin_id for origin in selected} == expected_ids


@pytest.mark.parametrize(
    ("origin", "rejected_role"),
    [
        (
            _origin(
                forecast_origin_id="ORIGIN:Example:2026-01-01",
                t0=FMD_MODEL_FITTING_CUTOFF,
            ),
            HELD_OUT_FROM_MODEL_FITTING,
        ),
        (
            _origin(
                forecast_origin_id="ORIGIN:Sri Lanka:2025-06-10",
                country="Sri Lanka",
            ),
            SRI_LANKA_TRANSFER_CASE_STUDY,
        ),
    ],
)
def test_fmd06a_non_development_origins_are_rejected_before_repository_access(origin, rejected_role):
    with pytest.raises(ValueError, match=rejected_role):
        build_fit_development_source_snapshots(
            _RepositoryAccessMustNotOccur(),
            [origin],
            disease=FMD_DISEASE,
            active_window_days=30,
            cutoff=FMD_MODEL_FITTING_CUTOFF,
        )


def test_fmd06a_snapshot_includes_before_and_at_t0_but_excludes_after_t0(repo):
    for record in (
        _historical("BEFORE_T0", "2025-06-09"),
        _historical("AT_T0", "2025-06-10"),
        _historical("AFTER_T0", "2025-06-11"),
    ):
        repo.add_historical_record(record)

    snapshots = build_fit_development_source_snapshots(
        repo,
        [_origin()],
        disease=FMD_DISEASE,
        active_window_days=30,
        cutoff=FMD_MODEL_FITTING_CUTOFF,
    )

    assert len(snapshots) == 1  # one forecast-origin row, not one row per source event
    snapshot = snapshots[0]
    assert snapshot.forecast_origin_id == "ORIGIN:Example:2025-06-10"
    assert snapshot.source_ids == ["AT_T0", "BEFORE_T0"]
    assert snapshot.source_count == 2
    assert set(snapshot.source_effective_dates) == {"2025-06-09", "2025-06-10"}
    assert "AFTER_T0" not in snapshot.source_ids


def test_fmd06a_targets_and_folds_reference_the_frozen_origin_ledger_without_role_leakage():
    origin_ids = {row["forecast_origin_id"] for row in _csv_rows(_ORIGINS)}
    target_origin_ids = {row["forecast_origin_id"] for row in _csv_rows(_TARGETS)}
    exposure_by_origin = {
        row["forecast_origin_id"]: row["role"] for row in _csv_rows(_EXPOSURE)
    }
    folds = json.loads(_FOLDS.read_text(encoding="utf-8"))

    assert target_origin_ids <= origin_ids
    for fold in folds:
        fold_origin_ids = (
            fold["training_origin_ids"]
            + fold["validation_origin_ids"]
            + fold["purged_origin_ids"]
        )
        assert all(exposure_by_origin[origin_id] == FIT_DEVELOPMENT for origin_id in fold_origin_ids)


def test_fmd06b_calibration_source_universe_artifact_has_6799_rows():
    rows = _csv_rows(_CALIBRATION_DIR / "fmd06_development_source_universe.csv")
    assert len(rows) == 6799
    assert len({row["source_id"] for row in rows}) == 6799


def test_fmd06b_unique_source_events_are_distinct_from_snapshot_appearances():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    rows = _csv_rows(_CALIBRATION_DIR / "fmd06_stdbscan_sensitivity.csv")
    selected = next(row for row in rows if row["selection_reason"] == STDBSCAN_SELECTION_RULE)
    assert freeze["unique_source_event_count"] == 6799
    assert int(selected["unique_source_event_count"]) == 6799
    assert int(selected["n_active_source_appearances"]) > 6799
    assert freeze["source_event_unit"] == "UNIQUE_SOURCE_EVENT_ID"
    assert freeze["snapshot_event_appearance_unit"] == "SNAPSHOT_EVENT_APPEARANCE"


def test_fmd06b_appearance_metrics_have_explicit_names():
    with (_CALIBRATION_DIR / "fmd06_stdbscan_sensitivity.csv").open(encoding="utf-8", newline="") as handle:
        header = next(csv.reader(handle))
    assert "clustered_snapshot_event_appearance_count" in header
    assert "noise_snapshot_event_appearance_count" in header
    assert "clustered_event_count" not in header
    assert "noise_event_count" not in header


def test_fmd06b_source_universe_rejects_mixed_roles_before_repository_access():
    held_out = _origin(forecast_origin_id="HELD", t0=FMD_MODEL_FITTING_CUTOFF)
    with pytest.raises(ValueError, match=HELD_OUT_FROM_MODEL_FITTING):
        build_fmd06_development_source_universe(
            _RepositoryAccessMustNotOccur(),
            [_origin(), held_out],
            cutoff=CALIBRATION_CUTOFF,
        )


def test_fmd06b_active_window_rejects_held_out_before_source_access():
    held_out = _origin(forecast_origin_id="HELD", t0=FMD_MODEL_FITTING_CUTOFF)
    with pytest.raises(ValueError, match=HELD_OUT_FROM_MODEL_FITTING):
        build_active_window_sensitivity([held_out], [], cutoff=CALIBRATION_CUTOFF)


def test_fmd06b_active_window_rejects_sri_lanka_before_source_access():
    sri_lanka = _origin(forecast_origin_id="SL", country="Sri Lanka")
    with pytest.raises(ValueError, match=SRI_LANKA_TRANSFER_CASE_STUDY):
        build_active_window_sensitivity([sri_lanka], [], cutoff=CALIBRATION_CUTOFF)


def test_fmd06b_active_window_candidates_are_deterministic():
    origins = [_origin(), _origin(forecast_origin_id="O2", t0="2025-06-11")]
    sources = [_development_source("A", "2025-06-10"), _development_source("B", "2025-06-09")]
    first = [audit.as_dict() for audit in build_active_window_sensitivity(origins, sources)]
    second = [audit.as_dict() for audit in build_active_window_sensitivity(list(reversed(origins)), list(reversed(sources)))]
    assert first == second


def test_fmd06b_active_window_candidates_remain_exactly_predeclared_values():
    audits = build_active_window_sensitivity(
        [_origin()],
        [_development_source("A", "2025-06-10"), _development_source("B", "2025-06-09")],
    )
    assert [audit.candidate_window_days for audit in audits] == [7, 14, 21, 28]


def test_fmd06b_zero_source_selector_is_non_discriminative_in_actual_audit():
    rows = _csv_rows(_CALIBRATION_DIR / "fmd06_active_window_candidate_audit.csv")
    assert len({row["zero_source_origin_count"] for row in rows}) == 1
    assert {row["previous_zero_source_criterion_status"] for row in rows} == {
        ACTIVE_WINDOW_ZERO_SOURCE_NON_DISCRIMINATIVE
    }


def test_fmd06b_country_balanced_preceding_source_gap_is_deterministic_and_one_vote_per_country():
    sources = [
        *[_development_source_for_country(f"A{i}", f"2025-01-{i:02d}", country="Dense") for i in range(1, 7)],
        _development_source_for_country("B1", "2025-01-01", country="Sparse"),
        _development_source_for_country("B2", "2025-04-11", country="Sparse"),
    ]
    audit = build_country_balanced_preceding_source_gap_audit(sources)
    assert audit.statistic_name == "COUNTRY_BALANCED_MEDIAN_PRECEDING_SOURCE_GAP_DAYS"
    assert audit.n_countries_contributing_median == 2
    assert audit.country_balanced_median_preceding_source_gap_days == 50.5
    assert [row["country"] for row in audit.per_country] == ["Dense", "Sparse"]
    assert build_country_balanced_preceding_source_gap_audit(list(reversed(sources))).as_dict() == audit.as_dict()


def test_fmd06b_active_window_selection_is_deterministic_and_labelled():
    origins = [_origin()]
    audits = build_active_window_sensitivity(
        origins,
        [_development_source("A", "2025-06-10"), _development_source("B", "2025-06-09")],
    )
    assert select_active_window(audits) == select_active_window(audits)
    status, selected, rule = select_active_window(audits)
    assert status == "GO"
    assert selected == 7
    assert rule == ACTIVE_WINDOW_SELECTION_RULE
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["active_window_classification"] == "DEVELOPMENT_CALIBRATED_TEMPORAL_DATA_PARAMETER"


def test_fmd06b_repaired_active_window_uses_country_balanced_statistic_and_no_targets():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["active_window_gap_statistic_name"] == "COUNTRY_BALANCED_MEDIAN_PRECEDING_SOURCE_GAP_DAYS"
    assert freeze["active_window_gap_statistic_days"] == 13.5
    assert freeze["active_window_days"] == 14
    assert "target" not in inspect.signature(build_active_window_sensitivity).parameters


def test_fmd06b_temporal_threshold_eligibility_is_binding_and_non_binding_candidates_are_visible():
    assert temporal_threshold_eligibility(13.5, 14) == (
        TEMPORAL_THRESHOLD_ELIGIBLE,
        True,
        "satisfies predictor-facing invariant 0 < eps_time_days <= active_window_days",
    )
    rows = _csv_rows(_CALIBRATION_DIR / "fmd06_stdbscan_candidate_audit.csv")
    statuses = {float(row["eps_time_days"]): row["temporal_eligibility_status"] for row in rows}
    assert statuses[50.75] == TEMPORAL_THRESHOLD_NON_BINDING
    assert statuses[5.0] == TEMPORAL_THRESHOLD_ELIGIBLE
    assert statuses[13.5] == TEMPORAL_THRESHOLD_ELIGIBLE


def test_fmd06b_ineligible_temporal_configurations_cannot_be_selected():
    rows = _csv_rows(_CALIBRATION_DIR / "fmd06_stdbscan_sensitivity.csv")
    assert all(
        row["selection_reason"] != STDBSCAN_SELECTION_RULE
        for row in rows
        if row["temporal_eligibility_status"] == TEMPORAL_THRESHOLD_NON_BINDING
    )
    assert all(
        row["predictor_facing_eligible"] == "False"
        for row in rows
        if row["temporal_eligibility_status"] == TEMPORAL_THRESHOLD_NON_BINDING
    )


def test_fmd06b_stdbscan_candidate_generation_uses_development_sources_only():
    sources = [
        _development_source("A", "2025-06-10", latitude=7.000),
        _development_source("B", "2025-06-09", latitude=7.010),
        _development_source("C", "2025-06-08", latitude=7.020),
    ]
    spatial, temporal, min_core, evidence = derive_stdbscan_candidates(sources)
    assert spatial and temporal and min_core == [2, 3, 4]
    assert evidence["country_scoped_parameter_report"]["n_sources_considered"] == 3


def test_fmd06b_stdbscan_rejects_held_out_before_candidate_evaluation():
    held_out = _origin(forecast_origin_id="HELD", t0=FMD_MODEL_FITTING_CUTOFF)
    with pytest.raises(ValueError, match=HELD_OUT_FROM_MODEL_FITTING):
        build_stdbscan_sensitivity([held_out], [], {}, active_window_days=7, eps_space_candidates=[1.0], eps_time_candidates=[1.0], min_core_support_candidates=[2])


def test_fmd06b_stdbscan_rejects_sri_lanka_before_candidate_evaluation():
    sri_lanka = _origin(forecast_origin_id="SL", country="Sri Lanka")
    with pytest.raises(ValueError, match=SRI_LANKA_TRANSFER_CASE_STUDY):
        build_stdbscan_sensitivity([sri_lanka], [], {}, active_window_days=7, eps_space_candidates=[1.0], eps_time_candidates=[1.0], min_core_support_candidates=[2])


def test_fmd06b_stdbscan_candidates_are_deterministic():
    sources = [_development_source("A", "2025-06-10", latitude=7.000), _development_source("B", "2025-06-09", latitude=7.010), _development_source("C", "2025-06-08", latitude=7.020)]
    first = derive_stdbscan_candidates(sources)[:3]
    second = derive_stdbscan_candidates(list(reversed(sources)))[:3]
    assert first == second


def test_fmd06b_future_availability_cannot_change_historical_cluster_structure():
    origin = _origin()
    at_t0 = _development_source("AT", "2025-06-10", latitude=7.000)
    future = _development_source("FUTURE", "2025-06-11", latitude=7.001)
    records = {"AT": _historical("AT", "2025-06-10"), "FUTURE": _historical("FUTURE", "2025-06-11")}
    common = dict(active_window_days=7, eps_space_candidates=[1.0], eps_time_candidates=[1.0], min_core_support_candidates=[2])
    with_future, _ = build_stdbscan_sensitivity([origin], [at_t0, future], records, **common)
    without_future, _ = build_stdbscan_sensitivity([origin], [at_t0], {"AT": records["AT"]}, **common)
    assert with_future == without_future


def test_fmd06b_selected_configuration_is_not_a_frozen_lsd_reference():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["stdbscan_status"] == "GO"
    assert freeze["stdbscan_classification"] == "DEVELOPMENT_CALIBRATED_SOFTWARE_PARAMETERS"
    assert freeze["stdbscan_eps_space_km"] in {0.236038, 5.168879, 18.58035}
    assert freeze["stdbscan_eps_time_days"] in {5.0, 13.5, 50.75}


def test_fmd06b_selected_configuration_and_rule_are_deterministic():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    rows = _csv_rows(_CALIBRATION_DIR / "fmd06_stdbscan_sensitivity.csv")
    selected = [row for row in rows if row["selection_reason"] == STDBSCAN_SELECTION_RULE]
    assert len(selected) == 1
    assert float(selected[0]["eps_space_km"]) == freeze["stdbscan_eps_space_km"]
    assert float(selected[0]["eps_time_days"]) == freeze["stdbscan_eps_time_days"]
    assert int(selected[0]["min_core_supports"]) == freeze["stdbscan_min_core_supports"]


def test_fmd06b_selected_eps_time_does_not_exceed_active_window():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["stdbscan_eps_time_days"] <= freeze["active_window_days"]


def test_fmd06b_no_predictive_model_or_metrics_used():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["predictive_metrics_used"] is False
    assert freeze["held_out_data_used"] is False
    assert freeze["sri_lanka_case_study_data_used"] is False
    assert freeze["ml_model_trained"] is False
    # NOTE: `risk_origin_labels_generated` is a single field on the one
    # shared, evolving `fmd06_calibration_freeze.json` -- it correctly
    # becomes True once FMD-06D actually runs later in the SAME pipeline
    # (see `test_fmd06d_*`), so it is no longer asserted False here. What
    # remains permanently true of FMD-06B specifically is that ITS OWN
    # implementation never writes or references the label artifact.
    from components.geospatial_tracking.services import fmd_calibration as m
    assert "fmd06_risk_origin_labels.csv" not in inspect.getsource(m.run_fmd06b)


def test_fmd06b_cluster_output_is_descriptive_only():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert "descriptive" in freeze["clusters_terminology"]
    assert "transmission" not in freeze["clusters_terminology"].lower()
    assert "causal" not in freeze["clusters_terminology"].lower()


def test_fmd06b_implementation_has_no_predictive_metric_inputs():
    from components.geospatial_tracking.services import fmd_calibration

    for name in ("build_active_window_sensitivity", "build_stdbscan_sensitivity"):
        signature = inspect.signature(getattr(fmd_calibration, name))
        assert not {"target", "label", "outcome", "risk", "prediction", "accuracy"} & set(signature.parameters)


def test_fmd06c_spatial_domain_status_is_resolved_and_no_risk_labels_generated():
    """FMD-06C superseded FMD-06B's `NOT_STARTED_FMD06C` placeholder: the
    spatial-domain status is now a real GO/NO-GO decision, never a
    risk-origin label. (`risk_origin_labels_generated` itself is not
    asserted False here -- see the note in
    `test_fmd06b_no_predictive_model_or_metrics_used` -- FMD-06C's own
    implementation never writing the label artifact is the permanent,
    checkpoint-scoped fact checked instead.)"""
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["spatial_domain_status"] in (SPATIAL_DOMAIN_STATUS_GO, SPATIAL_DOMAIN_STATUS_NO_GO)
    from components.geospatial_tracking.services import fmd_calibration as m
    assert "fmd06_risk_origin_labels.csv" not in inspect.getsource(m.run_fmd06c)


def test_fmd06b_canonical_fmd_and_lsd_inputs_are_unchanged():
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    canonical = _REPO_ROOT / "local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv"
    assert _sha256(canonical) == manifest["source_canonical_csv_sha256"]
    lsd = _REPO_ROOT / "local_data/processed/canonical_outbreaks_conservative.csv"
    if lsd.exists():
        assert _sha256(lsd) == "fa8e77d81b48af6bc2839deb4be9d4046d502ab948ce8e4e67a02a84c281d7f7"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# FMD-06C: spatial-domain (evaluation-radius) calibration.
# ---------------------------------------------------------------------------


def test_fmd06c_1_candidate_registry_matches_domain_design_predeclared_list():
    from components.geospatial_tracking.services.model_development.domain_design import (
        PREDECLARED_DOMAIN_CANDIDATES_KM,
    )

    assert SPATIAL_RADIUS_CANDIDATES_KM == PREDECLARED_DOMAIN_CANDIDATES_KM
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["spatial_radius_candidates_km"] == list(PREDECLARED_DOMAIN_CANDIDATES_KM)
    assert freeze["spatial_radius_candidate_source"] == SPATIAL_RADIUS_CANDIDATE_SOURCE


def test_fmd06c_2_candidate_list_is_an_immutable_tuple_runtime_cannot_append():
    assert isinstance(SPATIAL_RADIUS_CANDIDATES_KM, tuple)
    with pytest.raises(AttributeError):
        SPATIAL_RADIUS_CANDIDATES_KM.append(9999.0)


def test_fmd06c_3_candidate_list_is_independent_of_stdbscan_eps_space():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["stdbscan_eps_space_km"] not in freeze["spatial_radius_candidates_km"]
    assert "eps_space" not in SPATIAL_RADIUS_CANDIDATE_SOURCE


def test_fmd06c_4_active_window_days_remains_14():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["active_window_days"] == 14
    assert freeze["active_window_status"] == "GO"


def test_fmd06c_5_stdbscan_values_remain_unchanged():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["stdbscan_eps_space_km"] == 0.236038
    assert freeze["stdbscan_eps_time_days"] == 13.5
    assert freeze["stdbscan_min_core_supports"] == 4
    assert freeze["stdbscan_status"] == "GO"


def test_fmd06c_6_distance_audit_rows_are_all_fit_development():
    rows = _csv_rows(_CALIBRATION_DIR / "fmd06_spatial_target_distance_audit.csv")
    assert rows
    assert {row["containing_origin_model_fitting_role"] for row in rows} == {FIT_DEVELOPMENT}


def test_fmd06c_7_spatial_target_distance_audit_rejects_held_out_before_repository_access():
    held_out = _origin(forecast_origin_id="HELD", t0=FMD_MODEL_FITTING_CUTOFF)
    with pytest.raises(ValueError, match=HELD_OUT_FROM_MODEL_FITTING):
        build_fmd06c_spatial_target_distance_audit(_RepositoryAccessMustNotOccur(), [held_out], active_window_days=14)


def test_fmd06c_8_spatial_target_distance_audit_rejects_sri_lanka_before_repository_access():
    sri_lanka = _origin(forecast_origin_id="SL", country="Sri Lanka")
    with pytest.raises(ValueError, match=SRI_LANKA_TRANSFER_CASE_STUDY):
        build_fmd06c_spatial_target_distance_audit(_RepositoryAccessMustNotOccur(), [sri_lanka], active_window_days=14)


def test_fmd06c_9_source_snapshot_lower_bound_is_inclusive_t0_minus_active_window(repo):
    origin = _origin()
    for record in (
        _historical_at("IN_WINDOW", "2025-05-27"),  # exactly t0 - 14 days: included
        _historical_at("OUT_OF_WINDOW", "2025-05-26"),  # t0 - 15 days: excluded
        _historical_at("TARGET", "2025-06-12"),  # lead_days=2: a D1-D7 target, never a source
    ):
        repo.add_historical_record(record)

    rows = build_fmd06c_spatial_target_distance_audit(repo, [origin], active_window_days=14)

    assert rows
    assert rows[0]["active_source_count"] == 1
    assert rows[0]["nearest_active_source_event_id"] == "IN_WINDOW"


def test_fmd06c_10_source_snapshot_excludes_sources_strictly_after_t0(repo):
    origin = _origin()
    for record in (
        _historical_at("AT_T0", "2025-06-10"),
        _historical_at("AFTER_T0", "2025-06-11"),
        _historical_at("TARGET", "2025-06-12"),
    ):
        repo.add_historical_record(record)

    rows = build_fmd06c_spatial_target_distance_audit(repo, [origin], active_window_days=14)

    assert rows
    assert rows[0]["active_source_count"] == 1
    assert rows[0]["nearest_active_source_event_id"] == "AT_T0"


def test_fmd06c_11_source_reference_set_is_all_eligible_active_sources_at_t0():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["spatial_reference_source_set"] == "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0"
    assert SPATIAL_REFERENCE_SOURCE_SET == "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0"


def test_fmd06c_12_nearest_source_search_considers_every_eligible_active_source_not_just_the_trigger(repo):
    origin = _origin(trigger_source_ids_at_t0=["TRIGGER"], trigger_source_count=1)
    for record in (
        _historical_at("TRIGGER", "2025-06-10", latitude=7.000),
        _historical_at("CLOSER_NON_TRIGGER", "2025-06-09", latitude=7.001),
        _historical_at("TARGET", "2025-06-12", latitude=7.001),
    ):
        repo.add_historical_record(record)

    rows = build_fmd06c_spatial_target_distance_audit(repo, [origin], active_window_days=14)

    assert rows
    assert rows[0]["active_source_count"] == 2
    assert rows[0]["nearest_active_source_event_id"] == "CLOSER_NON_TRIGGER"


def test_fmd06c_13_uses_the_repository_geodesic_distance_km_helper():
    from components.geospatial_tracking.services import fmd_calibration as m
    from components.geospatial_tracking.services.geospatial.distance import distance_km

    assert m.distance_km is distance_km


def test_fmd06c_14_distance_audit_respects_the_frozen_d1_d7_target_horizon():
    rows = _csv_rows(_CALIBRATION_DIR / "fmd06_spatial_target_distance_audit.csv")
    assert rows
    assert all(1 <= int(row["target_horizon"]) <= 7 for row in rows)


def test_fmd06c_15_target_appearance_count_and_unique_target_event_count_are_separate():
    rows = _csv_rows(_CALIBRATION_DIR / "fmd06_spatial_target_distance_audit.csv")
    candidate_rows = _csv_rows(_CALIBRATION_DIR / "fmd06_spatial_domain_candidate_audit.csv")
    n_appearances = len(rows)
    n_unique = len({row["target_event_id"] for row in rows})

    assert n_appearances > n_unique  # the same real target event legitimately reappears from earlier origins
    assert int(candidate_rows[0]["target_event_appearance_count"]) == n_appearances
    assert int(candidate_rows[0]["unique_target_event_count"]) == n_unique


def test_fmd06c_16_forecast_origin_count_and_target_counts_are_separate():
    rows = _csv_rows(_CALIBRATION_DIR / "fmd06_spatial_target_distance_audit.csv")
    candidate_rows = _csv_rows(_CALIBRATION_DIR / "fmd06_spatial_domain_candidate_audit.csv")
    n_origins_with_eligible_target = len({row["forecast_origin_id"] for row in rows})
    evaluated_origin_count = int(candidate_rows[0]["evaluated_forecast_origin_count"])

    assert evaluated_origin_count == 3761  # the frozen FIT_DEVELOPMENT forecast-origin count
    assert n_origins_with_eligible_target < evaluated_origin_count  # not every origin has a D1-D7 eligible target
    assert int(candidate_rows[0]["origins_with_eligible_target"]) == n_origins_with_eligible_target


def test_fmd06c_17_candidate_audit_is_deterministic_regardless_of_origin_order(repo):
    origins = [_origin(), _origin(forecast_origin_id="O2", country="Example", t0="2025-06-11")]
    for record in (
        _historical_at("A", "2025-06-10"),
        _historical_at("B", "2025-06-11"),
        _historical_at("T1", "2025-06-12"),
    ):
        repo.add_historical_record(record)

    rows_forward = build_fmd06c_spatial_target_distance_audit(repo, origins, active_window_days=14)
    rows_reversed = build_fmd06c_spatial_target_distance_audit(repo, list(reversed(origins)), active_window_days=14)
    audits_forward, coverage_forward = build_development_domain_candidate_audit(
        repo, fit_development_origins=origins, disease=FMD_DISEASE, active_window_days=14,
        model_fitting_cutoff=FMD_MODEL_FITTING_CUTOFF,
    )
    audits_reversed, coverage_reversed = build_development_domain_candidate_audit(
        repo, fit_development_origins=list(reversed(origins)), disease=FMD_DISEASE, active_window_days=14,
        model_fitting_cutoff=FMD_MODEL_FITTING_CUTOFF,
    )
    audit_forward = build_fmd06c_domain_candidate_audit(origins, audits_forward, coverage_forward)
    audit_reversed = build_fmd06c_domain_candidate_audit(list(reversed(origins)), audits_reversed, coverage_reversed)

    assert rows_forward == rows_reversed
    assert audit_forward == audit_reversed


def test_fmd06c_18_selection_function_is_imported_unchanged_from_domain_design():
    from components.geospatial_tracking.services.model_development import domain_design
    from components.geospatial_tracking.services import fmd_calibration as m

    assert m.select_frozen_domain_distance is domain_design.select_frozen_domain_distance
    assert select_frozen_domain_distance is domain_design.select_frozen_domain_distance


def test_fmd06c_19_selected_radius_if_go_belongs_to_the_frozen_candidate_list():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    if freeze["spatial_domain_status"] == SPATIAL_DOMAIN_STATUS_GO:
        assert freeze["spatial_evaluation_radius_km"] in freeze["spatial_radius_candidates_km"]
        assert freeze["spatial_parameter_classification"] == "DEVELOPMENT_CALIBRATED_GEOSPATIAL_EVALUATION_PARAMETER"
    else:
        assert freeze["spatial_domain_status"] == SPATIAL_DOMAIN_STATUS_NO_GO
        assert freeze["spatial_evaluation_radius_km"] is None
        assert freeze["spatial_parameter_classification"] is None


def test_fmd06c_20_selection_rule_never_defaults_to_the_largest_candidate():
    from components.geospatial_tracking.services.model_development.domain_design import DomainCandidateAudit

    audits = [
        DomainCandidateAudit(candidate_distance_km=10.0, n_targets_total=5, n_targets_covered=5, coverage_fraction=1.0, n_targets_uncovered=0, uncovered_target_ids=()),
        DomainCandidateAudit(candidate_distance_km=20.0, n_targets_total=5, n_targets_covered=5, coverage_fraction=1.0, n_targets_uncovered=0, uncovered_target_ids=()),
    ]
    selected, status = select_frozen_domain_distance(audits)
    assert selected == 10.0  # the smallest full-coverage candidate is chosen, never the largest


def test_fmd06c_21_selected_radius_is_not_the_stdbscan_eps_space_by_derivation():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["stdbscan_eps_space_km"] not in freeze["spatial_radius_candidates_km"]
    if freeze["spatial_evaluation_radius_km"] is not None:
        assert freeze["spatial_evaluation_radius_km"] != freeze["stdbscan_eps_space_km"]


def test_fmd06c_22_no_risk_origin_labels_file_is_generated():
    """FMD-06C's own implementation never writes the risk-origin label
    file -- that remains FMD-06D's job (`run_fmd06d`), run separately and
    later in the pipeline. (This checks `run_fmd06c`'s own source, not
    live disk/freeze state, since `fmd06_risk_origin_labels.csv` and
    `risk_origin_labels_generated` correctly exist/flip True once FMD-06D
    itself runs later against the same shared calibration directory --
    see `test_fmd06d_*`.)"""
    from components.geospatial_tracking.services import fmd_calibration as m
    assert "fmd06_risk_origin_labels.csv" not in inspect.getsource(m.run_fmd06c)
    assert "fmd06_risk_origin_labels.csv" not in inspect.getsource(m.build_fmd06c_domain_candidate_audit)


def test_fmd06c_23_no_predictive_model_or_held_out_or_case_study_data_used():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["ml_model_trained"] is False
    assert freeze["predictive_metrics_used"] is False
    assert freeze["held_out_data_used"] is False
    assert freeze["sri_lanka_case_study_data_used"] is False


def test_fmd06c_implementation_has_no_predictive_metric_inputs():
    from components.geospatial_tracking.services import fmd_calibration

    for name in ("build_fmd06c_spatial_target_distance_audit", "build_fmd06c_domain_candidate_audit"):
        signature = inspect.signature(getattr(fmd_calibration, name))
        assert not {"target", "label", "outcome", "risk", "prediction", "accuracy"} & set(signature.parameters)


# ---------------------------------------------------------------------------
# FMD-06C-R2: removes the FMD-specific cutoff workaround, FMD-06C now calls
# the generic domain_design.build_development_domain_candidate_audit
# directly (R1 made its cutoff caller-suppliable).
# ---------------------------------------------------------------------------


def test_fmd06c_r2_1_run_fmd06c_calls_the_generic_domain_audit_builder():
    from components.geospatial_tracking.services import fmd_calibration as m

    source = inspect.getsource(m.run_fmd06c)
    assert "build_development_domain_candidate_audit(" in source


def test_fmd06c_r2_2_run_fmd06c_supplies_the_explicit_fmd_cutoff():
    from components.geospatial_tracking.services import fmd_calibration as m

    source = inspect.getsource(m.run_fmd06c)
    assert "model_fitting_cutoff=cutoff" in source
    assert inspect.signature(m.run_fmd06c).parameters["cutoff"].default == FMD_MODEL_FITTING_CUTOFF


def test_fmd06c_r2_3_manual_domain_candidate_audit_construction_no_longer_exists():
    from components.geospatial_tracking.services import fmd_calibration as m

    source = inspect.getsource(m.build_fmd06c_domain_candidate_audit)
    assert "DomainCandidateAudit(" not in source  # no more manually re-derived rows


def test_fmd06c_r2_4_generic_default_cutoff_still_rejects_an_fmd_fit_development_origin():
    # under the GENERIC module's own default cutoff (2024-01-01, not FMD's
    # 2026-01-01), a legitimate FMD FIT_DEVELOPMENT origin dated inside
    # [2024-01-01, 2026-01-01) is HELD_OUT -- proving the generic default
    # behavior is unchanged and does not silently know about FMD.
    origin = _origin(forecast_origin_id="ORIGIN:Example:2024-06-01", t0="2024-06-01")
    assert GENERIC_MODEL_FITTING_CUTOFF == "2024-01-01"
    with pytest.raises(ValueError, match=HELD_OUT_FROM_MODEL_FITTING):
        build_development_domain_candidate_audit(
            None, fit_development_origins=[origin], disease=FMD_DISEASE, active_window_days=14,
        )


def test_fmd06c_r2_5_explicit_fmd_cutoff_accepts_the_same_origin(repo):
    # the exact origin the generic default rejects is accepted once
    # FMD_MODEL_FITTING_CUTOFF is forwarded explicitly.
    origin = _origin(forecast_origin_id="ORIGIN:Example:2024-06-01", t0="2024-06-01")
    audits, rows = build_development_domain_candidate_audit(
        repo, fit_development_origins=[origin], disease=FMD_DISEASE, active_window_days=14,
        model_fitting_cutoff=FMD_MODEL_FITTING_CUTOFF,
    )
    assert len(audits) == len(PREDECLARED_DOMAIN_CANDIDATES_KM)  # no rejection


def test_fmd06c_r2_6_held_out_origin_still_rejected_under_the_fmd_cutoff(repo):
    origin = _origin(forecast_origin_id="ORIGIN:Example:2026-06-01", t0="2026-06-01")
    with pytest.raises(ValueError, match=HELD_OUT_FROM_MODEL_FITTING):
        build_development_domain_candidate_audit(
            repo, fit_development_origins=[origin], disease=FMD_DISEASE, active_window_days=14,
            model_fitting_cutoff=FMD_MODEL_FITTING_CUTOFF,
        )


def test_fmd06c_r2_7_sri_lanka_origin_still_rejected_under_the_fmd_cutoff(repo):
    sri_lanka = _origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-06-01", country="Sri Lanka", t0="2020-06-01")
    with pytest.raises(ValueError, match=SRI_LANKA_TRANSFER_CASE_STUDY):
        build_development_domain_candidate_audit(
            repo, fit_development_origins=[sri_lanka], disease=FMD_DISEASE, active_window_days=14,
            model_fitting_cutoff=FMD_MODEL_FITTING_CUTOFF,
        )


def test_fmd06c_r2_8_candidate_registry_still_exactly_the_predeclared_six_values():
    assert SPATIAL_RADIUS_CANDIDATES_KM == PREDECLARED_DOMAIN_CANDIDATES_KM
    assert SPATIAL_RADIUS_CANDIDATES_KM == (25.0, 50.0, 75.0, 100.0, 150.0, 200.0)


def test_fmd06c_r2_9_selection_function_still_the_unwrapped_generic_one():
    from components.geospatial_tracking.services.model_development import domain_design

    assert select_frozen_domain_distance is domain_design.select_frozen_domain_distance


def test_fmd06c_r2_10_rebuilt_candidate_coverage_matches_the_pre_repair_workaround_result():
    """The R1-repaired generic call must reproduce the exact pre-repair
    workaround numbers reported before this refactor -- development
    origins=3761, origins with >=1 eligible D1-D7 target=2359, target
    appearances=17965, unique target events=4906, the same per-radius
    coverage counts, and the same NO-GO/None outcome."""
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    distance_rows = _csv_rows(_CALIBRATION_DIR / "fmd06_spatial_target_distance_audit.csv")
    candidate_rows = _csv_rows(_CALIBRATION_DIR / "fmd06_spatial_domain_candidate_audit.csv")

    assert freeze["development_origin_count"] == 3761
    assert len({row["forecast_origin_id"] for row in distance_rows}) == 2359
    assert len(distance_rows) == 17965
    assert len({row["target_event_id"] for row in distance_rows}) == 4906

    expected_within_radius = {
        25.0: 12148, 50.0: 14144, 75.0: 15269, 100.0: 15991, 150.0: 16715, 200.0: 17106,
    }
    by_radius = {float(row["candidate_radius_km"]): row for row in candidate_rows}
    for radius, expected in expected_within_radius.items():
        assert int(by_radius[radius]["target_appearances_within_radius"]) == expected
        assert int(by_radius[radius]["target_event_appearance_count"]) == 17965

    assert freeze["spatial_domain_status"] == SPATIAL_DOMAIN_STATUS_NO_GO
    assert freeze["spatial_evaluation_radius_km"] is None


# ---------------------------------------------------------------------------
# FMD-06C-PA: transparent, post-feasibility spatial-domain protocol amendment.
# ---------------------------------------------------------------------------


def test_fmd06c_pa_1_original_no_go_is_preserved():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["spatial_domain_status"] == SPATIAL_DOMAIN_STATUS_NO_GO


def test_fmd06c_pa_2_original_selected_radius_remains_null_in_provenance():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["spatial_evaluation_radius_km"] is None
    assert freeze["original_spatial_evaluation_radius_km"] is None
    assert freeze["original_spatial_domain_status"] == SPATIAL_DOMAIN_STATUS_NO_GO


def test_fmd06c_pa_3_original_candidate_registry_unchanged():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["spatial_radius_candidates_km"] == [25.0, 50.0, 75.0, 100.0, 150.0, 200.0]
    assert freeze["original_spatial_radius_candidates_km"] == [25.0, 50.0, 75.0, 100.0, 150.0, 200.0]
    assert SPATIAL_RADIUS_CANDIDATES_KM == (25.0, 50.0, 75.0, 100.0, 150.0, 200.0)


def test_fmd06c_pa_4_amendment_explicitly_labelled_post_feasibility():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["spatial_protocol_amendment_status"] == "POST_FEASIBILITY_PROTOCOL_AMENDMENT"
    assert SPATIAL_PROTOCOL_AMENDMENT_STATUS == "POST_FEASIBILITY_PROTOCOL_AMENDMENT"
    assert freeze["spatial_protocol_amendment_reason"] == SPATIAL_PROTOCOL_AMENDMENT_REASON


def test_fmd06c_pa_5_amendment_is_not_labelled_preregistered():
    assert "preregist" not in SPATIAL_PROTOCOL_AMENDMENT_STATUS.lower()
    assert "not preregistered" in AMENDED_SPATIAL_SELECTION_RATIONALE.lower()
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert "preregist" not in freeze["spatial_protocol_amendment_status"].lower()
    assert "preregist" not in freeze["amended_spatial_domain_status"].lower()


def test_fmd06c_pa_6_amended_radius_equals_200km():
    assert FMD_SPATIAL_EVALUATION_RADIUS_KM == 200.0
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["amended_spatial_evaluation_radius_km"] == 200.0


def test_fmd06c_pa_7_200km_already_belonged_to_the_predeclared_registry():
    assert 200.0 in PREDECLARED_DOMAIN_CANDIDATES_KM
    assert 200.0 in SPATIAL_RADIUS_CANDIDATES_KM


def test_fmd06c_pa_8_no_new_radius_was_introduced():
    assert FMD_SPATIAL_EVALUATION_RADIUS_KM == max(PREDECLARED_DOMAIN_CANDIDATES_KM)
    for bad_radius in (175.0, 250.0, 201.0):
        with pytest.raises(ValueError, match="predeclared candidate"):
            run_fmd06c_pa(
                _REPO_ROOT / "local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv",
                _ORIGINS,
                _CALIBRATION_DIR,
                radius_km=bad_radius,
            )


def test_fmd06c_pa_9_amended_rule_is_maximum_predeclared_local_evaluation_domain():
    assert AMENDED_SPATIAL_SELECTION_RULE == "MAXIMUM_PREDECLARED_LOCAL_EVALUATION_DOMAIN"
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["amended_spatial_selection_rule"] == "MAXIMUM_PREDECLARED_LOCAL_EVALUATION_DOMAIN"


def test_fmd06c_pa_10_amended_choice_implementation_has_no_predictive_metric_inputs():
    from components.geospatial_tracking.services import fmd_calibration

    for name in ("run_fmd06c_pa", "build_fmd06c_pa_local_domain_audit", "summarize_fmd06c_pa_local_domain_audit"):
        signature = inspect.signature(getattr(fmd_calibration, name))
        assert not {"target", "label", "outcome", "risk", "prediction", "accuracy"} & set(signature.parameters)


def test_fmd06c_pa_11_local_domain_audit_rejects_held_out_before_any_coverage_row_use():
    held_out = _origin(forecast_origin_id="HELD", t0=FMD_MODEL_FITTING_CUTOFF)
    with pytest.raises(ValueError, match=HELD_OUT_FROM_MODEL_FITTING):
        build_fmd06c_pa_local_domain_audit([held_out], [], cutoff=FMD_MODEL_FITTING_CUTOFF)


def test_fmd06c_pa_12_local_domain_audit_rejects_sri_lanka_before_any_coverage_row_use():
    sri_lanka = _origin(forecast_origin_id="SL", country="Sri Lanka")
    with pytest.raises(ValueError, match=SRI_LANKA_TRANSFER_CASE_STUDY):
        build_fmd06c_pa_local_domain_audit([sri_lanka], [], cutoff=FMD_MODEL_FITTING_CUTOFF)


def test_fmd06c_pa_13_stdbscan_eps_space_remains_distinct_from_200km():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["stdbscan_eps_space_km"] == 0.236038
    assert freeze["stdbscan_eps_space_km"] != freeze["amended_spatial_evaluation_radius_km"]


def test_fmd06c_pa_14_local_binary_semantics_use_one_row_per_forecast_origin():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    rows = _csv_rows(_PA_LOCAL_DOMAIN_AUDIT)
    assert len(rows) == freeze["development_origin_count"] == 3761
    assert len({row["forecast_origin_id"] for row in rows}) == len(rows)  # exactly one row per origin


def test_fmd06c_pa_15_outside_domain_target_flag_is_defined():
    assert "outside_domain_target_present" in PA_LOCAL_DOMAIN_AUDIT_FIELDNAMES
    rows = _csv_rows(_PA_LOCAL_DOMAIN_AUDIT)
    assert "outside_domain_target_present" in rows[0]
    # an origin with a farther-only target is distinguishable from one with no target at all
    no_target = [r for r in rows if r["has_eligible_d1_d7_target"] == "False"]
    outside_only = [r for r in rows if r["has_eligible_d1_d7_target"] == "True" and r["local_domain_positive"] == "False"]
    assert all(r["outside_domain_target_present"] == "False" for r in no_target)
    assert all(r["outside_domain_target_present"] == "True" for r in outside_only)
    assert no_target and outside_only  # both sub-populations are actually present in the real corpus


def test_fmd06c_pa_16_target_appearances_remain_separate_from_unique_events():
    summary = json.loads(_PA_AMENDMENT_SUMMARY.read_text(encoding="utf-8"))
    assert summary["target_event_appearance_count"] == 17965
    assert summary["unique_target_event_count"] == 4906
    assert summary["target_event_appearance_count"] > summary["unique_target_event_count"]


def test_fmd06c_pa_17_no_final_risk_origin_label_file_is_generated_yet():
    """FMD-06C-PA's own implementation never writes the final risk-origin
    label file -- that remains FMD-06D's job (`run_fmd06d`), run
    separately and later. (Checks `run_fmd06c_pa`'s own source, not live
    disk/freeze state -- see the note on `test_fmd06c_22_*` above.)"""
    from components.geospatial_tracking.services import fmd_calibration as m
    assert "fmd06_risk_origin_labels.csv" not in inspect.getsource(m.run_fmd06c_pa)
    assert "fmd06_risk_origin_labels.csv" not in inspect.getsource(m.build_fmd06c_pa_local_domain_audit)
    assert "fmd06_risk_origin_labels.csv" not in inspect.getsource(m.summarize_fmd06c_pa_local_domain_audit)


def test_fmd06c_pa_18_no_predictive_ml_model_is_trained():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert freeze["ml_model_trained"] is False
    assert freeze["predictive_metrics_used"] is False
    assert freeze["held_out_data_used_for_amendment"] is False
    assert freeze["sri_lanka_data_used_for_amendment"] is False
    assert freeze["predictive_metrics_used_for_amendment"] is False


def test_fmd06c_pa_19_summary_reconciles_with_local_domain_audit_rows():
    rows = _csv_rows(_PA_LOCAL_DOMAIN_AUDIT)
    summary = json.loads(_PA_AMENDMENT_SUMMARY.read_text(encoding="utf-8"))
    positive = sum(row["local_domain_positive"] == "True" for row in rows)
    no_target = sum(row["has_eligible_d1_d7_target"] == "False" for row in rows)
    outside_only = sum(
        row["has_eligible_d1_d7_target"] == "True" and row["local_domain_positive"] == "False" for row in rows
    )
    assert positive + no_target + outside_only == len(rows)
    assert positive == summary["origins_with_target_within_local_domain"]
    assert no_target == summary["origins_without_eligible_d1_d7_target"]
    assert outside_only == summary["origins_with_eligible_target_all_outside_local_domain"]
    assert summary["origin_level_positive_fraction"] == round(positive / len(rows), 6)


def test_fmd06c_pa_20_reproducible_sha256_across_two_independent_builds(tmp_path):
    canonical = _REPO_ROOT / "local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv"
    names = ["fmd06_pa_local_domain_audit.csv", "fmd06_pa_amendment_summary.json", "fmd06_calibration_freeze.json"]

    def _build(out_dir: Path) -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in _CALIBRATION_DIR.iterdir():
            if name.name not in ("fmd06_pa_local_domain_audit.csv", "fmd06_pa_amendment_summary.json"):
                (out_dir / name.name).write_bytes(name.read_bytes())
        run_fmd06c_pa(canonical, _ORIGINS, out_dir)
        return {name: hashlib.sha256((out_dir / name).read_bytes()).hexdigest() for name in names}

    run1 = _build(tmp_path / "run1")
    run2 = _build(tmp_path / "run2")
    assert run1 == run2


# ---------------------------------------------------------------------------
# FMD-06D: deterministic development label freeze + final FMD-06 manifest.
# ---------------------------------------------------------------------------


def test_fmd06d_1_label_artifact_has_exactly_3761_rows():
    rows = _csv_rows(_RISK_ORIGIN_LABELS)
    assert len(rows) == 3761


def test_fmd06d_2_forecast_origin_id_is_unique():
    rows = _csv_rows(_RISK_ORIGIN_LABELS)
    ids = [row["forecast_origin_id"] for row in rows]
    assert len(ids) == len(set(ids))


def test_fmd06d_3_all_rows_are_fit_development():
    rows = _csv_rows(_RISK_ORIGIN_LABELS)
    assert {row["model_fitting_role"] for row in rows} == {FIT_DEVELOPMENT}


def test_fmd06d_4_held_out_origins_cannot_enter():
    held_out = _origin(forecast_origin_id="HELD", t0=FMD_MODEL_FITTING_CUTOFF)
    with pytest.raises(ValueError, match=HELD_OUT_FROM_MODEL_FITTING):
        build_fmd06d_risk_origin_labels([held_out], [], cutoff=FMD_MODEL_FITTING_CUTOFF)


def test_fmd06d_5_sri_lanka_origins_cannot_enter():
    sri_lanka = _origin(forecast_origin_id="SL", country="Sri Lanka")
    with pytest.raises(ValueError, match=SRI_LANKA_TRANSFER_CASE_STUDY):
        build_fmd06d_risk_origin_labels([sri_lanka], [], cutoff=FMD_MODEL_FITTING_CUTOFF)


def test_fmd06d_6_labels_are_exactly_binary():
    rows = _csv_rows(_RISK_ORIGIN_LABELS)
    assert {row["risk_target_label"] for row in rows} == {"0", "1"}


def test_fmd06d_7_positive_count_is_2215():
    rows = _csv_rows(_RISK_ORIGIN_LABELS)
    assert sum(row["risk_target_label"] == "1" for row in rows) == 2215


def test_fmd06d_8_negative_count_is_1546():
    rows = _csv_rows(_RISK_ORIGIN_LABELS)
    assert sum(row["risk_target_label"] == "0" for row in rows) == 1546


def test_fmd06d_9_no_target_negative_count_is_1402():
    rows = _csv_rows(_RISK_ORIGIN_LABELS)
    assert sum(row["has_eligible_d1_d7_target"] == "False" for row in rows) == 1402


def test_fmd06d_10_outside_domain_only_negative_count_is_144():
    rows = _csv_rows(_RISK_ORIGIN_LABELS)
    outside_only = sum(
        row["has_eligible_d1_d7_target"] == "True" and row["risk_target_label"] == "0" for row in rows
    )
    assert outside_only == 144


def test_fmd06d_11_reconciliation_sums_to_3761():
    rows = _csv_rows(_RISK_ORIGIN_LABELS)
    positive = sum(row["risk_target_label"] == "1" for row in rows)
    no_target = sum(row["has_eligible_d1_d7_target"] == "False" for row in rows)
    outside_only = sum(
        row["has_eligible_d1_d7_target"] == "True" and row["risk_target_label"] == "0" for row in rows
    )
    assert positive == 2215 and no_target == 1402 and outside_only == 144
    assert positive + no_target + outside_only == 3761


def test_fmd06d_12_positive_fraction_is_0_588939():
    manifest = json.loads(_FMD06_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["positive_fraction"] == 0.588939
    rows = _csv_rows(_RISK_ORIGIN_LABELS)
    positive = sum(row["risk_target_label"] == "1" for row in rows)
    assert round(positive / len(rows), 6) == 0.588939


def test_fmd06d_13_every_label_row_corresponds_1to1_with_pa_local_domain_audit():
    label_ids = {row["forecast_origin_id"] for row in _csv_rows(_RISK_ORIGIN_LABELS)}
    audit_ids = {row["forecast_origin_id"] for row in _csv_rows(_PA_LOCAL_DOMAIN_AUDIT)}
    assert label_ids == audit_ids
    assert len(label_ids) == len(_csv_rows(_RISK_ORIGIN_LABELS)) == len(_csv_rows(_PA_LOCAL_DOMAIN_AUDIT))


def test_fmd06d_14_risk_label_equals_local_domain_positive_deterministically():
    labels_by_id = {row["forecast_origin_id"]: row for row in _csv_rows(_RISK_ORIGIN_LABELS)}
    for audit_row in _csv_rows(_PA_LOCAL_DOMAIN_AUDIT):
        label_row = labels_by_id[audit_row["forecast_origin_id"]]
        expected = "1" if audit_row["local_domain_positive"] == "True" else "0"
        assert label_row["risk_target_label"] == expected


def test_fmd06d_15_outside_domain_target_present_is_preserved():
    assert "outside_domain_target_present" in RISK_LABEL_FIELDNAMES
    labels_by_id = {row["forecast_origin_id"]: row for row in _csv_rows(_RISK_ORIGIN_LABELS)}
    for audit_row in _csv_rows(_PA_LOCAL_DOMAIN_AUDIT):
        label_row = labels_by_id[audit_row["forecast_origin_id"]]
        assert label_row["outside_domain_target_present"] == audit_row["outside_domain_target_present"]


def test_fmd06d_16_outside_only_negatives_remain_distinguishable_from_no_target_negatives():
    rows = _csv_rows(_RISK_ORIGIN_LABELS)
    no_target = [r for r in rows if r["has_eligible_d1_d7_target"] == "False"]
    outside_only = [r for r in rows if r["has_eligible_d1_d7_target"] == "True" and r["risk_target_label"] == "0"]
    assert all(r["outside_domain_target_present"] == "False" for r in no_target)
    assert all(r["outside_domain_target_present"] == "True" for r in outside_only)
    assert no_target and outside_only


def test_fmd06d_17_no_target_appearance_becomes_a_modelling_row():
    rows = _csv_rows(_RISK_ORIGIN_LABELS)
    distance_rows = _csv_rows(_CALIBRATION_DIR / "fmd06_spatial_target_distance_audit.csv")
    assert len(rows) == 3761
    assert len(distance_rows) == 17965  # target-appearance count, a DIFFERENT unit
    assert len(rows) != len(distance_rows)
    ids = [row["forecast_origin_id"] for row in rows]
    assert len(ids) == len(set(ids))  # one row per ORIGIN, never per target appearance


def test_fmd06d_18_radius_is_200km_on_every_row():
    rows = _csv_rows(_RISK_ORIGIN_LABELS)
    assert {row["local_evaluation_radius_km"] for row in rows} == {"200.0"}


def test_fmd06d_19_original_spatial_no_go_remains_preserved_in_freeze_and_manifest():
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    manifest = json.loads(_FMD06_MANIFEST.read_text(encoding="utf-8"))
    assert freeze["spatial_domain_status"] == SPATIAL_DOMAIN_STATUS_NO_GO
    assert freeze["spatial_evaluation_radius_km"] is None
    assert manifest["original_spatial_domain_status"] == SPATIAL_DOMAIN_STATUS_NO_GO
    assert manifest["original_spatial_evaluation_radius_km"] is None


def test_fmd06d_20_amendment_remains_explicitly_post_feasibility():
    manifest = json.loads(_FMD06_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["spatial_protocol_amendment_status"] == SPATIAL_PROTOCOL_AMENDMENT_STATUS
    assert manifest["amended_spatial_selection_rule"] == "MAXIMUM_PREDECLARED_LOCAL_EVALUATION_DOMAIN"
    assert manifest["amended_spatial_evaluation_radius_km"] == 200.0


def test_fmd06d_21_active_window_days_remains_14():
    manifest = json.loads(_FMD06_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["active_window_days"] == 14


def test_fmd06d_22_stdbscan_values_remain_unchanged():
    manifest = json.loads(_FMD06_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["stdbscan_eps_space_km"] == 0.236038
    assert manifest["stdbscan_eps_time_days"] == 13.5
    assert manifest["stdbscan_min_core_supports"] == 4


def test_fmd06d_23_source_set_remains_all_eligible_active_sources_at_t0():
    manifest = json.loads(_FMD06_MANIFEST.read_text(encoding="utf-8"))
    rows = _csv_rows(_RISK_ORIGIN_LABELS)
    assert manifest["spatial_reference_source_set"] == "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0"
    assert {row["spatial_reference_source_set"] for row in rows} == {"ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0"}


def test_fmd06d_24_direction_speed_status_remains_no_go():
    manifest = json.loads(_FMD06_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["direction_speed_status"] == "NO-GO"
    assert DIRECTION_SPEED_STATUS == "NO-GO"
    assert "non-blocking" in manifest["direction_speed_status_reason"].lower() or "NON-BLOCKING" in manifest["direction_speed_status_reason"]


def test_fmd06d_25_weather_window_selection_remains_deferred_to_fmd07():
    manifest = json.loads(_FMD06_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["weather_window_selection_status"] == "DEFERRED_TO_FMD07_DEVELOPMENT_SELECTION"
    assert WEATHER_WINDOW_SELECTION_STATUS == "DEFERRED_TO_FMD07_DEVELOPMENT_SELECTION"


def test_fmd06d_26_no_predictive_model_is_fitted():
    manifest = json.loads(_FMD06_MANIFEST.read_text(encoding="utf-8"))
    freeze = json.loads(_CALIBRATION_FREEZE.read_text(encoding="utf-8"))
    assert manifest["predictive_model_trained"] is False
    assert manifest["held_out_outcomes_used"] is False
    assert manifest["sri_lanka_outcomes_used"] is False
    assert freeze["ml_model_trained"] is False
    for name in ("run_fmd06d", "build_fmd06d_risk_origin_labels", "summarize_fmd06d_risk_origin_labels"):
        from components.geospatial_tracking.services import fmd_calibration as m
        signature = inspect.signature(getattr(m, name))
        assert not {"target", "label", "outcome", "risk", "prediction", "accuracy"} & set(signature.parameters)


def test_fmd06d_27_canonical_fmd_input_unchanged():
    manifest = json.loads(_FMD06_MANIFEST.read_text(encoding="utf-8"))
    canonical = _REPO_ROOT / "local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv"
    fmd_manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert _sha256(canonical) == fmd_manifest["source_canonical_csv_sha256"]
    assert manifest["input_artifact_sha256"]["fmd_canonical_outbreaks_conservative.csv"] == _sha256(canonical)


def test_fmd06d_28_canonical_lsd_input_unchanged():
    lsd = _REPO_ROOT / "local_data/processed/canonical_outbreaks_conservative.csv"
    if lsd.exists():
        assert _sha256(lsd) == "fa8e77d81b48af6bc2839deb4be9d4046d502ab948ce8e4e67a02a84c281d7f7"


def test_fmd06d_29_label_artifact_deterministic_across_rebuilds(tmp_path):
    def _build(out_dir: Path) -> str:
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in _CALIBRATION_DIR.iterdir():
            if name.name not in ("fmd06_risk_origin_labels.csv", "fmd06_calibration_manifest.json"):
                (out_dir / name.name).write_bytes(name.read_bytes())
        run_fmd06d(_ORIGINS, out_dir)
        return hashlib.sha256((out_dir / "fmd06_risk_origin_labels.csv").read_bytes()).hexdigest()

    hash1 = _build(tmp_path / "run1")
    hash2 = _build(tmp_path / "run2")
    assert hash1 == hash2


def test_fmd06d_30_manifest_deterministic_across_rebuilds(tmp_path):
    def _build(out_dir: Path) -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in _CALIBRATION_DIR.iterdir():
            if name.name not in ("fmd06_risk_origin_labels.csv", "fmd06_calibration_manifest.json"):
                (out_dir / name.name).write_bytes(name.read_bytes())
        run_fmd06d(_ORIGINS, out_dir)
        manifest = json.loads((out_dir / "fmd06_calibration_manifest.json").read_text(encoding="utf-8"))
        manifest.pop("artifact_sha256", None)  # depends on freeze.json's own byte-identical reproduction, checked separately
        return manifest

    manifest1 = _build(tmp_path / "run1")
    manifest2 = _build(tmp_path / "run2")
    assert manifest1 == manifest2


def test_fmd06d_31_reconciliation_blocks_on_mismatch(tmp_path):
    # a deliberately corrupted audit row must BLOCK, never silently adjust
    out_dir = tmp_path / "corrupted"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in _CALIBRATION_DIR.iterdir():
        if name.name not in ("fmd06_risk_origin_labels.csv", "fmd06_calibration_manifest.json"):
            (out_dir / name.name).write_bytes(name.read_bytes())
    audit_rows = _csv_rows(out_dir / "fmd06_pa_local_domain_audit.csv")
    # flip one positive row to negative to break the frozen reconciliation
    for row in audit_rows:
        if row["local_domain_positive"] == "True":
            row["local_domain_positive"] = "False"
            row["outside_domain_target_present"] = "True"
            break
    with (out_dir / "fmd06_pa_local_domain_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PA_LOCAL_DOMAIN_AUDIT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(audit_rows)
    with pytest.raises(ValueError, match="BLOCKED"):
        run_fmd06d(_ORIGINS, out_dir)
    assert not (out_dir / "fmd06_risk_origin_labels.csv").exists()  # never written on a blocked reconciliation


def test_fmd06d_32_reproducibility_includes_freeze_json_hash(tmp_path):
    def _build(out_dir: Path) -> str:
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in _CALIBRATION_DIR.iterdir():
            if name.name not in ("fmd06_risk_origin_labels.csv", "fmd06_calibration_manifest.json"):
                (out_dir / name.name).write_bytes(name.read_bytes())
        run_fmd06d(_ORIGINS, out_dir)
        return hashlib.sha256((out_dir / "fmd06_calibration_freeze.json").read_bytes()).hexdigest()

    hash1 = _build(tmp_path / "run1")
    hash2 = _build(tmp_path / "run2")
    assert hash1 == hash2
