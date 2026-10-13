"""Tests for v2 prediction, coverage-aware surveillance, the v2 service and endpoints.
No network or real database: public data and Mongo collections are faked."""

import json
import re
from datetime import datetime

import pytest
from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.risk_forecasting.pipeline.features import ALL_FEATURES, FeatureSources
from components.risk_forecasting.pipeline.geography import DISTRICT_NAMES, DISTRICTS
from components.risk_forecasting.pipeline.predictor import V2Predictor, risk_tier
from components.risk_forecasting.pipeline.surveillance import (
    SurveillanceProvider, app_month_observations, observed_severity,
)
from components.risk_forecasting.repositories.forecast_record_repository import InMemoryForecastRecordRepository
from components.risk_forecasting.services.forecast_v2_service import ForecastV2Service


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


def test_missing_climate_input_falls_back_to_climatology_for_climate_model():
    predictor = V2Predictor.load("FMD")
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


def make_service(repo):
    counter = iter(range(10_000))
    return ForecastV2Service(repository_getter=lambda: repo, app_db_factory=fake_app_db,
                             sources_builder=fake_sources_builder,
                             id_generator=lambda: f"fdr_test{next(counter):05d}")


def test_forecast_period_builds_one_record_per_district_with_provenance():
    service = make_service(InMemoryForecastRecordRepository())
    records = service.forecast_period(2026, 10)
    assert len(records) == 2 * len(DISTRICT_NAMES)
    by_key = {(r.disease, r.district): r for r in records}
    # Anuradhapura FMD: previous month confirmed in the app, but neighbours lack coverage
    # -> surveillance unknown -> climatology baseline, clearly labelled.
    r = by_key[("FMD", "Anuradhapura")]
    assert r.surveillance_status == "CONFIRMED_OUTBREAK"
    assert r.previous_month_observation["verified_cases"] == 1
    assert r.forecaster == "climatology" and r.deployment_status == "baseline"
    assert r.feature_snapshot["neighbour_fraction_t1"] is None
    assert r.idempotency_key == "v2|FMD|Anuradhapura|2026-10|fmd_v2.0"
    assert r.input_quality == "COMPLETE"
    assert r.predicted_severity is None


def test_lsd_january_2025_uses_surveillance_model_from_curated_labels():
    records = make_service(InMemoryForecastRecordRepository()).forecast_period(2025, 1, ["LSD"])
    assert {r.forecaster for r in records} == {"S"}
    assert all(r.surveillance_source == "CURATED_DAPH_DATASET" for r in records)
    fmd = make_service(InMemoryForecastRecordRepository()).forecast_period(2025, 1, ["FMD"])
    assert {r.forecaster for r in fmd} == {"climatology"}  # December 2024 FMD labels unverified


def test_generate_period_is_idempotent_and_supersedes_older_records(monkeypatch):
    repo = InMemoryForecastRecordRepository()
    service = make_service(repo)
    from components.risk_forecasting.schemas import ForecastDecisionRecord
    old = ForecastDecisionRecord(
        forecast_id="fdr_v1_old", disease="FMD", district="Kandy", target_year=2026, target_month=10,
        generated_at="2026-08-01T00:00:00+00:00", probability=0.4, probability_pct=40.0, risk_level="MEDIUM",
        model_variant="30_feature_baseline", fallback_applied=True, data_quality="HISTORICAL_SAME_MONTH_PROXY",
        disclaimer="v1", created_at="2026-08-01T00:00:00+00:00", updated_at="2026-08-01T00:00:00+00:00")
    repo.save(old)

    first = service.generate_period(2026, 10, ["FMD"])
    assert first["summary"]["records"] == 25
    assert first["summary"]["superseded"] == 1
    assert repo.get_by_id("fdr_v1_old").status == "SUPERSEDED"

    second = service.generate_period(2026, 10, ["FMD"])
    assert second["summary"]["superseded"] == 0
    stored, total = repo.list(disease="FMD", target_year=2026, target_month=10, limit=200)
    assert total == 26  # 25 v2 records + the superseded v1 record; no duplicates


def test_dry_run_does_not_persist():
    repo = InMemoryForecastRecordRepository()
    result = make_service(repo).generate_period(2026, 10, ["LSD"], dry_run=True)
    assert result["summary"]["dry_run"] is True
    assert repo.list(limit=200)[1] == 0


# ─── endpoints ─────────────────────────────────────────────────────────────

def _app(role):
    from components.risk_forecasting import routes
    from components.risk_forecasting.integration.auth_adapter import (
        ViewerContextAuthorization, ViewerContextPermissions, ViewerContextResponse, get_viewer_context,
    )
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/v1/risk-forecasting")
    viewer = ViewerContextResponse(
        userId="u1", role=role,
        authorization=ViewerContextAuthorization(scopeLevel="NATIONAL", authorizedDistricts=["Colombo"], assignedFarmIds=[]),
        permissions=ViewerContextPermissions(viewDataQuality=True, viewModelTransparency=True, manageAlerts=False,
                                             recordResponse=False, viewReports=False))
    app.dependency_overrides[get_viewer_context] = lambda: viewer
    app.dependency_overrides[routes.get_forecast_v2_service] = lambda: make_service(InMemoryForecastRecordRepository())
    return TestClient(app)


def test_generate_endpoint_requires_daph():
    response = _app("VETERINARY_OFFICER").post("/api/v1/risk-forecasting/v2/forecasts/generate",
                                               json={"year": 2026, "month": 10, "dry_run": True})
    assert response.status_code == 403


def test_generate_endpoint_dry_run_for_daph():
    response = _app("DAPH_OFFICIAL").post("/api/v1/risk-forecasting/v2/forecasts/generate",
                                          json={"year": 2026, "month": 10, "diseases": ["LSD"], "dry_run": True})
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["records"] == 25 and body["summary"]["dry_run"] is True
    assert body["records"][0]["generated_by"] == "u1"


def test_model_card_endpoint():
    response = _app("DAPH_OFFICIAL").get("/api/v1/risk-forecasting/v2/model-card")
    assert response.status_code == 200
    card = response.json()
    assert card["FMD"]["deployment"]["surveillance_known"]["status"] == "validated"
    assert card["LSD"]["deployment"]["surveillance_known"]["status"] == "exploratory"


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
    assert entry["status"] == "ok" and entry["summary"]["records"] == 25 and entry["dry_run"] is True


def test_monthly_job_reports_storage_failure(tmp_path, monkeypatch):
    from components.risk_forecasting.jobs import run_monthly_forecast as job
    monkeypatch.setattr(job, "RUN_LOG", tmp_path / "runs.jsonl")

    class BrokenRepo(InMemoryForecastRecordRepository):
        def save(self, record):
            raise RuntimeError("Forecast record storage is temporarily unavailable.")

    assert job.main(["--year", "2026", "--month", "10", "--diseases", "FMD"],
                    service=make_service(BrokenRepo())) == 1
