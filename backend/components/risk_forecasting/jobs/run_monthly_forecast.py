"""
Monthly v2 forecast job.

Run on day 5 of every month (after CHIRPS preliminary and NASA POWER data for the
previous month are published), from backend/:

    python -m components.risk_forecasting.jobs.run_monthly_forecast            # current month
    python -m components.risk_forecasting.jobs.run_monthly_forecast --year 2025 --month 1
    python -m components.risk_forecasting.jobs.run_monthly_forecast --dry-run

Windows Task Scheduler (daily trigger is fine; the job is idempotent per period/model):
    Program:   python
    Arguments: -m components.risk_forecasting.jobs.run_monthly_forecast --trigger SCHEDULED
    Start in:  <repo>\\backend
Linux cron:  0 6 5 * *  cd <repo>/backend && python -m components.risk_forecasting.jobs.run_monthly_forecast --trigger SCHEDULED

Exit codes: 0 success, 1 storage unavailable, 2 bad arguments.
Each run appends a JSON line to model/data/cache/runs/forecast_runs.jsonl.
"""

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

RUN_LOG = Path(__file__).resolve().parents[1] / "model" / "data" / "cache" / "runs" / "forecast_runs.jsonl"


def parse_args(argv=None):
    today = date.today()
    parser = argparse.ArgumentParser(description="Generate and store v2 disease risk forecasts for a target month.")
    parser.add_argument("--year", type=int, default=today.year)
    parser.add_argument("--month", type=int, default=today.month)
    parser.add_argument("--diseases", nargs="+", default=["FMD", "LSD"], choices=["FMD", "LSD"])
    parser.add_argument("--dry-run", action="store_true", help="Compute without writing to the database.")
    parser.add_argument("--trigger", default="MANUAL", choices=["MANUAL", "SCHEDULED"])
    args = parser.parse_args(argv)
    if not (2017 <= args.year <= 2030 and 1 <= args.month <= 12):
        parser.error("year must be 2017-2030 and month 1-12")
    return args


def main(argv=None, service=None):
    args = parse_args(argv)
    if service is None:
        from components.risk_forecasting.repositories.mongo_forecast_record_repository import MongoForecastRecordRepository
        from components.risk_forecasting.routes import get_app_db
        from components.risk_forecasting.services.forecast_v2_service import ForecastV2Service
        repository = MongoForecastRecordRepository()
        service = ForecastV2Service(repository_getter=lambda: repository, app_db_factory=get_app_db)

    started = datetime.now(timezone.utc).isoformat()
    try:
        result = service.generate_period(args.year, args.month, args.diseases, generated_by="monthly_job",
                                         trigger_type=args.trigger, dry_run=args.dry_run)
        outcome, code = {"status": "ok", "summary": result["summary"]}, 0
    except RuntimeError as exc:
        outcome, code = {"status": "storage_unavailable", "error": str(exc)}, 1

    entry = {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
             "target": f"{args.year:04d}-{args.month:02d}", "diseases": args.diseases,
             "dry_run": args.dry_run, "trigger": args.trigger, **outcome}
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(entry) + "\n")
    print(json.dumps(entry, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
