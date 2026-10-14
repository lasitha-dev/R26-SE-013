"""
Seasonal Outlook job: issues the climatology-based outlook for the NEXT month.

    python -m components.risk_forecasting.jobs.run_seasonal_outlook --dry-run          # preview, writes nothing
    python -m components.risk_forecasting.jobs.run_seasonal_outlook --year 2026 --month 11   # store (needs approval)
    python -m components.risk_forecasting.jobs.run_seasonal_outlook --ensure-indexes   # one-time, approved phase only

Rules (see model/docs/v2/SEASONAL_OUTLOOK_CONTRACT.md):
- only the month after today's month can be issued;
- `--dry-run` and read paths never create a collection or an index; indexes are created only by `--ensure-indexes`;
- an outlook that already exists is reused, never rewritten.

Exit codes: 0 success, 1 storage unavailable, 2 bad arguments or target not allowed, 3 artifact lacks evidence,
4 partial failure (re-running is safe).
Each run appends a JSON line to model/data/cache/runs/outlook_runs.jsonl.
"""

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from components.risk_forecasting.services.seasonal_outlook_service import (
    OutlookDataError, OutlookTargetError, next_month)

RUN_LOG = Path(__file__).resolve().parents[1] / "model" / "data" / "cache" / "runs" / "outlook_runs.jsonl"


def parse_args(argv=None):
    target_year, target_month = next_month(date.today())
    parser = argparse.ArgumentParser(description="Issue the next-month Seasonal Outlook.")
    parser.add_argument("--year", type=int, default=target_year)
    parser.add_argument("--month", type=int, default=target_month)
    parser.add_argument("--diseases", nargs="+", default=["FMD", "LSD"], choices=["FMD", "LSD"])
    parser.add_argument("--dry-run", action="store_true", help="Preview only: compute and report, write nothing.")
    parser.add_argument("--ensure-indexes", action="store_true",
                        help="Create the collection indexes and exit (approved initialisation phase only).")
    args = parser.parse_args(argv)
    if not (2017 <= args.year <= 2030 and 1 <= args.month <= 12):
        parser.error("year must be 2017-2030 and month 1-12")
    if args.ensure_indexes and args.dry_run:
        parser.error("--ensure-indexes cannot be combined with --dry-run")
    return args


def main(argv=None, service=None):
    args = parse_args(argv)
    started = datetime.now(timezone.utc).isoformat()
    if service is None:
        from components.risk_forecasting.jobs.production_wiring import build_outlook_service
        service = build_outlook_service()
    try:
        if args.ensure_indexes:
            service.repository_getter().ensure_indexes()
            outcome, code = {"status": "indexes_ensured"}, 0
        else:
            summary = service.generate(args.year, args.month, args.diseases, dry_run=args.dry_run)
            outcome, code = {"status": summary["status"].lower(), "summary": summary}, (4 if summary["status"] == "PARTIAL" else 0)
    except OutlookTargetError as exc:
        outcome, code = {"status": "target_not_allowed", "error": str(exc)}, 2
    except OutlookDataError as exc:
        outcome, code = {"status": "artifact_incomplete", "error": str(exc)}, 3
    except RuntimeError as exc:
        outcome, code = {"status": "storage_unavailable", "error": str(exc)}, 1

    entry = {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
             "target": f"{args.year:04d}-{args.month:02d}", "diseases": args.diseases,
             "dry_run": args.dry_run, "ensure_indexes": args.ensure_indexes, **outcome}
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as log:
        log.write(json.dumps(entry) + "\n")
    print(json.dumps(entry, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
