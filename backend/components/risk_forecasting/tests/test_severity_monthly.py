"""Tests for the monthly severity pipeline. Pure and offline: no database, no network, no routes import.
Every simulated observation below is SYNTHETIC test data, generated in memory and never stored."""

import random

import pytest

from components.risk_forecasting.jobs import run_severity_monthly as job
from components.risk_forecasting.pipeline.geography import DISTRICT_NAMES
from components.risk_forecasting.pipeline.severity_monthly import (
    BETTER, INSUFFICIENT, NOT_BETTER, build_rows, month_index, prev_month, readiness, run, training_pairs)
from components.risk_forecasting.pipeline.surveillance import DistrictObservation


def obs(cases, deaths, status="CONFIRMED_OUTBREAK"):
    return DistrictObservation(status, "APP_VERIFIED_CASES_AND_DEATHS", cases, deaths)


def unknown():
    return DistrictObservation("NO_SURVEILLANCE_COVERAGE", "APP_VERIFIED_CASES_AND_DEATHS", None, None)


def months(start_year, start_month, count):
    y, m = start_year, start_month
    out = []
    for _ in range(count):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def synthetic_observations(n_months, districts, seed=3, persistence=0.0):
    """SYNTHETIC: random cases/deaths per reporting district-month. `persistence` > 0 makes a month's
    size depend on the previous month's (only used to exercise the 'better' branch)."""
    rng = random.Random(seed)
    result, last = {}, {d: 0 for d in districts}
    for (y, m) in months(2025, 1, n_months):
        month = {d: unknown() for d in DISTRICT_NAMES}
        for d in districts:
            base = rng.choice([0, 0, 1, 3, 8, 15, 28])
            cases = max(0, int(round(base + persistence * last[d])))
            deaths = rng.choice([0, 0, 0, 1, 2, 3]) if cases else 0
            month[d] = obs(cases, deaths, "CONFIRMED_OUTBREAK" if cases or deaths else "NO_REPORTED_CASES")
            last[d] = cases
        result[(y, m)] = month
    return result


# ─── table ────────────────────────────────────────────────────────────────

def test_unknown_districts_are_left_out_not_counted_as_zero():
    rows = build_rows({(2026, 9): {"Colombo": obs(2, 1), "Galle": unknown()}})
    assert ("Colombo", 2026, 9) in rows and ("Galle", 2026, 9) not in rows


def test_severity_uses_cases_plus_ten_times_deaths_and_the_documented_cut_offs():
    def klass(cases, deaths):
        return build_rows({(2026, 9): {"Colombo": obs(cases, deaths)}})[("Colombo", 2026, 9)]["severity"]
    assert klass(9, 0) == "LOW" and klass(10, 0) == "MEDIUM" and klass(0, 1) == "MEDIUM"
    assert klass(29, 0) == "MEDIUM" and klass(30, 0) == "HIGH" and klass(0, 3) == "HIGH"


def test_a_month_with_no_cases_or_deaths_is_not_an_outbreak_and_has_no_class():
    row = build_rows({(2026, 9): {"Colombo": obs(0, 0, "NO_REPORTED_CASES")}})[("Colombo", 2026, 9)]
    assert row["outbreak"] is False and row["severity"] is None


def test_pairs_need_an_observed_previous_month_and_use_its_numbers():
    rows = build_rows({(2026, 8): {"Colombo": obs(4, 0), "Galle": unknown()},
                       (2026, 9): {"Colombo": obs(12, 1), "Galle": obs(5, 0)}})
    pairs = training_pairs(rows)
    assert [p["district"] for p in pairs] == ["Colombo"]          # Galle's previous month is unknown -> no pair
    assert pairs[0]["y"] == 1 and pairs[0]["prev_class"] == 0      # 12 + 10 x 1 = 22 -> MEDIUM; previous month 4 -> LOW
    assert pairs[0]["month_index"] == month_index(2026, 9)


def test_month_arithmetic_across_a_year_boundary():
    assert prev_month(2027, 1) == (2026, 12) and prev_month(2026, 10) == (2026, 9)


# ─── gate ─────────────────────────────────────────────────────────────────

def test_few_months_of_data_is_insufficient_and_nothing_is_evaluated():
    report = run(synthetic_observations(3, ["Colombo", "Gampaha"]), "FMD", synthetic=True)
    assert report["state"] == INSUFFICIENT and report["evaluation"] is None and report["synthetic"] is True
    assert report["readiness"]["checks"]["outbreak_district_months"]["need"] == 100


def test_the_gate_needs_every_class_not_only_enough_rows():
    rows = build_rows({(2026, m): {d: obs(1, 0) for d in DISTRICT_NAMES[:10]} for m in range(1, 13)})   # 120 LOW rows
    gate = readiness(rows)
    assert gate["checks"]["outbreak_district_months"]["have"] >= 100 and gate["checks"]["distinct_months"]["have"] == 12
    assert gate["ready"] is False and gate["class_counts"]["HIGH"] == 0


# ─── simulation of a deployment (synthetic) ───────────────────────────────

def test_simulated_deployment_moves_from_insufficient_to_an_evaluation():
    districts = DISTRICT_NAMES[:12]
    early = run(synthetic_observations(4, districts), "FMD", synthetic=True)
    late = run(synthetic_observations(24, districts), "FMD", synthetic=True)
    assert early["state"] == INSUFFICIENT
    assert late["readiness"]["ready"] is True and late["state"] in (BETTER, NOT_BETTER)
    evaluation = late["evaluation"]
    assert evaluation["test_months"] >= 3 and set(evaluation["models"]) == {"national", "persistence", "district_history", "ordinal"}
    assert set(evaluation["decision_rule"]) == {"rps_below_every_baseline", "ordinal_mae_not_above_best_baseline",
                                                "better_than_best_baseline_in_most_months", "no_calibration_reversal"}


def test_random_synthetic_counts_do_not_produce_a_deployable_model():
    # months are independent of each other here, so a model must not be declared better than the baselines
    results = [run(synthetic_observations(24, DISTRICT_NAMES[:12], seed=s), "FMD", synthetic=True)["state"] for s in (1, 2, 3)]
    assert BETTER not in results


def test_report_never_contains_a_forecast_or_a_stored_field():
    report = run(synthetic_observations(24, DISTRICT_NAMES[:12]), "LSD", synthetic=True)
    text = str(report)
    assert "predicted_severity" not in text and "risk_level" not in text


# ─── job ──────────────────────────────────────────────────────────────────

class _ReadOnlyDb:
    """Any write attempt fails the test; reads return nothing."""
    def __getitem__(self, name):
        return self
    def find(self, *a, **k):
        return []
    def find_one(self, *a, **k):
        return None
    def __getattr__(self, name):
        if name.startswith(("insert", "update", "delete", "replace", "drop", "create", "bulk")):
            raise AssertionError(f"write attempted: {name}")
        raise AttributeError(name)


def test_job_reads_only_and_reports_insufficient_data_on_an_empty_database(capsys, tmp_path):
    out = tmp_path / "report.json"
    from datetime import date
    code = job.main(["--months", "3", "--report", str(out)], db_factory=lambda: _ReadOnlyDb(), today=date(2026, 10, 14))
    assert code == 0 and out.exists()
    printed = capsys.readouterr().out
    assert "INSUFFICIENT_DATA" in printed and '"2026-09"' in printed and '"2026-10"' not in printed   # current month excluded


def test_job_window_starts_no_earlier_than_the_first_app_year():
    assert job.months_back(2025, 2, 12) == [(2025, 1), (2025, 2)]
