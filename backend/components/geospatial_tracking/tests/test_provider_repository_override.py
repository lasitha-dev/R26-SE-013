"""GEO-MONGODB-NATIVE-INTEGRATION-24B: `repositories/provider.py`'s
composition-root override hook.

Verifies: (1) default behavior is completely unchanged -- no override
installed still returns a fresh `SQLiteOutbreakRepository`; (2) an
installed override redirects every subsequent `create_outbreak_repository()`
call, including calls made from OTHER modules that only import
`create_outbreak_repository` itself (`api/router.py::get_repository`,
`services/transport/geospatial_snapshot_10b.py::managed_repository_10b`)
-- proving the swap needs no change to router/transport code; (3) passing
`None` restores the default. Every test resets the override in a `finally`
so this module can never leak state into another test file."""

from __future__ import annotations

from components.geospatial_tracking.repositories import provider
from components.geospatial_tracking.repositories.mongo_repository import MongoOutbreakRepository
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.services.transport.geospatial_snapshot_10b import managed_repository_10b

from ._mongo_repository_fakes import FakeSyncCollection


def _mongo_repo() -> MongoOutbreakRepository:
    return MongoOutbreakRepository(
        FakeSyncCollection(), FakeSyncCollection(), FakeSyncCollection(), FakeSyncCollection(),
    )


def _point_default_path_at_schema_db(monkeypatch, tmp_path):
    """The default provider now refuses a missing/empty file, so these
    tests use a real schema-initialized temp DB instead of whatever sits
    at the developer's default path."""
    db_path = tmp_path / "pistes_test.db"
    seed = SQLiteOutbreakRepository(db_path)
    seed.init_schema()
    seed.close()
    monkeypatch.setattr(provider, "default_sqlite_db_path", lambda: db_path)


def test_default_provider_is_unchanged_sqlite_when_no_override_installed(monkeypatch, tmp_path):
    _point_default_path_at_schema_db(monkeypatch, tmp_path)
    provider.set_repository_factory_override(None)
    repo = provider.create_outbreak_repository()
    try:
        assert isinstance(repo, SQLiteOutbreakRepository)
    finally:
        repo.close()


def test_override_redirects_create_outbreak_repository_to_mongo():
    try:
        provider.set_repository_factory_override(_mongo_repo)
        repo = provider.create_outbreak_repository()
        try:
            assert isinstance(repo, MongoOutbreakRepository)
        finally:
            repo.close()
    finally:
        provider.set_repository_factory_override(None)


def test_override_is_picked_up_by_managed_repository_10b_without_any_transport_code_change():
    """`services/transport/geospatial_snapshot_10b.py::managed_repository_10b`
    (backing `/analysis/{id}/summary|cells|sources` and the WebSocket
    transport) only ever calls `create_outbreak_repository()` -- it must
    transparently pick up whichever backend the composition root
    installed, exactly like `api/router.py::get_repository` does."""
    try:
        provider.set_repository_factory_override(_mongo_repo)
        with managed_repository_10b() as repo:
            assert isinstance(repo, MongoOutbreakRepository)
    finally:
        provider.set_repository_factory_override(None)


def test_override_none_restores_default_sqlite_provider(monkeypatch, tmp_path):
    _point_default_path_at_schema_db(monkeypatch, tmp_path)
    provider.set_repository_factory_override(_mongo_repo)
    mongo_repo = provider.create_outbreak_repository()
    mongo_repo.close()
    assert isinstance(mongo_repo, MongoOutbreakRepository)

    provider.set_repository_factory_override(None)
    sqlite_repo = provider.create_outbreak_repository()
    try:
        assert isinstance(sqlite_repo, SQLiteOutbreakRepository)
    finally:
        sqlite_repo.close()


def test_missing_default_db_is_refused_and_never_created(monkeypatch, tmp_path):
    missing = tmp_path / "absent.db"
    monkeypatch.setattr(provider, "default_sqlite_db_path", lambda: missing)
    provider.set_repository_factory_override(None)
    try:
        provider.create_outbreak_repository()
        raise AssertionError("expected ScientificDatasetUnavailableError")
    except provider.ScientificDatasetUnavailableError as exc:
        assert exc.status == "SCIENTIFIC_DATASET_UNAVAILABLE"
    assert not missing.exists()


def test_zero_byte_default_db_is_refused(monkeypatch, tmp_path):
    empty = tmp_path / "empty.db"
    empty.write_bytes(b"")
    monkeypatch.setattr(provider, "default_sqlite_db_path", lambda: empty)
    provider.set_repository_factory_override(None)
    try:
        provider.create_outbreak_repository()
        raise AssertionError("expected ScientificDatasetUnavailableError")
    except provider.ScientificDatasetUnavailableError:
        pass
    assert empty.stat().st_size == 0
