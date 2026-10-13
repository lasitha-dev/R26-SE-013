"""Tests for DAPH bulletin import and its effect on surveillance coverage (pure, offline)."""

import json
from datetime import datetime, timezone

import pytest

from components.risk_forecasting.jobs import import_bulletin
from components.risk_forecasting.pipeline.bulletin_import import (
    COLLECTION, ImportBlocked, StaleImportPreview, apply_import, fetch_existing, parse_bulletin_csv, plan_import)
from components.risk_forecasting.pipeline.geography import DISTRICT_NAMES
from components.risk_forecasting.pipeline.surveillance import SurveillanceProvider
from components.risk_forecasting.repositories.forecast_record_repository import InMemoryForecastRecordRepository
from components.risk_forecasting.tests.test_v2_service import FakeCollection, FakeDb, fake_app_db, make_service

HEADER = "disease,district,year,month,outbreak,cases,deaths,source_document,entered_by\n"


class WritableCollection(FakeCollection):
    def find(self, query=None, projection=None):
        query = dict(query or {})
        wanted = query.pop("_id", None)
        docs = super().find(query)
        if isinstance(wanted, dict) and "$in" in wanted:
            docs = [d for d in docs if d["_id"] in wanted["$in"]]
        return docs

    def replace_one(self, flt, document, upsert=False):
        self.docs[:] = [d for d in self.docs if d["_id"] != flt["_id"]]
        self.docs.append(dict(document))


def csv_of(*lines):
    return HEADER + "\n".join(lines) + "\n"


# ─── parsing and validation ────────────────────────────────────────────────

def test_valid_rows_are_parsed_and_districts_normalised():
    rows, errors = parse_bulletin_csv(csv_of(
        "FMD,Kandy District,2025,3,1,12,2,Bulletin 2025 p.14,a@b.lk",
        "lsd,galle,2025,3,0,,,Bulletin 2025 p.31,"))
    assert errors == []
    assert rows[0].key == "FMD|Kandy|2025-03" and (rows[0].cases, rows[0].deaths) == (12, 2)
    assert rows[1].key == "LSD|Galle|2025-03" and rows[1].cases is None and rows[1].entered_by is None


@pytest.mark.parametrize("line, fragment", [
    ("FMD,Kandy,2025,3,,5,0,doc,", "outbreak must be exactly 1 or 0"),          # blank is never read as 0
    ("FMD,Kandy,2025,3,yes,5,0,doc,", "outbreak must be exactly 1 or 0"),
    ("FMD,Kandy,2025,3,0,4,0,doc,", "outbreak 0 cannot have cases"),
    ("FMD,Atlantis,2025,3,1,,,doc,", "unknown district"),
    ("DOG,Kandy,2025,3,1,,,doc,", "disease must be one of"),
    ("FMD,Kandy,2025,13,1,,,doc,", "month 1-12"),
    ("FMD,Kandy,2025,3,1,,,,", "source_document"),
    ("FMD,Kandy,2025,3,1,-2,,doc,", "cases must be a whole number"),
    ("FMD,Kandy,abc,3,1,,,doc,", "year and month must be whole numbers"),
])
def test_invalid_rows_are_rejected_with_a_reason(line, fragment):
    rows, errors = parse_bulletin_csv(csv_of(line))
    assert rows == [] and len(errors) == 1
    assert errors[0]["line"] == 2 and fragment in errors[0]["error"]


def test_duplicates_and_missing_columns_are_reported():
    rows, errors = parse_bulletin_csv(csv_of(
        "FMD,Kandy,2025,3,1,,,doc,", "FMD,Kandy,2025,3,0,,,doc,"))
    assert len(rows) == 1 and "duplicate of line 2" in errors[0]["error"]
    _, errors = parse_bulletin_csv("disease,district\nFMD,Kandy\n")
    assert "missing column" in errors[0]["error"]


# ─── planning and applying ─────────────────────────────────────────────────

def test_plan_skips_verified_curated_years_but_not_unverified_fmd_2024():
    rows, _ = parse_bulletin_csv(csv_of(
        "FMD,Kandy,2022,3,1,,,doc,",     # curated FMD year -> skipped
        "FMD,Kandy,2024,3,1,,,doc,",     # unverified FMD year -> importable
        "LSD,Kandy,2024,3,1,,,doc,",     # curated LSD year -> skipped
        "LSD,Kandy,2025,3,1,,,doc,"))
    plan = plan_import(rows, {})
    assert sorted(plan.skipped_curated) == ["FMD|Kandy|2022-03", "LSD|Kandy|2024-03"]
    assert [r.key for r in plan.to_write] == ["FMD|Kandy|2024-03", "LSD|Kandy|2025-03"]


def test_apply_requires_a_confirmed_count_and_is_idempotent():
    collection = WritableCollection([])
    rows, errors = parse_bulletin_csv(csv_of("FMD,Kandy,2025,3,1,3,0,doc,", "FMD,Galle,2025,3,0,0,0,doc,"))
    with pytest.raises(ImportBlocked):
        apply_import(collection, rows, errors, None)
    with pytest.raises(StaleImportPreview):
        apply_import(collection, rows, errors, 5)
    assert collection.docs == []                                     # neither attempt wrote anything

    now = datetime(2026, 10, 14, tzinfo=timezone.utc)
    done = apply_import(collection, rows, errors, 2, now=now)
    assert done["written"] == 2 and {d["_id"] for d in collection.docs} == {"FMD|Kandy|2025-03", "FMD|Galle|2025-03"}
    assert all(d["imported_at"] == now.isoformat() for d in collection.docs)

    again = plan_import(rows, fetch_existing(collection, rows))
    assert again.unchanged == 2 and again.to_write == []
    assert apply_import(collection, rows, errors, 0)["written"] == 0


def test_changes_to_existing_rows_are_previewed_before_overwriting():
    collection = WritableCollection([])
    first, _ = parse_bulletin_csv(csv_of("FMD,Kandy,2025,3,0,0,0,doc A,"))
    apply_import(collection, first, [], 1)
    corrected, _ = parse_bulletin_csv(csv_of("FMD,Kandy,2025,3,1,7,0,doc B,"))
    plan = plan_import(corrected, fetch_existing(collection, corrected))
    assert len(plan.changed) == 1
    assert plan.changed[0]["before"]["outbreak"] == 0 and plan.changed[0]["after"]["outbreak"] == 1


def test_validation_errors_block_a_write():
    rows, errors = parse_bulletin_csv(csv_of("FMD,Kandy,2025,3,1,,,doc,", "FMD,Atlantis,2025,3,1,,,doc,"))
    collection = WritableCollection([])
    with pytest.raises(ImportBlocked):
        apply_import(collection, rows, errors, 1)
    assert collection.docs == []


# ─── effect on surveillance ────────────────────────────────────────────────

def db_with_bulletins(*docs):
    db = fake_app_db()
    db[COLLECTION] = WritableCollection(list(docs))
    return db


def bulletin(disease, district, year, month, outbreak, cases=None, deaths=None):
    return {"_id": f"{disease}|{district}|{year:04d}-{month:02d}", "disease": disease, "district": district,
            "year": year, "month": month, "outbreak": outbreak, "cases": cases, "deaths": deaths}


def test_bulletins_fill_unknown_districts_without_overriding_the_app():
    db = db_with_bulletins(
        bulletin("FMD", "Jaffna", 2026, 9, 1, 5, 1),        # not covered by the app -> confirmed from the bulletin
        bulletin("FMD", "Galle", 2026, 9, 0, 0, 0),         # not covered by the app -> bulletin negative is a known 0
        bulletin("FMD", "Anuradhapura", 2026, 9, 0, 0, 0),  # the app has a verified case -> the app wins
        bulletin("FMD", "Colombo", 2026, 9, 1, 2, 0),       # app covered but no cases -> bulletin positive confirms
    )
    month = SurveillanceProvider("FMD", {}, lambda: db).month(2026, 9)
    assert (month["Jaffna"].status, month["Jaffna"].source, month["Jaffna"].cases) == ("CONFIRMED_OUTBREAK", "DAPH_BULLETIN_IMPORT", 5)
    assert (month["Galle"].status, month["Galle"].outbreak) == ("NO_OUTBREAK_RECORDED", 0)
    assert month["Anuradhapura"].status == "CONFIRMED_OUTBREAK" and month["Anuradhapura"].source == "APP_VERIFIED_CASES_AND_DEATHS"
    assert month["Colombo"].status == "CONFIRMED_OUTBREAK" and month["Colombo"].source == "DAPH_BULLETIN_IMPORT"
    assert month["Kandy"].status == "NO_SURVEILLANCE_COVERAGE" and month["Kandy"].outbreak is None  # still unknown


def test_unverified_fmd_2024_can_be_verified_by_a_bulletin_but_curated_years_cannot_be_overridden():
    db = db_with_bulletins(bulletin("FMD", "Kandy", 2024, 3, 1, 4, 0), bulletin("FMD", "Kandy", 2022, 3, 1))
    provider = SurveillanceProvider("FMD", {("Kandy", 2022, 3): 0}, lambda: db)
    unverified = provider.month(2024, 3)
    assert unverified["Kandy"].status == "CONFIRMED_OUTBREAK"
    assert unverified["Galle"].status == "UNVERIFIED_LABEL"
    assert provider.month(2022, 3)["Kandy"].status == "NO_OUTBREAK_RECORDED"   # curated label wins


def test_an_unreachable_bulletin_source_never_creates_a_zero():
    class Broken(FakeDb):
        def __getitem__(self, name):
            if name == COLLECTION:
                raise RuntimeError("down")
            return super().__getitem__(name)

    db = Broken(fake_app_db())
    month = SurveillanceProvider("FMD", {}, lambda: db).month(2026, 9)
    assert month["Kandy"].outbreak is None and month["Anuradhapura"].status == "CONFIRMED_OUTBREAK"


def test_bulletin_coverage_switches_the_lsd_model_on():
    """The point of the import: with the previous two months known for every district, the LSD
    surveillance model runs instead of the climatology baseline."""
    docs = [bulletin("LSD", d, y, m, 0, 0, 0) for d in DISTRICT_NAMES for (y, m) in ((2026, 8), (2026, 9))]
    db = db_with_bulletins(*docs)

    def service(database):
        svc = make_service(InMemoryForecastRecordRepository(), clock=lambda: datetime(2026, 10, 14, tzinfo=timezone.utc))
        svc.app_db_factory = lambda: database
        return svc

    without = service(fake_app_db()).forecast_period(2026, 10, ["LSD"])
    assert {r.forecaster for r in without} == {"climatology"}
    with_bulletins = service(db).forecast_period(2026, 10, ["LSD"])
    assert {r.forecaster for r in with_bulletins} == {"A"}
    # districts the app covers keep their app observation; the rest now come from the bulletin
    assert {r.surveillance_source for r in with_bulletins} == {"DAPH_BULLETIN_IMPORT", "APP_VERIFIED_CASES_AND_DEATHS"}


# ─── command line ──────────────────────────────────────────────────────────

def test_cli_previews_then_writes_only_with_the_confirmed_count(tmp_path, capsys):
    path = tmp_path / "b.csv"
    path.write_text(csv_of("LSD,Kandy,2025,3,1,3,0,doc,"), encoding="utf-8")
    collection = WritableCollection([])

    assert import_bulletin.main([str(path)], collection=collection) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["status"] == "preview" and preview["rows_to_write"] == 1 and collection.docs == []

    assert import_bulletin.main([str(path), "--confirm", "9"], collection=collection) == 3
    assert collection.docs == []
    assert import_bulletin.main([str(path), "--confirm", "1"], collection=collection) == 0
    assert len(collection.docs) == 1


def test_cli_rejects_a_file_with_errors(tmp_path, capsys):
    path = tmp_path / "bad.csv"
    path.write_text(csv_of("LSD,Nowhere,2025,3,1,,,doc,"), encoding="utf-8")
    collection = WritableCollection([])
    assert import_bulletin.main([str(path)], collection=collection) == 2
    assert import_bulletin.main([str(path), "--confirm", "0"], collection=collection) == 2
    assert collection.docs == []
