"""GEO-LIVE-05 Section 15: focused tests for the two concrete
`CaseEventSource` adapters. Both use only fakes (`_event_fakes.py`) --
never a real Mongo driver/network. Mirrors
`test_host_operational_adapter.py`'s `asyncio.run(...)` convention --
no `pytest-asyncio` plugin is installed in this repo."""

from __future__ import annotations

import asyncio

from components.geospatial_tracking.domain.operational_events import CaseChangeKind
from components.geospatial_tracking.repositories.mongo_case_event_source import (
    DeltaPollingCaseEventSource,
    MongoChangeStreamCaseEventSource,
)

from ._event_fakes import FakeDiagnosticCasesCollection, FakeWatchableCollection


def _run(coro):
    return asyncio.run(coro)


async def _no_real_delay(_seconds):
    await asyncio.sleep(0)


def _verified_case_doc(**overrides):
    doc = {
        "_id": "C1",
        "farm_id": "F1",
        "disease_name": "Lumpy Skin Disease",
        "verified": True,
        "created_at": "2026-01-01 09:00:00",
        "verified_at": "2026-01-02 10:00:00",
    }
    doc.update(overrides)
    return doc


class TestDeltaPollingCaseEventSource:
    def test_describes_transport_as_delta_refresh_never_push(self):
        source = DeltaPollingCaseEventSource(FakeDiagnosticCasesCollection())
        assert source.describe_transport() == "delta_refresh"

    def test_priming_pass_does_not_broadcast_preexisting_cases(self):
        async def scenario():
            collection = FakeDiagnosticCasesCollection([_verified_case_doc()])
            source = DeltaPollingCaseEventSource(collection, poll_interval_seconds=0.01, sleep=_no_real_delay)
            gen = source.watch()
            try:
                received = await asyncio.wait_for(gen.__anext__(), timeout=0.2)
            except asyncio.TimeoutError:
                received = None
            assert received is None, "pre-existing verified case must not be replayed as a new event"
            await gen.aclose()

        _run(scenario())

    def test_new_case_after_priming_is_broadcast_as_created(self):
        async def scenario():
            collection = FakeDiagnosticCasesCollection([])
            source = DeltaPollingCaseEventSource(collection, poll_interval_seconds=0.01, sleep=_no_real_delay)
            source._ensure_started()
            await source._primed.wait()
            gen = source.watch()
            collection.documents.append(_verified_case_doc())

            change = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
            assert change.change_kind == CaseChangeKind.CREATED
            assert change.case.case_id == "C1"
            await gen.aclose()

        _run(scenario())

    def test_reverification_is_broadcast_as_updated(self):
        async def scenario():
            collection = FakeDiagnosticCasesCollection([_verified_case_doc()])
            source = DeltaPollingCaseEventSource(collection, poll_interval_seconds=0.01, sleep=_no_real_delay)
            source._ensure_started()
            await source._primed.wait()
            gen = source.watch()
            collection.documents[0]["verified_at"] = "2026-02-01 00:00:00"

            change = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
            assert change.change_kind == CaseChangeKind.UPDATED
            await gen.aclose()

        _run(scenario())

    def test_disconnect_removes_subscriber(self):
        async def scenario():
            collection = FakeDiagnosticCasesCollection([])
            source = DeltaPollingCaseEventSource(collection, poll_interval_seconds=0.01, sleep=_no_real_delay)
            source._ensure_started()
            await source._primed.wait()
            gen = source.watch()
            task = asyncio.ensure_future(gen.__anext__())
            for _ in range(20):
                await asyncio.sleep(0)
                if source._subscribers:
                    break
            assert len(source._subscribers) == 1
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            assert len(source._subscribers) == 0

        _run(scenario())

    def test_current_snapshot_reflects_last_seen_cases(self):
        async def scenario():
            collection = FakeDiagnosticCasesCollection([_verified_case_doc()])
            source = DeltaPollingCaseEventSource(collection, poll_interval_seconds=0.01, sleep=_no_real_delay)
            source._ensure_started()
            await source._primed.wait()
            snapshot = source.current_snapshot()
            assert "C1" in snapshot
            assert snapshot["C1"].verified_at == "2026-01-02 10:00:00"

        _run(scenario())


async def _wait_until_subscribed(collection: FakeWatchableCollection, count: int = 1, attempts: int = 50) -> None:
    """The pump task (`MongoChangeStreamCaseEventSource._pump`) is only
    scheduled, not run, by `_ensure_started()` -- it needs its own turn(s)
    on the event loop before it actually calls `collection.watch(...)` and
    subscribes. A single `asyncio.sleep(0)` is not reliably enough turns
    (the pump's `watch()` call is itself a lazy async generator with its
    own internal subscribe step), so poll in a bounded loop instead of
    guessing a fixed number of yields."""
    for _ in range(attempts):
        if len(collection._subscribers) >= count:
            return
        await asyncio.sleep(0)
    raise AssertionError("pump never subscribed to the fake collection in time")


class TestMongoChangeStreamCaseEventSource:
    def test_describes_transport_as_push(self):
        source = MongoChangeStreamCaseEventSource(FakeWatchableCollection())
        assert source.describe_transport() == "push"

    def test_insert_operation_yields_created(self):
        async def scenario():
            collection = FakeWatchableCollection()
            source = MongoChangeStreamCaseEventSource(collection)
            gen = source.watch()
            task = asyncio.ensure_future(gen.__anext__())
            await _wait_until_subscribed(collection)
            collection.push({"operationType": "insert", "fullDocument": _verified_case_doc()})
            change = await asyncio.wait_for(task, timeout=1.0)
            assert change.change_kind == CaseChangeKind.CREATED
            await gen.aclose()

        _run(scenario())

    def test_update_operation_yields_updated(self):
        async def scenario():
            collection = FakeWatchableCollection()
            source = MongoChangeStreamCaseEventSource(collection)
            gen = source.watch()
            task = asyncio.ensure_future(gen.__anext__())
            await _wait_until_subscribed(collection)
            collection.push({"operationType": "update", "fullDocument": _verified_case_doc()})
            change = await asyncio.wait_for(task, timeout=1.0)
            assert change.change_kind == CaseChangeKind.UPDATED
            await gen.aclose()

        _run(scenario())

    def test_change_with_no_full_document_is_skipped(self):
        async def scenario():
            collection = FakeWatchableCollection()
            source = MongoChangeStreamCaseEventSource(collection)
            gen = source.watch()
            task = asyncio.ensure_future(gen.__anext__())
            await _wait_until_subscribed(collection)
            collection.push({"operationType": "delete"})  # no fullDocument
            collection.push({"operationType": "insert", "fullDocument": _verified_case_doc()})
            change = await asyncio.wait_for(task, timeout=1.0)
            assert change.case.case_id == "C1"  # the delete was skipped, not delivered
            await gen.aclose()

        _run(scenario())

    def test_single_underlying_watch_call_fans_out_to_multiple_subscribers(self):
        async def scenario():
            collection = FakeWatchableCollection()
            source = MongoChangeStreamCaseEventSource(collection)
            gen_a = source.watch()
            gen_b = source.watch()
            task_a = asyncio.ensure_future(gen_a.__anext__())
            task_b = asyncio.ensure_future(gen_b.__anext__())
            await _wait_until_subscribed(collection)
            collection.push({"operationType": "insert", "fullDocument": _verified_case_doc()})
            change_a, change_b = await asyncio.gather(asyncio.wait_for(task_a, 1.0), asyncio.wait_for(task_b, 1.0))
            assert change_a.case.case_id == change_b.case.case_id == "C1"
            assert len(collection.watch_calls) == 1
            await gen_a.aclose()
            await gen_b.aclose()

        _run(scenario())
