"""Reproducible local dev-DB seeding: creates/opens the gitignored SQLite
dev database and imports Checkpoint 2.5's conservative canonical CSV into
it (master-prompt §7). Run locally only — never in CI, since
local_data/processed/canonical_outbreaks_conservative.csv is gitignored
and not present in the repo (same convention as
data_processing/build_canonical.py and audit.py).

    cd backend
    python -m components.geospatial_tracking.services.seed_dev_db \
        ../local_data/processed/canonical_outbreaks_conservative.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

from ..config import DEFAULT_SQLITE_DB_PATH
from ..repositories.sqlite_repository import SQLiteOutbreakRepository
from .historical_import import import_conservative_csv


def seed(csv_path: str | Path, db_path: str | Path | None = None) -> int:
    resolved_db_path = Path(db_path) if db_path is not None else Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
    repo = SQLiteOutbreakRepository(resolved_db_path)
    repo.init_schema()
    try:
        return import_conservative_csv(repo, csv_path)
    finally:
        repo.close()


def main(csv_path: str) -> None:
    count = seed(csv_path)
    print(f"imported {count} historical records into the local dev DB")


if __name__ == "__main__":
    args = sys.argv[1:]
    csv_path = args[0] if args else "../local_data/processed/canonical_outbreaks_conservative.csv"
    main(csv_path)
