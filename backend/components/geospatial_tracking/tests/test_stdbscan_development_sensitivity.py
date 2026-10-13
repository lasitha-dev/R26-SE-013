"""Development sensitivity report (Part 19) — real DB, small synthetic corpus."""

from __future__ import annotations

import pytest

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.stdbscan.config import GpsCorePolicy, STDBSCANConfig, SOFTWARE_FIXTURE_ONLY
from components.geospatial_tracking.services.stdbscan.development_sensitivity import build_config_sensitivity_report


@pytest.fixture
def repo(tmp_path):
    r = SQLiteOutbreakRepository(tmp_path / "test.db")
    r.init_schema()
    yield r
    r.close()


def _historical(**overrides) -> HistoricalOutbreakRecord:
    fields = dict(
        source_record_id="H1",
        country="Thailand",
        disease="Lumpy skin disease",
        outbreak_start_date="2021/06/01",
        proxy_availability_date="2021/06/01",
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        proxy_availability_source_field="outbreak_start_date",
        latitude=15.0,
        longitude=101.0,
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value,
        model_candidate=True,
    )
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


def test_sensitivity_report_aggregates_across_origins(repo):
    repo.add_historical_record(_historical(source_record_id="A1", latitude=15.0, longitude=101.0))
    repo.add_historical_record(_historical(source_record_id="A2", latitude=15.001, longitude=101.0))
    repo.add_historical_record(_historical(source_record_id="B1", latitude=20.0, longitude=105.0, outbreak_start_date="2021/07/01", proxy_availability_date="2021/07/01"))

    origins = [
        ForecastOrigin(forecast_origin_id="O1", country="Thailand", t0="2021-06-01", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["A1"], trigger_source_count=1),
        ForecastOrigin(forecast_origin_id="O2", country="Thailand", t0="2021-07-01", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["B1"], trigger_source_count=1),
    ]
    config = STDBSCANConfig(
        eps_space_km=5.0, eps_time_days=7, min_core_supports=2, active_window_days=14,
        gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value, parameter_status=SOFTWARE_FIXTURE_ONLY,
    )
    report = build_config_sensitivity_report(repo, fit_development_origins=origins, disease="Lumpy skin disease", config=config)
    assert report.n_origins_evaluated == 2
    assert report.n_usable_sources_total > 0
    assert report.gps_quality_composition.get("EXACT", 0) > 0
    assert report.noise_fraction is not None
    assert 0.0 <= report.noise_fraction <= 1.0


def test_sensitivity_report_never_reports_prediction_accuracy_fields():
    from components.geospatial_tracking.services.stdbscan.development_sensitivity import ConfigSensitivityReport

    field_names = {name.lower() for name in ConfigSensitivityReport.__dataclass_fields__}
    for forbidden in ("accuracy", "risk_capture", "direction_error", "speed_error", "risk", "prediction"):
        assert forbidden not in field_names


def _fixture_config():
    return STDBSCANConfig(
        eps_space_km=5.0, eps_time_days=7, min_core_supports=2, active_window_days=14,
        gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value, parameter_status=SOFTWARE_FIXTURE_ONLY,
    )


def test_firewall_01_rejects_held_out_origin(repo):
    held_out = ForecastOrigin(
        forecast_origin_id="ORIGIN:Thailand:2024-06-01", country="Thailand", t0="2024-06-01",
        temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1,
    )
    with pytest.raises(ValueError, match="HELD_OUT_FROM_MODEL_FITTING"):
        build_config_sensitivity_report(repo, fit_development_origins=[held_out], disease="Lumpy skin disease", config=_fixture_config())


def test_firewall_02_rejects_sri_lanka_origin(repo):
    sri_lanka = ForecastOrigin(
        forecast_origin_id="ORIGIN:Sri Lanka:2020-06-01", country="Sri Lanka", t0="2020-06-01",
        temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1,
    )
    with pytest.raises(ValueError, match="SRI_LANKA_TRANSFER_CASE_STUDY"):
        build_config_sensitivity_report(repo, fit_development_origins=[sri_lanka], disease="Lumpy skin disease", config=_fixture_config())


def test_firewall_03_mixed_list_rejected_entirely(repo):
    good = ForecastOrigin(
        forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01",
        temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1,
    )
    held_out = ForecastOrigin(
        forecast_origin_id="ORIGIN:Thailand:2024-06-01", country="Thailand", t0="2024-06-01",
        temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1,
    )
    with pytest.raises(ValueError):
        build_config_sensitivity_report(repo, fit_development_origins=[good, held_out], disease="Lumpy skin disease", config=_fixture_config())


def test_firewall_04_pure_fit_development_list_works(repo):
    repo.add_historical_record(_historical(source_record_id="A1", latitude=15.0, longitude=101.0))
    good = ForecastOrigin(
        forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01",
        temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["A1"], trigger_source_count=1,
    )
    report = build_config_sensitivity_report(repo, fit_development_origins=[good], disease="Lumpy skin disease", config=_fixture_config())
    assert report.n_origins_evaluated == 1


def test_thailand_scope_label_is_explicit(repo):
    repo.add_historical_record(_historical(source_record_id="A1", latitude=15.0, longitude=101.0))
    good = ForecastOrigin(
        forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01",
        temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["A1"], trigger_source_count=1,
    )
    report = build_config_sensitivity_report(
        repo, fit_development_origins=[good], disease="Lumpy skin disease", config=_fixture_config(),
        scope_label="THAILAND_DEVELOPMENT_SENSITIVITY",
    )
    assert report.scope_label == "THAILAND_DEVELOPMENT_SENSITIVITY"
    assert report.as_dict()["scope_label"] == "THAILAND_DEVELOPMENT_SENSITIVITY"
