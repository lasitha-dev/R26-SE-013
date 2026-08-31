"""Checkpoint 10B.1 Part 8: single repository-provider boundary.

Scientific/runtime consumers depend on the `OutbreakRepository`
Protocol (`repositories/base.py`); the current DEVELOPMENT provider is
SQLite-backed. `create_outbreak_repository()` is the ONE place that
knows the concrete class -- both the `/origins` HTTP dependency
(`api/router.py::get_repository`) and the snapshot cache-miss
computation (`services/transport/geospatial_snapshot_10b.py`) call it,
so a Mongo-backed provider requires changing only this one function
(via the override hook below), never router or transport code.

GEO-MONGODB-NATIVE-INTEGRATION-24B: `MongoOutbreakRepository`
(`repositories/mongo_repository.py`) is now implemented, but this
module's OWN default behavior is left byte-for-byte unchanged --
calling `create_outbreak_repository()` with no override still returns a
fresh SQLite-backed instance, exactly as before, so every existing
caller (standalone research scripts, `tests/test_sqlite_repository.py`,
any test that never installs an override) keeps working unmodified.

`set_repository_factory_override` is the ONE composition-root hook a
running application may call ONCE, at startup, to redirect every future
`create_outbreak_repository()` call (across this whole process) to a
different backend -- `backend/main.py`'s Geospatial composition block
is the only place in this codebase that calls it for the live app,
passing a factory that builds a `MongoOutbreakRepository` over the
host's existing `core.database.db` collections. No router/transport/
service file changes to pick this up -- they all still just call
`create_outbreak_repository()`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..config import DEFAULT_SQLITE_DB_PATH
from .base import OutbreakRepository
from .sqlite_repository import SQLiteOutbreakRepository

REPOSITORY_PROVIDER_KIND_10B1 = "SQLITE_DEVELOPMENT_PROVIDER"

_repository_factory_override: Callable[[], OutbreakRepository] | None = None


def set_repository_factory_override(factory: Callable[[], OutbreakRepository] | None) -> None:
    """GEO-MONGODB-NATIVE-INTEGRATION-24B composition-root hook. Pass a
    zero-argument factory to redirect every subsequent
    `create_outbreak_repository()` call to whatever backend it
    constructs (e.g. a `MongoOutbreakRepository` over the host's real
    collections); pass `None` to restore the default SQLite-backed
    development provider. Intended to be called exactly once, at
    process startup, by the single application composition root
    (`backend/main.py`) -- never by router/service/test code reaching
    for a shortcut."""
    global _repository_factory_override
    _repository_factory_override = factory


def create_outbreak_repository() -> OutbreakRepository:
    """Returns a new, unopened-transaction `OutbreakRepository`
    instance. Caller owns the instance and is responsible for calling
    `.close()`. Backed by the current development SQLite database
    UNLESS `set_repository_factory_override` has installed a different
    factory (Checkpoint GEO-MONGODB-NATIVE-INTEGRATION-24B) -- the
    default SQLite path is completely unchanged when no override is
    installed."""
    if _repository_factory_override is not None:
        return _repository_factory_override()
    db_path = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
    return SQLiteOutbreakRepository(db_path)
