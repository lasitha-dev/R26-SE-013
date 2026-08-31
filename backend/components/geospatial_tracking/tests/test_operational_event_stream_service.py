"""GEO-LIVE-05 Section 6/15: `OperationalEventStreamService` tests --
authorization scoping, dedup, and reconnect/missed-event reconciliation.
Fakes only (`_operational_fakes.py`, `_event_fakes.py`), no real Mongo."""

from __future__ import annotations

import asyncio

from components.geospatial_tracking.domain.operational_events import CaseChangeKind, RawCaseChange
from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext, HostDiagnosticCase, HostFarmRecord
from components.geospatial_tracking.services.operational.event_stream_service import OperationalEventStreamService

from ._event_fakes import FakeCaseEventSource
from ._operational_fakes import FakeOperationalDataPort

_VET_A = AuthenticatedVetContext(email="vet-a@example.com", role="vet")
_VET_B = AuthenticatedVetContext(email="vet-b@example.com", role="vet")


def _run(coro):
    return asyncio.run(coro)


def _lsd_case(**overrides) -> HostDiagnosticCase:
    fields = dict(
        case_id="C1", farm_id="F1", disease_name="Lumpy Skin Disease", verified=True,
        created_at="2026-01-01 09:00:00", verified_at="2026-01-02 10:00:00",
    )
    fields.update(overrides)
    return HostDiagnosticCase(**fields)


async def _collect_n(agen, n, timeout=1.0):
    results = []
    for _ in range(n):
        results.append(await asyncio.wait_for(agen.__anext__(), timeout=timeout))
    return results


class TestAuthorizationScoping:
    def test_vet_a_does_not_receive_vet_bs_farm_event(self):
        async def scenario():
            port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F-A", latitude=6.9, longitude=79.8)])
            source = FakeCaseEventSource()
            service = OperationalEventStreamService(port, source)

            stream = service.stream_events(_VET_A)
            task = asyncio.ensure_future(stream.__anext__())
            await asyncio.sleep(0)

            source.push(RawCaseChange(case=_lsd_case(farm_id="F-B"), change_kind=CaseChangeKind.CREATED))
            # Vet A's farm set is only F-A, so the F-B event must never arrive.
            source.push(RawCaseChange(case=_lsd_case(case_id="C-A", farm_id="F-A"), change_kind=CaseChangeKind.CREATED))

            event = await asyncio.wait_for(task, timeout=1.0)
            assert event.case_id == "C-A"
            assert event.farm_id == "F-A"
            await stream.aclose()

        _run(scenario())

    def test_two_vets_each_only_see_their_own_farm(self):
        async def scenario():
            port_a = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F-A", latitude=6.9, longitude=79.8)])
            port_b = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F-B", latitude=6.9, longitude=79.8)])
            source = FakeCaseEventSource()
            service_a = OperationalEventStreamService(port_a, source)
            service_b = OperationalEventStreamService(port_b, source)

            stream_a = service_a.stream_events(_VET_A)
            stream_b = service_b.stream_events(_VET_B)
            task_a = asyncio.ensure_future(stream_a.__anext__())
            task_b = asyncio.ensure_future(stream_b.__anext__())
            await asyncio.sleep(0)

            source.push(RawCaseChange(case=_lsd_case(case_id="CA", farm_id="F-A"), change_kind=CaseChangeKind.CREATED))
            source.push(RawCaseChange(case=_lsd_case(case_id="CB", farm_id="F-B"), change_kind=CaseChangeKind.CREATED))

            event_a = await asyncio.wait_for(task_a, timeout=1.0)
            event_b = await asyncio.wait_for(task_b, timeout=1.0)
            assert event_a.farm_id == "F-A"
            assert event_b.farm_id == "F-B"
            await stream_a.aclose()
            await stream_b.aclose()

        _run(scenario())


class TestDeduplication:
    def test_duplicate_event_id_delivered_once(self):
        async def scenario():
            port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)])
            source = FakeCaseEventSource()
            service = OperationalEventStreamService(port, source)
            stream = service.stream_events(_VET_A)

            change = RawCaseChange(case=_lsd_case(), change_kind=CaseChangeKind.CREATED)
            first_task = asyncio.ensure_future(stream.__anext__())
            await asyncio.sleep(0)
            source.push(change)
            source.push(change)  # exact duplicate -- same case_id + verified_at
            first_event = await asyncio.wait_for(first_task, timeout=1.0)

            # Pushing one genuinely new event proves the stream is still
            # alive and the duplicate above was silently dropped, not
            # queued behind it.
            source.push(RawCaseChange(case=_lsd_case(case_id="C2"), change_kind=CaseChangeKind.CREATED))
            second_event = await asyncio.wait_for(stream.__anext__(), timeout=1.0)

            assert first_event.event_id == "vcc:C1:2026-01-02 10:00:00"
            assert second_event.case_id == "C2"
            await stream.aclose()

        _run(scenario())


class TestReconciliationOnReconnect:
    def test_reconnect_delivers_missed_events_from_source_snapshot(self):
        async def scenario():
            port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)])
            source = FakeCaseEventSource()
            # Simulates a case verified while this vet was disconnected --
            # already in the source's authoritative snapshot before this
            # vet's stream_events() is ever called.
            source.seed_snapshot(_lsd_case(case_id="MISSED-1"))
            service = OperationalEventStreamService(port, source)

            stream = service.stream_events(_VET_A)
            first_event = await asyncio.wait_for(stream.__anext__(), timeout=1.0)
            assert first_event.case_id == "MISSED-1"
            await stream.aclose()

        _run(scenario())

    def test_reconnect_does_not_redeliver_an_already_delivered_event(self):
        async def scenario():
            port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)])
            source = FakeCaseEventSource()
            source.seed_snapshot(_lsd_case(case_id="C1"))
            service = OperationalEventStreamService(port, source)

            # First connection delivers the seeded case.
            stream_one = service.stream_events(_VET_A)
            first_event = await asyncio.wait_for(stream_one.__anext__(), timeout=1.0)
            assert first_event.case_id == "C1"
            await stream_one.aclose()

            # A second connection (simulating reconnect) for the SAME vet,
            # with no new case, must not redeliver C1 -- prove it by
            # pushing a genuinely new case and asserting THAT is what
            # arrives first.
            stream_two = service.stream_events(_VET_A)
            task = asyncio.ensure_future(stream_two.__anext__())
            await asyncio.sleep(0)
            source.push(RawCaseChange(case=_lsd_case(case_id="C2"), change_kind=CaseChangeKind.CREATED))
            next_event = await asyncio.wait_for(task, timeout=1.0)
            assert next_event.case_id == "C2"
            await stream_two.aclose()

        _run(scenario())


class TestFiltering:
    def test_unverified_and_unsupported_disease_never_yielded(self):
        async def scenario():
            port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)])
            source = FakeCaseEventSource()
            service = OperationalEventStreamService(port, source)
            stream = service.stream_events(_VET_A)

            task = asyncio.ensure_future(stream.__anext__())
            await asyncio.sleep(0)
            source.push(RawCaseChange(case=_lsd_case(case_id="UNVERIFIED", verified=False), change_kind=CaseChangeKind.CREATED))
            source.push(RawCaseChange(case=_lsd_case(case_id="MASTITIS", disease_name="Mastitis"), change_kind=CaseChangeKind.CREATED))
            source.push(RawCaseChange(case=_lsd_case(case_id="OK"), change_kind=CaseChangeKind.CREATED))

            event = await asyncio.wait_for(task, timeout=1.0)
            assert event.case_id == "OK"
            await stream.aclose()

        _run(scenario())

    def test_transport_mode_matches_source(self):
        source = FakeCaseEventSource(transport="delta_refresh")
        service = OperationalEventStreamService(FakeOperationalDataPort(), source)
        assert service.transport_mode() == "delta_refresh"


class TestDistrictSurveillanceRelevance:
    """GEO31A Section 4: LIVE_SSE_DISTRICT_SCOPE=PARTIAL -- a genuine event
    for a farm that is in the vet's registered district but NOT personally
    assigned to them must still reach this vet's stream, additively,
    without disturbing assigned-farm relevance."""

    def test_district_only_farm_event_is_relevant(self):
        async def scenario():
            # Vet has ZERO personally-assigned farms (mirrors the real
            # Dr. Thushan / VET-LK-44444 Matara scenario from GEO29A) but a
            # real registered district containing a real farm.
            port = FakeOperationalDataPort(
                farms=[],
                district="Matara",
                district_farms=[HostFarmRecord(farm_id="F-DISTRICT", latitude=5.95, longitude=80.55, location_district="Matara")],
            )
            source = FakeCaseEventSource()
            service = OperationalEventStreamService(port, source)
            stream = service.stream_events(_VET_A)

            task = asyncio.ensure_future(stream.__anext__())
            await asyncio.sleep(0)
            source.push(RawCaseChange(case=_lsd_case(case_id="D1", farm_id="F-DISTRICT"), change_kind=CaseChangeKind.CREATED))

            event = await asyncio.wait_for(task, timeout=1.0)
            assert event.case_id == "D1"
            assert event.farm_id == "F-DISTRICT"
            await stream.aclose()

        _run(scenario())

    def test_assigned_farm_relevance_is_unchanged_alongside_a_real_district(self):
        async def scenario():
            port = FakeOperationalDataPort(
                farms=[HostFarmRecord(farm_id="F-ASSIGNED", latitude=6.9, longitude=79.8)],
                district="Matara",
                district_farms=[HostFarmRecord(farm_id="F-DISTRICT", latitude=5.95, longitude=80.55, location_district="Matara")],
            )
            source = FakeCaseEventSource()
            service = OperationalEventStreamService(port, source)
            stream = service.stream_events(_VET_A)

            task = asyncio.ensure_future(stream.__anext__())
            await asyncio.sleep(0)
            source.push(RawCaseChange(case=_lsd_case(case_id="A1", farm_id="F-ASSIGNED"), change_kind=CaseChangeKind.CREATED))

            event = await asyncio.wait_for(task, timeout=1.0)
            assert event.case_id == "A1"
            assert event.farm_id == "F-ASSIGNED"
            await stream.aclose()

        _run(scenario())

    def test_event_outside_both_assigned_farms_and_district_is_excluded(self):
        async def scenario():
            port = FakeOperationalDataPort(
                farms=[HostFarmRecord(farm_id="F-ASSIGNED", latitude=6.9, longitude=79.8)],
                district="Matara",
                district_farms=[HostFarmRecord(farm_id="F-DISTRICT", latitude=5.95, longitude=80.55, location_district="Matara")],
            )
            source = FakeCaseEventSource()
            service = OperationalEventStreamService(port, source)
            stream = service.stream_events(_VET_A)

            task = asyncio.ensure_future(stream.__anext__())
            await asyncio.sleep(0)
            # Neither assigned nor district-surveillance -- must never arrive.
            source.push(RawCaseChange(case=_lsd_case(case_id="OUTSIDE", farm_id="F-ELSEWHERE"), change_kind=CaseChangeKind.CREATED))
            # The one genuinely relevant event, pushed second, proves the
            # stream is alive and OUTSIDE was silently dropped, not queued.
            source.push(RawCaseChange(case=_lsd_case(case_id="D1", farm_id="F-DISTRICT"), change_kind=CaseChangeKind.CREATED))

            event = await asyncio.wait_for(task, timeout=1.0)
            assert event.case_id == "D1"
            await stream.aclose()

        _run(scenario())

    def test_a_district_resolution_failure_never_breaks_assigned_farm_relevance(self):
        async def scenario():
            port = FakeOperationalDataPort(
                farms=[HostFarmRecord(farm_id="F-ASSIGNED", latitude=6.9, longitude=79.8)],
                raise_on_district=True,
            )
            source = FakeCaseEventSource()
            service = OperationalEventStreamService(port, source)
            stream = service.stream_events(_VET_A)

            task = asyncio.ensure_future(stream.__anext__())
            await asyncio.sleep(0)
            source.push(RawCaseChange(case=_lsd_case(case_id="A1", farm_id="F-ASSIGNED"), change_kind=CaseChangeKind.CREATED))

            event = await asyncio.wait_for(task, timeout=1.0)
            assert event.case_id == "A1"
            await stream.aclose()

        _run(scenario())

    def test_reconciliation_on_reconnect_includes_district_only_farms(self):
        async def scenario():
            port = FakeOperationalDataPort(
                farms=[],
                district="Matara",
                district_farms=[HostFarmRecord(farm_id="F-DISTRICT", latitude=5.95, longitude=80.55, location_district="Matara")],
            )
            source = FakeCaseEventSource()
            source.seed_snapshot(_lsd_case(case_id="MISSED-DISTRICT", farm_id="F-DISTRICT"))
            service = OperationalEventStreamService(port, source)

            stream = service.stream_events(_VET_A)
            first_event = await asyncio.wait_for(stream.__anext__(), timeout=1.0)
            assert first_event.case_id == "MISSED-DISTRICT"
            await stream.aclose()

        _run(scenario())
