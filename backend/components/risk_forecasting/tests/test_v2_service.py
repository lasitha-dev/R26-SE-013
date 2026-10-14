"""Tests for v2 prediction, coverage-aware surveillance, the v2 service, scoring and the monthly job.
No network or real database: public data and Mongo collections are faked.
Deliberately does NOT import routes/core.database (endpoint tests live in test_v2_endpoints.py)."""

import json
import re
from datetime import datetime, timezone

import pytest
from bson import ObjectId

from components.risk_forecasting.pipeline.features import ALL_FEATURES, FeatureSources
from components.risk_forecasting.pipeline.geography import DISTRICT_NAMES, DISTRICTS
from components.risk_forecasting.pipeline.predictor import V2Predictor, risk_tier
from components.risk_forecasting.pipeline.surveillance import (
    SurveillanceProvider, app_month_observations, observed_severity,
)
from components.risk_forecasting.repositories.forecast_record_repository import InMemoryForecastRecordRepository
from components.risk_forecasting.schemas import ForecastDecisionRecord
from components.risk_forecasting.services.forecast_v2_service import (
    ForecastV2Service, StalePreview, SupersedeConfirmationRequired,
)


# ─── fakes ─────────────────────────────────────────────────────────────────

def _match(doc, query):
    for key, cond in query.items():
        if key == "$or":
            if not any(_match(doc, sub) for sub in cond):
                return False
            continue
        value = doc.get(key)
        if isinstance(cond, dict):
            if "$regex" in cond:
                flags = re.IGNORECASE if "i" in cond.get("$options", "") else 0
                if not isinstance(value, str) or not re.search(cond["$regex"], value, flags):
                    return False
            if "$gte" in cond:
                if value is None or type(value) is not type(cond["$gte"]) or not (cond["$gte"] <= value < cond["$lt"]):
                    return False
        elif value != cond:
            return False
    return True


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, query=None, projection=None):
        return [d for d in self.docs if _match(d, query or {})]

    def find_one(self, query, projection=None):
        found = self.find(query)
        return found[0] if found else None


class FakeDb(dict):
    def __getitem__(self, name):
        return self.get(name, FakeCollection([]))


FARM_A = ObjectId()
FARM_B = ObjectId()
CATTLE = ObjectId()


def fake_app_db():
    return FakeDb({
        "farms": FakeCollection([
            {"_id": FARM_A, "location_district": "8.4162, 80.0261 (Anuradhapura District)", "email": "a@farm.lk"},
            {"_id": FARM_B, "location_district": "Colombo District", "email": "b@farm.lk"},
        ]),
        "cattle": FakeCollection([{"_id": CATTLE, "owner_email": "a@farm.lk"}]),
        "diagnostic_cases": FakeCollection([
            {"verified": True, "disease_name": "Foot-and-Mouth Disease", "cattle_id": str(CATTLE),
             "created_at": datetime(2026, 9, 10)},
            {"verified": False, "disease_name": "FMD", "farm_id": str(FARM_B), "created_at": datetime(2026, 9, 11)},
            {"verified": True, "disease_name": "Lumpy Skin Disease", "farm_id": str(FARM_B),
             "created_at": datetime(2026, 9, 12)},
            {"verified": True, "disease_name": "FMD", "farm_id": str(FARM_A), "created_at": datetime(2026, 8, 30)},
        ]),
        "death_logs": FakeCollection([
            {"cause": "FMD", "district": "Anuradhapura District", "date_of_death": datetime(2026, 9, 20)},
        ]),
    })


# ─── predictor ─────────────────────────────────────────────────────────────

def test_risk_tiers_use_relative_risk_and_absolute_ceiling():
    assert risk_tier(0.05, 1.0) == "LOW"
    assert risk_tier(0.10, 2.0) == "MEDIUM"
    assert risk_tier(0.10, 4.0) == "HIGH"
    assert risk_tier(0.55, 1.1) == "HIGH"


def _complete_features():
    return {name: 0.5 for name in ALL_FEATURES}


@pytest.mark.parametrize("disease", ["FMD", "LSD"])
def test_deployed_forecasters_and_fallbacks(disease):
    predictor = V2Predictor.load(disease)
    deployment = predictor.artifact["deployment"]
    known = predictor.predict("Anuradhapura", 1, _complete_features())
    assert known.forecaster == deployment["surveillance_known"]["forecaster"]
    assert 0 < known.probability < 1 and known.relative_risk > 0

    no_surveillance = {**_complete_features(), "own_t1": None}
    unknown = predictor.predict("Anuradhapura", 1, no_surveillance)
    assert unknown.forecaster == deployment["surveillance_unknown"]["forecaster"]
    if unknown.forecaster == "climatology":
        assert unknown.probability == pytest.approx(predictor.baseline("Anuradhapura", 1))
        assert unknown.relative_risk == pytest.approx(1.0)


def test_deployment_decisions_follow_the_current_evidence():
    """Pins the decisions produced by the leave-one-year-out evaluation (docs/v2/MODEL_CARD.md).
    Re-training may legitimately change these; update the model card together with this test."""
    fmd = V2Predictor.load("FMD").artifact["deployment"]
    assert fmd["surveillance_known"] == {"forecaster": "climatology", "C": None, "status": "baseline"}
    assert fmd["own_known"]["forecaster"] == "O" and fmd["own_known"]["status"] == "back_tested"
    assert fmd["surveillance_unknown"]["forecaster"] == "climatology"
    lsd = V2Predictor.load("LSD").artifact["deployment"]
    assert lsd["surveillance_known"]["forecaster"] == "A" and lsd["surveillance_known"]["status"] == "back_tested"
    assert lsd["surveillance_unknown"]["forecaster"] == "climatology"
    assert lsd["own_known"]["forecaster"] == "climatology"  # O/OC did not clear the rule for LSD


def test_district_known_but_neighbours_unknown_uses_the_own_district_model_for_fmd():
    predictor = V2Predictor.load("FMD")
    own_only = {**_complete_features(), "neighbour_fraction_t1": None, "neighbour_count_t1": None,
                "neighbour_fraction_t2": None}
    prediction = predictor.predict("Anuradhapura", 1, own_only)
    assert prediction.forecaster == "O" and prediction.deployment_status == "back_tested"
    assert {c["feature"] for c in prediction.contributions} <= {"own_t1", "own_t2", "climatology_logit"}
    # Own district unknown too -> baseline, never a guess.
    nothing = predictor.predict("Anuradhapura", 1, {**own_only, "own_t1": None})
    assert nothing.forecaster == "climatology"
    # Full surveillance still takes precedence over the own-district tier.
    assert predictor.predict("Anuradhapura", 1, _complete_features()).forecaster == predictor.artifact["deployment"]["surveillance_known"]["forecaster"]


def test_missing_climate_input_falls_back_to_climatology_for_climate_model():
    predictor = V2Predictor.load("LSD")  # deployed known-surveillance forecaster uses climate features
    assert predictor.artifact["deployment"]["surveillance_known"]["forecaster"] == "A"
    features = {**_complete_features(), "rain_t1": None}
    assert predictor.predict("Kandy", 3, features).forecaster == "climatology"


# ─── surveillance ──────────────────────────────────────────────────────────

def test_app_observations_are_coverage_aware():
    obs = app_month_observations(fake_app_db(), "FMD", 2026, 9)
    anuradhapura = obs["Anuradhapura"]
    assert anuradhapura.status == "CONFIRMED_OUTBREAK"
    assert anuradhapura.cases == 1 and anuradhapura.deaths == 1  # case resolved via cattle -> owner farm
    assert obs["Colombo"].status == "NO_REPORTED_CASES"            # covered; unverified case ignored
    assert obs["Colombo"].outbreak == 0
    assert obs["Jaffna"].status == "NO_SURVEILLANCE_COVERAGE"       # no farms
    assert obs["Jaffna"].outbreak is None
    # Where the app has no coverage, counts and severity are unknown, not zero.
    assert obs["Jaffna"].cases is None and obs["Jaffna"].deaths is None
    assert obs["Jaffna"].as_dict()["observed_severity"] is None
    assert obs["Colombo"].cases == 0 and obs["Colombo"].as_dict()["observed_severity"] == "NONE"
    lsd = app_month_observations(fake_app_db(), "LSD", 2026, 9)
    assert lsd["Colombo"].status == "CONFIRMED_OUTBREAK"


def test_observed_severity_bands():
    assert observed_severity(0, 0) == "NONE"
    assert observed_severity(3, 0) == "LOW"
    assert observed_severity(5, 1) == "MODERATE"
    assert observed_severity(10, 2) == "HIGH"
    assert observed_severity(None, 0) is None


def test_surveillance_provider_sources_and_unknowns():
    labels = {("Jaffna", 2023, 5): 1, ("Kandy", 2023, 5): 0}
    provider = SurveillanceProvider("FMD", labels, fake_app_db)
    assert provider.status("Jaffna", 2023, 5) == 1
    assert provider.status("Kandy", 2023, 5) == 0
    assert provider.status("Jaffna", 2024, 12) is None  # FMD 2024 labels unverified
    assert provider.month(2024, 12)["Jaffna"].status == "UNVERIFIED_LABEL"
    assert provider.status("Anuradhapura", 2026, 9) == 1  # app records

    def broken():
        raise ConnectionError("Atlas unreachable")

    failing = SurveillanceProvider("FMD", {}, broken)
    assert failing.status("Anuradhapura", 2026, 9) is None
    assert failing.month(2026, 9)["Anuradhapura"].status == "SOURCE_UNAVAILABLE"


# ─── service ───────────────────────────────────────────────────────────────

def fake_sources_builder(targets, surveillance):
    (year, month), = targets
    prev = (year, month - 1) if month > 1 else (year - 1, 12)
    prev2 = (prev[0], prev[1] - 1) if prev[1] > 1 else (prev[0] - 1, 12)
    rain, weather = {}, {}
    for district, info in DISTRICTS.items():
        for p in (prev, prev2):
            rain[(info["pcode"], *p)] = {"rainfall_mm": 150.0, "r3h": 450.0, "rfq": 100.0}
        weather[(district, *prev)] = {"T2M": 27.0, "RH2M": 80.0, "WS2M": 3.0}
    nino = {(y, m): 0.2 for y in range(2015, 2031) for m in range(1, 13)}
    density = {d: [(2024, 3.0, 12.0)] for d in DISTRICTS}
    sources = FeatureSources(rain=rain, weather=weather, nino_anomaly=nino, density=density,
                             surveillance=surveillance.status)
    return sources, {"rainfall": "fake", "weather": "fake", "enso": "fake"}


def no_dependents(_forecast_id):
    return {"advisories": 0, "follow_ups": 0}


def make_service(repo, dependency_counter=no_dependents, clock=None):
    counter = iter(range(10_000))
    return ForecastV2Service(repository_getter=lambda: repo, app_db_factory=fake_app_db,
                             sources_builder=fake_sources_builder, clock=clock,
                             id_generator=lambda: f"fdr_test{next(counter):05d}",
                             dependency_counter=dependency_counter)


def old_record(fid, status="GENERATED", district="Kandy", disease="FMD", year=2026, month=10):
    return ForecastDecisionRecord(
        forecast_id=fid, disease=disease, district=district, target_year=year, target_month=month,
        generated_at="2026-08-01T00:00:00+00:00", probability=0.4, probability_pct=40.0, risk_level="MEDIUM",
        model_variant="30_feature_baseline", fallback_applied=True, data_quality="HISTORICAL_SAME_MONTH_PROXY",
        status=status, disclaimer="v1", created_at="2026-08-01T00:00:00+00:00", updated_at="2026-08-01T00:00:00+00:00")


def test_forecast_period_builds_one_record_per_district_with_provenance():
    service = make_service(InMemoryForecastRecordRepository())
    records = service.forecast_period(2026, 10)
    assert len(records) == 2 * len(DISTRICT_NAMES)
    by_key = {(r.disease, r.district): r for r in records}
    # Anuradhapura FMD: the district's own last two months are known from the app, but its
    # neighbours lack coverage -> the own-district model (not the full surveillance model).
    r = by_key[("FMD", "Anuradhapura")]
    assert r.surveillance_status == "CONFIRMED_OUTBREAK"
    assert r.previous_month_observation["verified_cases"] == 1
    assert r.forecaster == "O" and r.deployment_status == "back_tested"
    assert r.feature_snapshot["neighbour_fraction_t1"] is None
    # Every other district has no app coverage at all -> climatology baseline.
    assert by_key[("FMD", "Jaffna")].forecaster == "climatology"
    assert r.idempotency_key == "v2|FMD|Anuradhapura|2026-10|fmd_v2.0"
    assert r.input_quality == "COMPLETE"
    assert r.predicted_severity is None


def test_record_carries_the_real_issue_date_and_data_cutoff():
    clock = lambda: datetime(2026, 10, 17, 9, 30, tzinfo=timezone.utc)  # noqa: E731
    records = make_service(InMemoryForecastRecordRepository(), clock=clock).forecast_period(2026, 10, ["FMD"])
    assert {r.issue_date for r in records} == {"2026-10-17"}  # not the nominal day 5
    assert {r.data_cutoff for r in records} == {"2026-09-30"}
    assert {r.retrospective for r in records} == {False}
    assert {r.trigger_type for r in records} == {"MANUAL"}


def test_cutoff_crosses_year_and_leap_boundaries():
    clock = lambda: datetime(2024, 3, 6, tzinfo=timezone.utc)  # noqa: E731
    svc = make_service(InMemoryForecastRecordRepository(), clock=clock)
    assert svc.forecast_period(2024, 3, ["LSD"])[0].data_cutoff == "2024-02-29"
    clock_jan = lambda: datetime(2025, 1, 6, tzinfo=timezone.utc)  # noqa: E731
    svc = make_service(InMemoryForecastRecordRepository(), clock=clock_jan)
    assert svc.forecast_period(2025, 1, ["LSD"])[0].data_cutoff == "2024-12-31"


def test_late_runs_are_labelled_backfill_and_retrospective():
    clock = lambda: datetime(2026, 10, 13, tzinfo=timezone.utc)  # noqa: E731
    repo = InMemoryForecastRecordRepository()
    service = make_service(repo, clock=clock)
    late = service.forecast_period(2026, 9, ["FMD"], trigger_type="SCHEDULED")
    assert {r.trigger_type for r in late} == {"BACKFILL"}  # overrides the requested trigger
    assert {r.retrospective for r in late} == {True}
    assert {r.issue_date for r in late} == {"2026-10-13"}
    # A run during the target month, or in advance of it, is not retrospective.
    assert {r.retrospective for r in service.forecast_period(2026, 10, ["FMD"])} == {False}
    assert {r.retrospective for r in service.forecast_period(2026, 11, ["FMD"])} == {False}


def test_performance_separates_retrospective_from_prospective_scores():
    clock_prospective = lambda: datetime(2026, 9, 10, tzinfo=timezone.utc)  # noqa: E731
    repo = InMemoryForecastRecordRepository()
    make_service(repo, clock=clock_prospective).generate_period(2026, 9, ["FMD"])
    fmd = make_service(repo).performance(as_of=datetime(2026, 11, 13))["diseases"]["FMD"]
    assert fmd["scored"] > 0 and fmd["retrospective_scored"] == 0
    backfill_repo = InMemoryForecastRecordRepository()
    make_service(backfill_repo, clock=lambda: datetime(2026, 10, 13, tzinfo=timezone.utc)).generate_period(2026, 9, ["FMD"])
    fmd = make_service(backfill_repo).performance(as_of=datetime(2026, 11, 13))["diseases"]["FMD"]
    assert fmd["retrospective_scored"] == fmd["scored"] > 0


def test_lsd_january_2025_uses_surveillance_model_from_curated_labels():
    records = make_service(InMemoryForecastRecordRepository()).forecast_period(2025, 1, ["LSD"])
    deployed = V2Predictor.load("LSD").artifact["deployment"]["surveillance_known"]["forecaster"]
    assert {r.forecaster for r in records} == {deployed}
    assert all(r.surveillance_source == "CURATED_DAPH_DATASET" for r in records)
    fmd = make_service(InMemoryForecastRecordRepository()).forecast_period(2025, 1, ["FMD"])
    assert {r.forecaster for r in fmd} == {"climatology"}  # December 2024 FMD labels unverified


def test_real_run_requires_confirmation_before_superseding():
    repo = InMemoryForecastRecordRepository()
    repo.save(old_record("fdr_v1_old"))
    service = make_service(repo)

    preview = service.generate_period(2026, 10, ["FMD"], dry_run=True)["summary"]
    assert preview["status"] == "PREVIEW" and preview["would_supersede"] == 1 and preview["protected"] == 0
    assert repo.list(limit=200)[1] == 1  # nothing written by the preview

    try:
        service.generate_period(2026, 10, ["FMD"])
        raise AssertionError("expected SupersedeConfirmationRequired")
    except SupersedeConfirmationRequired as exc:
        assert exc.would_supersede == 1
    assert repo.list(limit=200)[1] == 1  # still nothing written

    try:
        service.generate_period(2026, 10, ["FMD"], expected_supersede_count=3)
        raise AssertionError("expected StalePreview")
    except StalePreview as exc:
        assert (exc.expected, exc.actual) == (3, 1)
    assert repo.list(limit=200)[1] == 1 and repo.get_by_id("fdr_v1_old").status == "GENERATED"


def test_confirmed_run_is_idempotent_and_supersedes_only_unused_records():
    repo = InMemoryForecastRecordRepository()
    repo.save(old_record("fdr_v1_old"))
    service = make_service(repo)

    first = service.generate_period(2026, 10, ["FMD"], expected_supersede_count=1)["summary"]
    assert first["status"] == "OK" and first["saved"] == 25 and first["superseded"] == 1
    assert repo.get_by_id("fdr_v1_old").status == "SUPERSEDED"

    second = service.generate_period(2026, 10, ["FMD"])["summary"]  # nothing left to supersede: no confirmation needed
    assert second["superseded"] == 0 and second["reused"] == 25
    assert repo.list(disease="FMD", target_year=2026, target_month=10, limit=200)[1] == 26  # no duplicates


def test_records_with_advisories_follow_ups_or_workflow_status_are_never_superseded():
    repo = InMemoryForecastRecordRepository()
    for fid, status in [("fdr_adv", "GENERATED"), ("fdr_fu", "GENERATED"), ("fdr_used", "AVAILABLE"), ("fdr_free", "GENERATED")]:
        repo.save(old_record(fid, status))
    dependents = {"fdr_adv": {"advisories": 1, "follow_ups": 0}, "fdr_fu": {"advisories": 0, "follow_ups": 2},
                  "fdr_used": {"advisories": 0, "follow_ups": 0}, "fdr_free": {"advisories": 0, "follow_ups": 0}}
    service = make_service(repo, dependency_counter=lambda fid: dependents[fid])

    preview = service.generate_period(2026, 10, ["FMD"], dry_run=True)["summary"]
    assert preview["would_supersede"] == 1 and preview["protected"] == 3
    assert preview["protected_reasons"] == {"HAS_ADVISORY": 1, "HAS_FOLLOW_UP": 1, "WORKFLOW_STATUS": 1}

    service.generate_period(2026, 10, ["FMD"], expected_supersede_count=1)
    assert {fid: repo.get_by_id(fid).status for fid in dependents} == {
        "fdr_adv": "GENERATED", "fdr_fu": "GENERATED", "fdr_used": "AVAILABLE", "fdr_free": "SUPERSEDED"}


def test_without_a_dependency_check_nothing_is_superseded():
    repo = InMemoryForecastRecordRepository()
    repo.save(old_record("fdr_v1_old"))
    service = make_service(repo, dependency_counter=None)
    summary = service.generate_period(2026, 10, ["FMD"])["summary"]  # no confirmation needed: nothing to supersede
    assert summary["would_supersede"] == 0 and summary["protected_reasons"] == {"DEPENDENCY_CHECK_UNAVAILABLE": 1}
    assert repo.get_by_id("fdr_v1_old").status == "GENERATED"

    def failing(_fid):
        raise RuntimeError("database down")

    failing_service = make_service(InMemoryForecastRecordRepository(), dependency_counter=failing)
    failing_service.repository_getter().save(old_record("fdr_other"))
    assert failing_service.generate_period(2026, 10, ["FMD"], dry_run=True)["summary"]["protected"] == 1


def test_supersede_can_be_disabled_entirely():
    repo = InMemoryForecastRecordRepository()
    repo.save(old_record("fdr_v1_old"))
    summary = make_service(repo).generate_period(2026, 10, ["FMD"], supersede=False)["summary"]
    assert summary["saved"] == 25 and summary["superseded"] == 0
    assert repo.get_by_id("fdr_v1_old").status == "GENERATED"


def test_all_existing_records_are_considered_beyond_a_single_page():
    repo = InMemoryForecastRecordRepository()
    for i in range(230):  # more than the 200-record page size
        repo.save(old_record(f"fdr_bulk_{i:03d}", district="Kandy"))
    preview = make_service(repo).generate_period(2026, 10, ["FMD"], dry_run=True)["summary"]
    assert preview["would_supersede"] == 230


class FlakyRepo(InMemoryForecastRecordRepository):
    """Fails the Nth save, and optionally fails status updates."""

    def __init__(self, fail_save_at=None, fail_updates=False):
        super().__init__()
        self.fail_save_at, self.fail_updates, self.saves = fail_save_at, fail_updates, 0

    def save(self, record):
        self.saves += 1
        if self.fail_save_at and self.saves == self.fail_save_at:
            raise RuntimeError("Forecast record storage is temporarily unavailable.")
        return super().save(record)

    def update_status(self, forecast_id, new_status):
        if self.fail_updates:
            raise RuntimeError("Forecast record storage is temporarily unavailable.")
        return super().update_status(forecast_id, new_status)


def test_partial_save_failure_supersedes_nothing_and_a_rerun_completes():
    repo = FlakyRepo(fail_save_at=10)
    repo.fail_save_at = 10
    InMemoryForecastRecordRepository.save(repo, old_record("fdr_v1_old"))
    service = make_service(repo)

    first = service.generate_period(2026, 10, ["FMD"], expected_supersede_count=1)["summary"]
    assert first["status"] == "PARTIAL" and first["saved"] == 24 and len(first["failed"]) == 1
    assert first["superseded"] == 0 and repo.get_by_id("fdr_v1_old").status == "GENERATED"

    repo.fail_save_at = None
    second = service.generate_period(2026, 10, ["FMD"], expected_supersede_count=1)["summary"]
    assert second["status"] == "OK" and second["saved"] == 25 and second["superseded"] == 1
    assert repo.list(disease="FMD", target_year=2026, target_month=10, limit=200)[1] == 26


def test_storage_down_from_the_first_write_raises_and_writes_nothing():
    repo = FlakyRepo(fail_save_at=1)
    try:
        make_service(repo).generate_period(2026, 10, ["FMD"])
        raise AssertionError("expected RuntimeError")
    except RuntimeError:
        pass
    assert repo.list(limit=200)[1] == 0


def test_supersede_update_failure_is_reported_as_partial():
    repo = FlakyRepo(fail_updates=True)
    InMemoryForecastRecordRepository.save(repo, old_record("fdr_v1_old"))
    summary = make_service(repo).generate_period(2026, 10, ["FMD"], expected_supersede_count=1)["summary"]
    assert summary["status"] == "PARTIAL" and summary["saved"] == 25 and summary["superseded"] == 0
    assert summary["supersede_failed"] == [{"forecast_id": "fdr_v1_old", "error": "RuntimeError"}]


def test_dry_run_does_not_persist():
    repo = InMemoryForecastRecordRepository()
    result = make_service(repo).generate_period(2026, 10, ["LSD"], dry_run=True)
    assert result["summary"]["dry_run"] is True
    assert repo.list(limit=200)[1] == 0


# ─── monitoring and monthly job ────────────────────────────────────────────

def test_performance_scores_only_known_outcomes():
    repo = InMemoryForecastRecordRepository()
    service = make_service(repo)
    service.generate_period(2023, 5, ["FMD"])  # outcome comes from curated 2023 labels
    service.generate_period(2026, 9, ["FMD"])  # outcome from app records (fake db)
    report = service.performance(as_of=datetime(2026, 11, 13))
    fmd = report["diseases"]["FMD"]
    assert report["scored_through"] == "2026-09"
    # 25 curated outcomes + Anuradhapura (confirmed) and Colombo (covered, no cases) from the app
    assert fmd["scored"] == 27
    assert fmd["unscored_by_status"] == {"NO_SURVEILLANCE_COVERAGE": 23}
    assert fmd["hits"] + fmd["missed_outbreaks"] == fmd["outbreaks"]
    assert fmd["brier_score"] is not None


def test_performance_skips_months_inside_grace_period():
    service = make_service(InMemoryForecastRecordRepository())
    service.generate_period(2026, 10, ["LSD"])
    assert service.performance(as_of=datetime(2026, 11, 13))["diseases"] == {}


def test_monthly_job_runs_and_logs(tmp_path, monkeypatch, capsys):
    from components.risk_forecasting.jobs import run_monthly_forecast as job
    monkeypatch.setattr(job, "RUN_LOG", tmp_path / "runs.jsonl")
    code = job.main(["--year", "2026", "--month", "10", "--diseases", "LSD", "--dry-run"],
                    service=make_service(InMemoryForecastRecordRepository()))
    assert code == 0
    entry = json.loads((tmp_path / "runs.jsonl").read_text().strip())
    assert entry["status"] == "preview" and entry["summary"]["records"] == 25 and entry["dry_run"] is True


def test_monthly_job_reports_storage_failure(tmp_path, monkeypatch):
    from components.risk_forecasting.jobs import run_monthly_forecast as job
    monkeypatch.setattr(job, "RUN_LOG", tmp_path / "runs.jsonl")

    class BrokenRepo(InMemoryForecastRecordRepository):
        def save(self, record):
            raise RuntimeError("Forecast record storage is temporarily unavailable.")

    assert job.main(["--year", "2026", "--month", "10", "--diseases", "FMD"],
                    service=make_service(BrokenRepo())) == 1


def test_monthly_job_supersede_requires_the_previewed_count(tmp_path, monkeypatch):
    from components.risk_forecasting.jobs import run_monthly_forecast as job
    monkeypatch.setattr(job, "RUN_LOG", tmp_path / "runs.jsonl")
    repo = InMemoryForecastRecordRepository()
    repo.save(old_record("fdr_v1_old"))

    service = make_service(repo)  # one instance: the fake id counter must not restart between runs
    args = ["--year", "2026", "--month", "10", "--diseases", "FMD"]
    assert job.main(args + ["--supersede-count", "5"], service=service) == 3  # stale count
    assert repo.list(limit=200)[1] == 1 and repo.get_by_id("fdr_v1_old").status == "GENERATED"

    assert job.main(args, service=service) == 0  # default: stores, never supersedes
    assert repo.get_by_id("fdr_v1_old").status == "GENERATED"
    assert job.main(args + ["--supersede-count", "1"], service=service) == 0
    assert repo.get_by_id("fdr_v1_old").status == "SUPERSEDED"


def test_monthly_job_exit_code_for_partial_failure(tmp_path, monkeypatch):
    from components.risk_forecasting.jobs import run_monthly_forecast as job
    monkeypatch.setattr(job, "RUN_LOG", tmp_path / "runs.jsonl")
    assert job.main(["--year", "2026", "--month", "10", "--diseases", "FMD"],
                    service=make_service(FlakyRepo(fail_save_at=7))) == 4
