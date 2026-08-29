"""Checkpoint 10B.1 Part 8: single repository-provider boundary.

Scientific/runtime consumers depend on the `OutbreakRepository`
Protocol (`repositories/base.py`); the current DEVELOPMENT provider is
SQLite-backed. `create_outbreak_repository()` is the ONE place that
knows the concrete class -- both the `/origins` HTTP dependency
(`api/router.py::get_repository`) and the snapshot cache-miss
computation (`services/transport/geospatial_snapshot_10b.py`) call it,
so a future Mongo-backed provider requires changing this one function,
never router or transport code.

Mongo is NOT implemented here -- `motor` is already listed in
`backend/requirements.txt` for that eventual work, but no Mongo client
is constructed anywhere in this component yet. This module changes no
repository query semantics.
"""

from __future__ import annotations

from pathlib import Path

from ..config import DEFAULT_SQLITE_DB_PATH
from .base import OutbreakRepository
from .sqlite_repository import SQLiteOutbreakRepository

REPOSITORY_PROVIDER_KIND_10B1 = "SQLITE_DEVELOPMENT_PROVIDER"


def create_outbreak_repository() -> OutbreakRepository:
    """Returns a new, unopened-transaction `OutbreakRepository`
    instance backed by the current development SQLite database. Caller
    owns the instance and is responsible for calling `.close()`."""
    db_path = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
    return SQLiteOutbreakRepository(db_path)
