"""
Import DAPH bulletin rows (district-month outbreak facts) so the v2 forecaster knows the previous
month's status in districts the app does not cover yet.

From backend/ (the Atlas connection comes from backend/.env):

    python -m components.risk_forecasting.jobs.import_bulletin bulletin.csv                 # preview, writes nothing
    python -m components.risk_forecasting.jobs.import_bulletin bulletin.csv --confirm N     # N = "rows_to_write" from the preview

CSV columns: disease, district, year, month, outbreak (1|0), cases, deaths, source_document, entered_by
(see docs/v2/bulletin_template.csv). Only explicitly entered rows are stored; a district-month that is
missing from the file stays unknown. Rows for verified curated-label years are skipped.

Exit codes: 0 ok / preview, 1 storage unavailable, 2 file unreadable or validation errors,
3 confirmation missing or stale (nothing written).
"""

import argparse
import json
import sys
from pathlib import Path

from components.risk_forecasting.pipeline.bulletin_import import (
    COLLECTION, ImportBlocked, StaleImportPreview, apply_import, fetch_existing, parse_bulletin_csv, plan_import)


def main(argv=None, collection=None):
    parser = argparse.ArgumentParser(description="Preview or import DAPH bulletin rows.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--confirm", type=int, default=None,
                        help="Write the rows; must equal 'rows_to_write' from a preview of the same file.")
    args = parser.parse_args(argv)

    try:
        text = args.file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(json.dumps({"status": "unreadable_file", "error": str(exc)}, indent=2))
        return 2
    rows, errors = parse_bulletin_csv(text)

    try:
        if collection is None:
            # Production path only; tests always pass a collection. Loads the Atlas client lazily.
            from components.risk_forecasting.routes import get_app_db
            collection = get_app_db()[COLLECTION]
        if args.confirm is None:
            plan = plan_import(rows, fetch_existing(collection, rows), errors)
            outcome, code = {"status": "preview", **plan.summary()}, (2 if plan.errors else 0)
        else:
            outcome, code = apply_import(collection, rows, errors, args.confirm), 0
    except ImportBlocked as exc:
        outcome, code = {"status": "blocked", "error": str(exc), "error_details": errors}, 2
    except StaleImportPreview as exc:
        outcome, code = {"status": "stale_preview", "error": str(exc)}, 3
    except Exception as exc:  # database unreachable
        outcome, code = {"status": "storage_unavailable", "error": str(exc)}, 1
    print(json.dumps(outcome, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
