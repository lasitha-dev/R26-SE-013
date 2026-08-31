import pytest

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord, PredictionRun
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, ValidationMode


def _record(**overrides):
    fields = dict(source_record_id="H1")
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


class TestEffectiveAvailability:
    def test_strict_operational_returns_none_when_only_proxy_documented(self):
        record = _record(
            proxy_availability_date="2026/01/05",
            proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        )
        date, quality = record.effective_availability(ValidationMode.STRICT_OPERATIONAL)
        assert date is None
        assert quality == AvailabilityQuality.UNKNOWN.value

    def test_strict_operational_returns_actual_when_evidence_exists(self):
        record = _record(
            operational_availability_date="2026/01/05",
            operational_availability_quality=AvailabilityQuality.ACTUAL.value,
        )
        date, quality = record.effective_availability(ValidationMode.STRICT_OPERATIONAL)
        assert date == "2026/01/05"
        assert quality == AvailabilityQuality.ACTUAL.value

    def test_retrospective_proxy_returns_documented_proxy(self):
        record = _record(
            proxy_availability_date="2026/01/05",
            proxy_availability_quality=AvailabilityQuality.OBSERVATION_DATE_PROXY.value,
        )
        date, quality = record.effective_availability(ValidationMode.RETROSPECTIVE_PROXY)
        assert date == "2026/01/05"
        assert quality == AvailabilityQuality.OBSERVATION_DATE_PROXY.value

    def test_retrospective_proxy_returns_none_when_proxy_undocumented(self):
        record = _record(proxy_availability_date=None, proxy_availability_quality=AvailabilityQuality.UNKNOWN.value)
        date, quality = record.effective_availability(ValidationMode.RETROSPECTIVE_PROXY)
        assert date is None
        assert quality == AvailabilityQuality.UNKNOWN.value

    def test_current_corpus_default_is_unknown_under_strict_operational(self):
        # every record in the current corpus has no real operational
        # evidence — the default-constructed record must reflect that.
        record = _record()
        date, quality = record.effective_availability(ValidationMode.STRICT_OPERATIONAL)
        assert date is None
        assert quality == AvailabilityQuality.UNKNOWN.value


class TestActualGuard:
    def test_operational_actual_requires_a_date(self):
        with pytest.raises(ValueError, match="ACTUAL requires"):
            _record(
                operational_availability_quality=AvailabilityQuality.ACTUAL.value,
                operational_availability_date=None,
            )

    def test_proxy_can_never_be_actual(self):
        with pytest.raises(ValueError, match="never be ACTUAL"):
            _record(
                proxy_availability_quality=AvailabilityQuality.ACTUAL.value,
                proxy_availability_date="2026/01/05",
            )


class TestPredictionRunAudit:
    def test_pred_01_stores_t0_and_source_ids_without_fake_model_metrics(self, tmp_path):
        repo = SQLiteOutbreakRepository(tmp_path / "test.db")
        repo.init_schema()
        run = PredictionRun(
            prediction_id="PR-1",
            forecast_origin_t0="2026-01-10",
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY.value,
            primary_source_id="H1",
            active_source_ids=["H1", "H2", "H3"],
            model_version=None,  # no model exists yet — must be allowed
            config_hash=None,
        )
        repo.add_prediction_run(run)
        fetched = repo.get_prediction_run("PR-1")
        assert fetched.forecast_origin_t0 == "2026-01-10"
        assert fetched.active_source_ids == ["H1", "H2", "H3"]
        assert fetched.model_version is None
        assert fetched.config_hash is None
        repo.close()
