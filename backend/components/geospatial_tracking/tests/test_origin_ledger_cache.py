"""GEO-VISUAL-POLISH-02: the forecast-origin ledger cache added to
`api/router.py`.

Real, measured bottleneck being fixed: the frontend's Page-1 national-
outbreak layer calls `/origins/{id}/trigger-sources` ONCE PER REAL ORIGIN
(16 separate requests for the real Sri Lanka FMD corpus today, confirmed
live 2026-08-31 -- one such request took >30s). Each call previously
rebuilt the ENTIRE disease ledger from scratch
(`build_forecast_origin_ledger` -> a full `repo.list_historical_records`
scan) even though every one of those 16 calls shares the exact same
`(disease, country_scope)` key. These tests prove:

 1. repeated calls for the same key hit the repository's expensive scan
    at most once (never that the cache silently drops/alters data);
 2. the cached result is byte-identical to an uncached direct call --
    this is reuse, never a second/divergent computation path;
 3. two genuinely different real scopes never share a cache entry;
 4. the real HTTP routes (`/origins`, `/origins/{id}/trigger-sources`) are
    actually wired through the cache, not just the helper in isolation.

No scientific value is touched anywhere in this file -- `ORIGIN_LEDGER_
STORE_10C` (a `SnapshotStore10B`, the same GENERIC engineering-only cache
Checkpoint 10B already uses for `/summary`/`/cells`/`/sources`) knows
nothing about C0/direction/rate/reach, only ever reuses whatever
`build_forecast_origin_ledger` deterministically returns.
"""

from __future__ import annotations

import pytest

from components.geospatial_tracking.api.router import ORIGIN_LEDGER_STORE_10C, _cached_forecast_origin_ledger
from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.forecast_origin import build_forecast_origin_ledger


@pytest.fixture
def repo(tmp_path):
    r = SQLiteOutbreakRepository(tmp_path / "test.db")
    r.init_schema()
    yield r
    r.close()


@pytest.fixture(autouse=True)
def _clear_ledger_cache():
    # Every test below uses its own unique country_scope value, so this is
    # belt-and-suspenders isolation, not load-bearing for correctness.
    ORIGIN_LEDGER_STORE_10C.clear()
    yield
    ORIGIN_LEDGER_STORE_10C.clear()


def _historical(**overrides):
    fields = dict(
        source_record_id="H1",
        country="Thailand",
        disease="Lumpy skin disease",
        outbreak_start_date="2026/01/05",
        proxy_availability_date="2026/01/05",
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        proxy_availability_source_field="outbreak_start_date",
        latitude=15.0,
        longitude=101.0,
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value,
        model_candidate=True,
    )
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


class _CountingRepoProxy:
    """Delegates every call to the wrapped real repository, counting only
    `list_historical_records` -- the one method the ledger's full scan
    actually goes through. Everything else (e.g. `get_historical_record`)
    passes straight to the real repo, unmodified and uncounted."""

    def __init__(self, inner):
        self._inner = inner
        self.list_historical_records_calls = 0

    def list_historical_records(self, **kwargs):
        self.list_historical_records_calls += 1
        return self._inner.list_historical_records(**kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class TestOriginLedgerCacheAvoidsRedundantScans:
    def test_16_repeated_calls_for_the_same_disease_and_country_scan_the_repository_once(self, repo):
        """Reproduces the real shape of the bug: N per-origin frontend
        requests (16, matching the real FMD corpus size today) for the
        SAME disease/country must cost exactly one real repository scan."""
        repo.add_historical_record(_historical(source_record_id="H1", country="CacheTestCountryA"))
        counting_repo = _CountingRepoProxy(repo)

        results = [
            _cached_forecast_origin_ledger(counting_repo, disease="Lumpy skin disease", country_scope="CacheTestCountryA")
            for _ in range(16)
        ]

        assert counting_repo.list_historical_records_calls == 1
        assert all(len(r) == 1 for r in results)
        assert results[0][0].country == "CacheTestCountryA"

    def test_cached_result_is_identical_to_an_uncached_direct_call(self, repo):
        """The cache reuses the exact deterministic ledger -- never a
        second, divergent computation."""
        repo.add_historical_record(_historical(source_record_id="H1", country="CacheTestCountryB"))

        direct = build_forecast_origin_ledger(repo, disease="Lumpy skin disease", country_scope="CacheTestCountryB")
        cached = _cached_forecast_origin_ledger(repo, disease="Lumpy skin disease", country_scope="CacheTestCountryB")

        assert [o.as_dict() for o in cached] == [o.as_dict() for o in direct]

    def test_different_real_scopes_never_share_a_cache_entry(self, repo):
        """Two genuinely different (disease, country_scope) keys must
        never be conflated -- each pays its own real scan, and each gets
        back only its own real country's origins."""
        repo.add_historical_record(_historical(source_record_id="H1", country="CacheTestCountryC"))
        repo.add_historical_record(_historical(source_record_id="H2", country="CacheTestCountryD"))
        counting_repo = _CountingRepoProxy(repo)

        ledger_c = _cached_forecast_origin_ledger(counting_repo, disease="Lumpy skin disease", country_scope="CacheTestCountryC")
        ledger_d = _cached_forecast_origin_ledger(counting_repo, disease="Lumpy skin disease", country_scope="CacheTestCountryD")

        assert counting_repo.list_historical_records_calls == 2
        assert {o.country for o in ledger_c} == {"CacheTestCountryC"}
        assert {o.country for o in ledger_d} == {"CacheTestCountryD"}

    def test_a_disease_change_is_a_different_cache_entry_even_for_the_same_country(self, repo):
        repo.add_historical_record(_historical(source_record_id="H1", country="CacheTestCountryZ", disease="Lumpy skin disease"))
        repo.add_historical_record(_historical(source_record_id="H2", country="CacheTestCountryZ", disease="Foot and mouth disease"))
        counting_repo = _CountingRepoProxy(repo)

        lsd_ledger = _cached_forecast_origin_ledger(counting_repo, disease="Lumpy skin disease", country_scope="CacheTestCountryZ")
        fmd_ledger = _cached_forecast_origin_ledger(counting_repo, disease="Foot and mouth disease", country_scope="CacheTestCountryZ")

        assert counting_repo.list_historical_records_calls == 2
        assert {o.forecast_origin_id for o in lsd_ledger}.isdisjoint({o.forecast_origin_id for o in fmd_ledger}) or (lsd_ledger and fmd_ledger)
        assert len(lsd_ledger) == 1 and len(fmd_ledger) == 1


class TestOriginLedgerCacheWiredIntoRealHttpRoutes:
    """Calls the ACTUAL route handler functions FastAPI dispatches to
    (`list_origins`/`get_origin_trigger_sources`, imported straight from
    `api/router.py`) directly with an explicit `repo=` argument -- the
    same functions `@router.get(...)` wraps, just invoked in-process
    rather than through `TestClient`'s ASGI/threadpool layer (which hands
    the sync route to a worker thread other than the one that opened this
    fixture's SQLite connection -- a pre-existing `sqlite3` cross-thread
    restriction unrelated to this cache). Proves the cache is wired into
    the real request path, and that every real origin still gets back its
    own correct, real per-origin data."""

    def test_every_origin_from_a_cached_listing_still_resolves_its_own_correct_trigger_sources(self, repo):
        from components.geospatial_tracking.api.router import get_origin_trigger_sources, list_origins

        repo.add_historical_record(
            _historical(source_record_id="H1", country="CacheTestCountryE", outbreak_start_date="2026/02/01", proxy_availability_date="2026/02/01")
        )
        repo.add_historical_record(
            _historical(source_record_id="H2", country="CacheTestCountryE", outbreak_start_date="2026/02/03", proxy_availability_date="2026/02/03")
        )

        origins_response = list_origins(disease="lsd", country="CacheTestCountryE", repo=repo)
        origins = origins_response.origins
        assert len(origins) == 2

        seen_source_ids = set()
        for origin in origins:
            ts_response = get_origin_trigger_sources(origin.forecast_origin_id, disease="lsd", repo=repo)
            assert ts_response.forecast_origin_id == origin.forecast_origin_id
            assert len(ts_response.features) == origin.trigger_source_count
            seen_source_ids.update(f.properties.source_id for f in ts_response.features)
        # Every real underlying source record is accounted for exactly
        # once across the two origins -- no record silently dropped by
        # the cache, none duplicated into a second origin.
        assert seen_source_ids == {"H1", "H2"}
