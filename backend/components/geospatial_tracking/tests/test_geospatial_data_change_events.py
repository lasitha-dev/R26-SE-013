"""Realtime Geospatial invalidation signals (FICTIONAL in-memory data only).

The delta poller must surface every change that can alter a Geospatial
output -- creation (pending or verified), verification, withdrawal,
disease reclassification, correction and deletion -- as a privacy-safe
`geospatial_data_changed` signal, keep the existing verified-clinical-event
semantics, and expose a dataset version for reconnect reconciliation.
"""

from __future__ import annotations

import asyncio
import json

from components.geospatial_tracking.domain.operational_events import CaseChangeKind, GeospatialDataChangedEvent, RawCaseChange
from components.geospatial_tracking.repositories.mongo_case_event_source import DeltaPollingCaseEventSource

from ._event_fakes import FakeDiagnosticCasesCollection


def _doc(case_id, **kw):
    doc = {"_id": case_id, "farm_id": "F1", "disease_name": "Lumpy Skin Disease", "verified": True,
           "created_at": "2026-10-01 09:00:00", "verified_at": "2026-10-02 10:00:00", "clinical_notes": "FICTIONAL NOTE"}
    doc.update(kw)
    return doc


async def _no_delay(_):
    await asyncio.sleep(0)


async def _primed_source(docs):
    collection = FakeDiagnosticCasesCollection(docs)
    source = DeltaPollingCaseEventSource(collection, poll_interval_seconds=0.01, sleep=_no_delay)
    gen = source.watch()  # subscriber registered eagerly
    await source._primed.wait()
    return collection, source, gen


async def _next_items(gen, n, timeout=1.0):
    items = []
    while len(items) < n:
        items.append(await asyncio.wait_for(gen.__anext__(), timeout=timeout))
    return items


def _data_events(items):
    return [i for i in items if isinstance(i, GeospatialDataChangedEvent)]


def test_every_change_kind_is_signalled_privacy_safely():
    async def scenario():
        collection, source, gen = await _primed_source([_doc("A"), _doc("B", verified=False, verified_at=None)])
        v0 = source.current_data_version()

        collection.documents.append(_doc("C", verified=False, verified_at=None))             # pending report created
        created = _data_events(await _next_items(gen, 2))  # raw CREATED (filtered later) + data event
        assert [e.change for e in created] == ["CREATED"] and created[0].verified is False

        collection.documents[1].update(verified=True, verified_at="2026-10-03 08:00:00")    # B verified
        items = await _next_items(gen, 2)
        assert any(isinstance(i, RawCaseChange) and i.change_kind == CaseChangeKind.CREATED and i.case.case_id == "B" for i in items)
        assert [e.change for e in _data_events(items)] == ["VERIFIED"]

        collection.documents[0]["disease_name"] = "Foot and Mouth Disease"                 # A reclassified
        reclass = _data_events(await _next_items(gen, 2))[0]
        assert (reclass.change, reclass.disease, reclass.previous_disease) == ("RECLASSIFIED", "FMD", "LSD")

        collection.documents[0].update(verified=False)                                    # A verification withdrawn
        assert _data_events(await _next_items(gen, 1))[0].change == "UNVERIFIED"

        collection.documents[1]["farm_id"] = "F2"                                         # B corrected (farm)
        assert [e.change for e in _data_events(await _next_items(gen, 2))] == ["CORRECTED"]

        del collection.documents[2]                                                       # C deleted
        deleted = _data_events(await _next_items(gen, 1))[0]
        assert deleted.change == "DELETED" and deleted.verified is None

        assert source.current_data_version() != v0
        for event in (created[0], reclass, deleted):
            payload = json.dumps(event.as_dict())
            assert event.record_key.startswith("CASE:")
            for secret in ('"A"', '"B"', '"C"', "F1", "F2", "FICTIONAL NOTE"):
                assert secret not in payload
        await gen.aclose()

    asyncio.run(scenario())


def test_unchanged_dataset_emits_nothing_and_version_is_stable():
    async def scenario():
        _collection, source, gen = await _primed_source([_doc("A")])
        version = source.current_data_version()
        try:
            await asyncio.wait_for(gen.__anext__(), timeout=0.2)
            raised = False
        except asyncio.TimeoutError:
            raised = True
        assert raised and source.current_data_version() == version
        await gen.aclose()

    asyncio.run(scenario())


def test_stream_service_forwards_signals_to_every_vet_and_reports_the_version():
    from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext
    from components.geospatial_tracking.repositories.host_operational_adapter import MongoOperationalDataPort
    from components.geospatial_tracking.services.operational.event_stream_service import OperationalEventStreamService

    from ._operational_fakes import FakeCollection, make_vet_document

    async def scenario():
        collection = FakeDiagnosticCasesCollection([_doc("A")])
        source = DeltaPollingCaseEventSource(collection, poll_interval_seconds=0.01, sleep=_no_delay)
        vet_doc = make_vet_document(email="far@example.com", district="Kandy")  # no farms anywhere near F1
        service = OperationalEventStreamService(MongoOperationalDataPort(FakeCollection([vet_doc]), FakeCollection([]), FakeCollection([])), source)
        events = service.stream_events(AuthenticatedVetContext(email="far@example.com", role="vet"))
        task = asyncio.ensure_future(events.__anext__())
        await source._primed.wait()
        assert service.data_version() == source.current_data_version()
        collection.documents.append(_doc("NEW"))
        event = await asyncio.wait_for(task, timeout=1.0)
        assert isinstance(event, GeospatialDataChangedEvent) and event.change == "CREATED"
        assert event.sse_event_name == "geospatial_data_changed"
        await events.aclose()

    asyncio.run(scenario())


def test_ready_version_is_available_before_the_first_event():
    from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext  # noqa: F401
    from components.geospatial_tracking.repositories.host_operational_adapter import MongoOperationalDataPort
    from components.geospatial_tracking.services.operational.event_stream_service import OperationalEventStreamService

    from ._operational_fakes import FakeCollection

    async def scenario():
        source = DeltaPollingCaseEventSource(FakeDiagnosticCasesCollection([_doc("A")]), poll_interval_seconds=0.01, sleep=_no_delay)
        service = OperationalEventStreamService(MongoOperationalDataPort(FakeCollection([]), FakeCollection([]), FakeCollection([])), source)
        version = await service.primed_data_version()
        assert version is not None and version.startswith("ds_") and version == source.current_data_version()

    asyncio.run(scenario())
