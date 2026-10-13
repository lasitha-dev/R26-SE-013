"""Checkpoint 6B.5 Parts 13-15: international development sensitivity —
SENS-01..04."""

from __future__ import annotations

import pytest

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.stdbscan.config import GpsCorePolicy, STDBSCANConfig, SOFTWARE_FIXTURE_ONLY
from components.geospatial_tracking.services.stdbscan.international_sensitivity import (
    CountrySensitivitySlice,
    InternationalDevelopmentSensitivityReport,
    build_international_development_sensitivity_report,
)

DISEASE = "Lumpy skin disease"


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
        disease=DISEASE,
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


def _origin(**overrides) -> ForecastOrigin:
    fields = dict(
        forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01",
        temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["H1"], trigger_source_count=1,
    )
    fields.update(overrides)
    return ForecastOrigin(**fields)


def _tight_config():
    return STDBSCANConfig(
        eps_space_km=5.0, eps_time_days=7, min_core_supports=2, active_window_days=14,
        gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value, parameter_status=SOFTWARE_FIXTURE_ONLY,
    )


def test_sens_01_international_includes_more_than_thailand(repo):
    repo.add_historical_record(_historical(source_record_id="TH1", country="Thailand", latitude=15.0, longitude=101.0))
    repo.add_historical_record(_historical(source_record_id="VN1", country="Vietnam", latitude=16.0, longitude=106.0, outbreak_start_date="2021/07/01", proxy_availability_date="2021/07/01"))

    origins = [
        _origin(forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01", trigger_source_ids_at_t0=["TH1"]),
        _origin(forecast_origin_id="ORIGIN:Vietnam:2021-07-01", country="Vietnam", t0="2021-07-01", trigger_source_ids_at_t0=["VN1"]),
    ]
    report = build_international_development_sensitivity_report(
        repo, fit_development_origins=origins, disease=DISEASE, config=_tight_config()
    )
    countries = {slice_["country"] for slice_ in report.macro_country_summary}
    assert countries == {"Thailand", "Vietnam"}
    assert report.n_countries == 2
    assert report.scope_label == "INTERNATIONAL_DEVELOPMENT_SENSITIVITY"


def test_sens_02_country_specific_report_is_explicitly_labeled():
    from components.geospatial_tracking.services.stdbscan.development_sensitivity import DEFAULT_SCOPE_LABEL

    assert DEFAULT_SCOPE_LABEL != "INTERNATIONAL_DEVELOPMENT_SENSITIVITY"
    assert "COUNTRY_SPECIFIC" in DEFAULT_SCOPE_LABEL or "THAILAND" not in DEFAULT_SCOPE_LABEL


def test_sens_03_no_target_outcome_performance_field():
    forbidden = {"accuracy", "risk_capture", "direction_error", "speed_error", "risk", "prediction", "target", "outcome"}
    for cls in (InternationalDevelopmentSensitivityReport, CountrySensitivitySlice):
        field_names = {name.lower() for name in cls.__dataclass_fields__}
        assert not (field_names & forbidden), f"{cls.__name__} leaked a forbidden field: {field_names & forbidden}"


def test_sens_04_100_percent_noise_configuration_retained(repo):
    repo.add_historical_record(_historical(source_record_id="TH1", country="Thailand", latitude=15.0, longitude=101.0))
    repo.add_historical_record(_historical(source_record_id="TH2", country="Thailand", latitude=25.0, longitude=110.0, outbreak_start_date="2021/09/01", proxy_availability_date="2021/09/01"))
    origins = [_origin(trigger_source_ids_at_t0=["TH1", "TH2"])]
    tiny_config = STDBSCANConfig(
        eps_space_km=0.001, eps_time_days=0, min_core_supports=2, active_window_days=14,
        gps_core_policy=GpsCorePolicy.PRIMARY_CORE_SUPPORT.value, parameter_status=SOFTWARE_FIXTURE_ONLY,
    )
    report = build_international_development_sensitivity_report(
        repo, fit_development_origins=origins, disease=DISEASE, config=tiny_config
    )
    assert report.micro_summary["n_clusters_total"] == 0
    assert report.micro_summary["noise_fraction"] == 1.0


def test_international_firewall_rejects_held_out(repo):
    held_out = ForecastOrigin(
        forecast_origin_id="ORIGIN:Thailand:2024-06-01", country="Thailand", t0="2024-06-01",
        temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1,
    )
    with pytest.raises(ValueError, match="HELD_OUT_FROM_MODEL_FITTING"):
        build_international_development_sensitivity_report(
            repo, fit_development_origins=[held_out], disease=DISEASE, config=_tight_config()
        )
