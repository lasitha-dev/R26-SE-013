"""Tests for the Seasonal Outlook product (contract: model/docs/v2/SEASONAL_OUTLOOK_CONTRACT.md).
Pure and offline: no network, no database, no routes/core.database import (allowlisted)."""

import json
from datetime import datetime, timezone

import pytest

from components.risk_forecasting.jobs import run_seasonal_outlook as job
from components.risk_forecasting.pipeline.geography import DISTRICT_NAMES
from components.risk_forecasting.pipeline.predictor import V2Predictor
from components.risk_forecasting.repositories.outlook_repository import (
    InMemoryOutlookRepository, MongoOutlookRepository)
from components.risk_forecasting.schemas import SeasonalOutlookRecord
from components.risk_forecasting.services.seasonal_outlook_service import (
    OutlookDataError, OutlookTargetError, SeasonalOutlookService, climatology_hash)

OCT_15 = datetime(2026, 10, 15, 8, 0, tzinfo=timezone.utc)
FORBIDDEN = {"risk_level", "relative_risk", "contributions", "predicted_severity", "feature_snapshot"}


def make_service(repo=None, now=OCT_15, loader=V2Predictor.load):
    counter = iter(range(100_000))
    repo = repo if repo is not None else InMemoryOutlookRepository()
    return SeasonalOutlookService(repository_getter=lambda: repo, predictor_loader=loader,
                                  clock=lambda: now, id_generator=lambda: f"out_test{next(counter):06d}"), repo


# ─── content ───────────────────────────────────────────────────────────────

def test_plan_covers_every_district_and_disease_with_consistent_numbers():
    service, _ = make_service()
    records = service.plan(2026, 11)
    assert len(records) == 50
    assert {(r.disease, r.district) for r in records} == {(d, n) for d in ("FMD", "LSD") for n in DISTRICT_NAMES}
    assert len({r.idempotency_key for r in records}) == 50
    for r in records:
        assert 0 <= r.probability_low <= r.probability <= r.probability_high <= 1
        assert r.positive_years <= r.years_observed
        assert r.interval_level == pytest.approx(0.8)
        assert r.status == "ACTIVE" and r.replaces_outlook_id is None
        assert r.method_version == "district_month_climatology_v1"
        assert r.idempotency_key == f"OUTLOOK|{r.disease}|{r.district}|2026-11"


@pytest.mark.parametrize("disease,years", [("FMD", 7), ("LSD", 5)])
def test_probability_and_evidence_come_from_the_artifact(disease, years):
    service, _ = make_service()
    predictor = V2Predictor.load(disease)
    for r in (r for r in service.plan(2026, 11, [disease]) if r.district in ("Colombo", "Kandy", "Jaffna")):
        assert r.probability == pytest.approx(predictor.baseline(r.district, 11), abs=1e-6)
        assert r.years_observed == years
        assert r.source_artifact_version == predictor.model_version
        assert r.source_artifact_hash == climatology_hash(predictor.artifact)
        assert r.data_cutoff == predictor.artifact["training_period"][1]


def test_an_outlook_carries_no_tier_severity_or_stored_percentage():
    service, _ = make_service()
    record = service.plan(2026, 11, ["FMD"])[0]
    dumped = record.model_dump()
    assert FORBIDDEN.isdisjoint(dumped)                    # serving adds only the derived percentage
    assert dumped["probability_pct"] == round(record.probability * 100, 1)
    stored = MongoOutlookRepository._to_document(record)
    assert "probability_pct" not in stored and FORBIDDEN.isdisjoint(stored)
    assert stored["_id"] == record.outlook_id
    with pytest.raises(Exception):                         # extra fields are rejected
        SeasonalOutlookRecord(**{**stored, "risk_level": "LOW"})


def test_schema_rejects_an_interval_that_excludes_the_probability_or_impossible_counts():
    base = json.loads(make_service()[0].plan(2026, 11, ["FMD"])[0].model_dump_json())
    base.pop("probability_pct")
    with pytest.raises(Exception):
        SeasonalOutlookRecord(**{**base, "probability_low": base["probability"] + 0.01})
    with pytest.raises(Exception):
        SeasonalOutlookRecord(**{**base, "positive_years": base["years_observed"] + 1})


def test_climatology_hash_is_stable_and_sensitive():
    artifact = V2Predictor.load("FMD").artifact
    assert climatology_hash(artifact) == climatology_hash(json.loads(json.dumps(artifact)))
    changed = json.loads(json.dumps(artifact))
    changed["climatology"]["overall"] += 0.01
    assert climatology_hash(changed) != climatology_hash(artifact)


# ─── next month only ───────────────────────────────────────────────────────

@pytest.mark.parametrize("target", [(2026, 10), (2026, 12), (2027, 1), (2025, 11)])
def test_only_the_next_month_can_be_issued(target):
    service, _ = make_service()
    with pytest.raises(OutlookTargetError):
        service.plan(*target)


def test_year_boundary_and_lead_days():
    service, _ = make_service(now=datetime(2026, 12, 20, tzinfo=timezone.utc))
    records = service.plan(2027, 1)
    assert {r.lead_days for r in records} == {12} and {r.target_year for r in records} == {2027}
    assert {r.lead_days for r in make_service()[0].plan(2026, 11)} == {17}   # Oct 15 -> Nov 1
    assert {r.issue_date for r in make_service()[0].plan(2026, 11)} == {"2026-10-15"}


def test_missing_evidence_fails_closed_instead_of_falling_back():
    def loader(disease):
        predictor = V2Predictor.load(disease)
        artifact = json.loads(json.dumps(predictor.artifact))
        artifact["climatology"].pop("counts")
        return V2Predictor(artifact)

    service, _ = make_service(loader=loader)
    with pytest.raises(OutlookDataError):
        service.plan(2026, 11)


# ─── storing, idempotency, corrections ─────────────────────────────────────

def test_dry_run_writes_nothing_and_a_real_run_is_idempotent():
    service, repo = make_service()
    preview = service.generate(2026, 11, dry_run=True)
    assert preview["status"] == "PREVIEW" and preview["would_create"] == 50 and repo.list()[1] == 0

    first = service.generate(2026, 11, dry_run=False)
    assert first["saved"] == 50 and first["status"] == "OK" and repo.list()[1] == 50
    ids = {r.outlook_id for r in repo.list(limit=200)[0]}

    again = service.generate(2026, 11, dry_run=False)
    assert again["saved"] == 0 and again["already_issued"] == 50 and again["would_create"] == 0
    assert {r.outlook_id for r in repo.list(limit=200)[0]} == ids          # nothing rewritten


def test_a_failure_for_one_record_is_reported_and_a_rerun_completes_the_rest():
    class FlakyRepository(InMemoryOutlookRepository):
        fail_once = True

        def save(self, record):
            if self.fail_once and record.district == "Kandy" and record.disease == "FMD":
                FlakyRepository.fail_once = False
                raise ValueError("boom")
            return super().save(record)

    service, repo = make_service(repo=FlakyRepository())
    summary = service.generate(2026, 11, dry_run=False)
    assert summary["status"] == "PARTIAL" and summary["saved"] == 49 and len(summary["failed"]) == 1
    assert service.generate(2026, 11, dry_run=False)["saved"] == 1
    assert repo.list()[1] == 50


def test_void_and_correct_keep_the_original_and_allow_one_active_head():
    service, repo = make_service()
    service.generate(2026, 11, ["FMD"], dry_run=False)
    original = repo.get_by_key("OUTLOOK|FMD|Colombo|2026-11")

    voided = service.void(original.outlook_id)
    assert voided.status == "VOIDED" and repo.get_by_key(original.idempotency_key) is None
    assert repo.list(disease="FMD", district="Colombo")[1] == 1             # kept for audit
    # a voided key can be issued again by a normal run
    assert service.generate(2026, 11, ["FMD"], dry_run=False)["saved"] == 1

    head = repo.get_by_key("OUTLOOK|FMD|Colombo|2026-11")
    replacement = head.model_copy(update={"outlook_id": "out_replacement", "probability": 0.04, "probability_high": 0.2})
    corrected = service.correct(head.outlook_id, replacement)
    assert corrected.replaces_outlook_id == head.outlook_id and corrected.status == "ACTIVE"
    assert repo.get_by_key("OUTLOOK|FMD|Colombo|2026-11").outlook_id == "out_replacement"
    statuses = {r.outlook_id: r.status for r in repo.list(disease="FMD", district="Colombo")[0]}
    assert statuses[head.outlook_id] == "CORRECTED" and statuses[original.outlook_id] == "VOIDED"
    with pytest.raises(ValueError):                                          # two active heads are impossible
        repo.save(head.model_copy(update={"outlook_id": "out_second", "status": "ACTIVE"}))


# ─── Mongo adapter safety ──────────────────────────────────────────────────

class FakeCursor(list):
    def sort(self, *a, **k): return self
    def skip(self, *a, **k): return self
    def limit(self, *a, **k): return self


class FakeCollection:
    def __init__(self):
        self.calls = []
        self.docs = []

    def insert_one(self, doc): self.calls.append("insert_one"); self.docs.append(doc)
    def find_one(self, q): self.calls.append("find_one"); return next((d for d in self.docs if all(d.get(k) == v for k, v in q.items())), None)
    def count_documents(self, q): self.calls.append("count_documents"); return len(self.docs)
    def find(self, q): self.calls.append("find"); return FakeCursor(self.docs)
    def create_index(self, *a, **k): self.calls.append("create_index")


def test_mongo_adapter_reads_and_constructs_without_creating_indexes():
    collection = FakeCollection()
    repo = MongoOutlookRepository(collection=collection)
    assert collection.calls == []                                            # construction does no I/O
    repo.list(disease="FMD")
    repo.get_by_key("OUTLOOK|FMD|Colombo|2026-11")
    assert "create_index" not in collection.calls
    repo.ensure_indexes()
    assert collection.calls.count("create_index") == 2


def test_mongo_adapter_round_trips_a_record_without_a_stored_percentage():
    collection = FakeCollection()
    repo = MongoOutlookRepository(collection=collection)
    record = make_service()[0].plan(2026, 11, ["LSD"])[0]
    repo.save(record)
    assert "probability_pct" not in collection.docs[0]
    assert repo.get_by_key(record.idempotency_key) == record


# ─── CLI job ───────────────────────────────────────────────────────────────

@pytest.fixture
def run_log(tmp_path, monkeypatch):
    monkeypatch.setattr(job, "RUN_LOG", tmp_path / "runs" / "outlook_runs.jsonl")
    return job.RUN_LOG


def test_job_dry_run_exit_codes_and_log(run_log, capsys):
    service, repo = make_service()
    assert job.main(["--year", "2026", "--month", "11", "--dry-run"], service=service) == 0
    assert repo.list()[1] == 0
    entry = json.loads(run_log.read_text().splitlines()[-1])
    assert entry["status"] == "preview" and entry["dry_run"] is True and entry["summary"]["would_create"] == 50

    assert job.main(["--year", "2026", "--month", "12", "--dry-run"], service=service) == 2   # not the next month
    assert json.loads(run_log.read_text().splitlines()[-1])["status"] == "target_not_allowed"

    assert job.main(["--year", "2026", "--month", "11"], service=service) == 0
    assert repo.list()[1] == 50


def test_job_reports_storage_failure_and_ensure_indexes_is_explicit(run_log):
    class Down:
        def get_by_key(self, key): raise RuntimeError("down")
        def ensure_indexes(self): self.indexed = True

    down = Down()
    service, _ = make_service(repo=down)
    assert job.main(["--year", "2026", "--month", "11", "--dry-run"], service=service) == 1
    assert not hasattr(down, "indexed")                                      # a dry run never touches indexes
    assert job.main(["--ensure-indexes"], service=service) == 0
    assert down.indexed is True
    with pytest.raises(SystemExit):
        job.parse_args(["--ensure-indexes", "--dry-run"])
