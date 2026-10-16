"""
Monthly severity job (Stage 2, district level). READ-ONLY: it reads verified app records and reports; it never writes
to the database and never deploys a model.

    python -m components.risk_forecasting.jobs.run_severity_monthly                 # last 12 completed months, prints the report
    python -m components.risk_forecasting.jobs.run_severity_monthly --months 6 --report out.json

States: INSUFFICIENT_DATA (not enough monthly counts yet), EVALUATED_NOT_BETTER, EVALUATED_BETTER (issuing a
severity model then needs a separate approval). See model/docs/v2/STAGE2_MONTHLY_PIPELINE.md.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from components.risk_forecasting.pipeline.severity_monthly import prev_month, run

FIRST_APP_YEAR = 2025          # earlier months are covered by the curated labels, not by app records


def months_back(end_year: int, end_month: int, count: int):
    months, (y, m) = [], (end_year, end_month)
    for _ in range(count):
        if y < FIRST_APP_YEAR:
            break
        months.append((y, m))
        y, m = prev_month(y, m)
    return sorted(months)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Read-only monthly severity report.")
    parser.add_argument("--months", type=int, default=12, help="How many completed months to read (default 12).")
    parser.add_argument("--diseases", nargs="+", default=["FMD", "LSD"], choices=["FMD", "LSD"])
    parser.add_argument("--report", type=Path, default=None, help="Also write the report JSON to this file.")
    args = parser.parse_args(argv)
    if not 1 <= args.months <= 60:
        parser.error("months must be 1-60")
    return args


def main(argv=None, db_factory=None, today=None):
    args = parse_args(argv)
    today = today or date.today()
    end = prev_month(today.year, today.month)                     # the current month is not complete
    months = months_back(end[0], end[1], args.months)
    if db_factory is None:
        from components.risk_forecasting.routes import get_app_db
        db_factory = get_app_db
    from components.risk_forecasting.pipeline.surveillance import app_month_observations
    db = db_factory()
    report = {"window": [f"{y}-{m:02d}" for y, m in months], "diseases": {}}
    for disease in args.diseases:
        observations = {(y, m): app_month_observations(db, disease, y, m) for y, m in months}
        report["diseases"][disease] = run(observations, disease)
    text = json.dumps(report, indent=1)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
