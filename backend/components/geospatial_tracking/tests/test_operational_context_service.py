"""GEO-INT-01 Section 17/19/20/21: end-to-end `OperationalContextService`
behavior against the in-memory fake port (`_operational_fakes.py`).

GEO-INT-02 note: `get_operational_context` is `async` (see
`context_service.py` module docstring) — every call below runs through
`_run()` (`asyncio.run`) rather than depending on a pytest-asyncio/anyio
test-collection plugin, so this file needs no `pytest.ini` change (out of
GEO-INT-02's write scope)."""

import asyncio

from components.geospatial_tracking.domain.operational_enums import OperationalStatus
from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext, HostDiagnosticCase, HostFarmRecord
from components.geospatial_tracking.services.operational.context_service import OperationalContextService

from ._operational_fakes import FakeOperationalDataPort

_VET = AuthenticatedVetContext(email="vet@example.com", role="vet")
_NON_VET = AuthenticatedVetContext(email="farm@example.com", role="farm")


def _run(coro):
    return asyncio.run(coro)


class TestAuthorization:
    def test_no_vet_context_is_unauthorized(self):
        service = OperationalContextService(FakeOperationalDataPort())
        result = _run(service.get_operational_context(None))
        assert result.status == OperationalStatus.UNAUTHORIZED.value
        assert result.farms == []
        assert result.clinical_contexts == []

    def test_non_vet_role_is_forbidden(self):
        port = FakeOperationalDataPort()
        service = OperationalContextService(port)
        result = _run(service.get_operational_context(_NON_VET))
        assert result.status == OperationalStatus.NON_VET_FORBIDDEN.value
        assert result.farms == []
        # non-vet rejection must not even query the host data source:
        assert port.farms_calls == []
        assert port.cases_calls == []


class TestAssignedFarms:
    def test_no_assigned_farms(self):
        service = OperationalContextService(FakeOperationalDataPort(farms=[]))
        result = _run(service.get_operational_context(_VET))
        assert result.status == OperationalStatus.NO_ASSIGNED_FARMS.value

    def test_one_assigned_geolocated_farm(self):
        port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)])
        result = _run(OperationalContextService(port).get_operational_context(_VET))
        assert len(result.farms) == 1
        assert result.farms[0].farm_id == "F1"

    def test_multiple_assigned_farms(self):
        port = FakeOperationalDataPort(
            farms=[
                HostFarmRecord(farm_id="F3", latitude=7.0, longitude=80.0),
                HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8),
                HostFarmRecord(farm_id="F2", latitude=None, longitude=None),
            ]
        )
        result = _run(OperationalContextService(port).get_operational_context(_VET))
        assert [f.farm_id for f in result.farms] == ["F1", "F2", "F3"]  # Section 20 deterministic ordering


class TestVerifiedClinicalContextAssembly:
    def _farms(self):
        return [HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)]

    def test_no_verified_clinical_context(self):
        port = FakeOperationalDataPort(farms=self._farms(), cases=[])
        result = _run(OperationalContextService(port).get_operational_context(_VET))
        assert result.status == OperationalStatus.NO_VERIFIED_CLINICAL_CONTEXT.value

    def test_qualifying_case_produces_ok_status(self):
        port = FakeOperationalDataPort(
            farms=self._farms(),
            cases=[
                HostDiagnosticCase(
                    case_id="C1",
                    farm_id="F1",
                    disease_name="Lumpy Skin Disease",
                    verified=True,
                    created_at="2026-01-01 09:00:00",
                    verified_at="2026-01-02 10:00:00",
                )
            ],
        )
        result = _run(OperationalContextService(port).get_operational_context(_VET))
        assert result.status == OperationalStatus.OK.value
        assert len(result.clinical_contexts) == 1

    def test_deterministic_case_ordering(self):
        cases = [
            HostDiagnosticCase(
                case_id=cid, farm_id="F1", disease_name="Lumpy Skin Disease", verified=True,
                created_at="2026-01-01 09:00:00", verified_at="2026-01-02 10:00:00",
            )
            for cid in ["C3", "C1", "C2"]
        ]
        port = FakeOperationalDataPort(farms=self._farms(), cases=cases)
        result = _run(OperationalContextService(port).get_operational_context(_VET))
        assert [c.case_id for c in result.clinical_contexts] == ["C1", "C2", "C3"]


class TestUpstreamUnavailable:
    def test_farms_source_unavailable_handled_cleanly(self):
        port = FakeOperationalDataPort(raise_on_farms=True)
        result = _run(OperationalContextService(port).get_operational_context(_VET))
        assert result.status == OperationalStatus.OPERATIONAL_DATA_UNAVAILABLE.value
        assert result.farms == []

    def test_cases_source_unavailable_handled_cleanly(self):
        port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)], raise_on_cases=True)
        result = _run(OperationalContextService(port).get_operational_context(_VET))
        assert result.status == OperationalStatus.OPERATIONAL_DATA_UNAVAILABLE.value
        assert len(result.farms) == 1  # already-fetched farms are not discarded


class TestMinimalPii:
    def test_top_level_dto_carries_no_email(self):
        port = FakeOperationalDataPort(farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)])
        result = _run(OperationalContextService(port).get_operational_context(_VET))
        assert result.vet.role == "vet"
        assert not hasattr(result.vet, "email")
        assert "email" not in set(result.vet.__dataclass_fields__)


class TestCaseReconciliation:
    """GEO-OWNED-FINAL-08 Section 1/2/3: `OperationalContextService` is a
    stateless snapshot builder -- every call re-derives `clinical_contexts`
    and `farms` from whatever `OperationalDataPort` returns THAT call, never
    from a cached/merged prior result. These tests lock exactly the
    reconciliation scenarios GEO-OWNED-FINAL-08 calls out (verified case
    updated, disease changed, verified flipped false, farm_id changed, case
    deleted upstream, farm GPS changed) by calling `get_operational_context`
    TWICE against the SAME port instance with different data configured
    between calls -- proving the second call reflects the new authoritative
    state rather than anything remembered from the first, with no special
    "diff"/"patch" logic anywhere in this service."""

    _FARM_F1 = HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)
    _FARM_F2 = HostFarmRecord(farm_id="F2", latitude=7.2, longitude=80.6)

    def _case(self, **overrides):
        base = dict(
            case_id="C1",
            farm_id="F1",
            disease_name="Lumpy Skin Disease",
            verified=True,
            created_at="2026-01-01 09:00:00",
            verified_at="2026-01-02 10:00:00",
        )
        base.update(overrides)
        return HostDiagnosticCase(**base)

    def test_disease_change_lsd_to_fmd_is_reflected_on_next_call(self):
        port = FakeOperationalDataPort(farms=[self._FARM_F1], cases=[self._case(disease_name="Lumpy Skin Disease")])
        service = OperationalContextService(port)
        first = _run(service.get_operational_context(_VET))
        assert first.clinical_contexts[0].disease == "LSD"

        port._cases = [self._case(disease_name="Foot and Mouth Disease", verified_at="2026-01-03 08:00:00")]
        second = _run(service.get_operational_context(_VET))
        assert len(second.clinical_contexts) == 1
        assert second.clinical_contexts[0].disease == "FMD"

    def test_disease_change_fmd_to_lsd_is_reflected_on_next_call(self):
        port = FakeOperationalDataPort(farms=[self._FARM_F1], cases=[self._case(disease_name="Foot and Mouth Disease")])
        service = OperationalContextService(port)
        assert _run(service.get_operational_context(_VET)).clinical_contexts[0].disease == "FMD"

        port._cases = [self._case(disease_name="Lumpy Skin Disease", verified_at="2026-01-03 08:00:00")]
        second = _run(service.get_operational_context(_VET))
        assert second.clinical_contexts[0].disease == "LSD"

    def test_disease_becomes_unsupported_excludes_case_on_next_call(self):
        port = FakeOperationalDataPort(farms=[self._FARM_F1], cases=[self._case()])
        service = OperationalContextService(port)
        assert len(_run(service.get_operational_context(_VET)).clinical_contexts) == 1

        # A corrected/edited case whose disease is no longer LSD/FMD (e.g.
        # re-diagnosed healthy) must disappear, never silently keep its
        # last-known disease label.
        port._cases = [self._case(disease_name="Cattle (Healthy)")]
        second = _run(service.get_operational_context(_VET))
        assert second.clinical_contexts == []
        assert second.status == OperationalStatus.NO_VERIFIED_CLINICAL_CONTEXT.value

    def test_verified_becomes_false_excludes_case_on_next_call(self):
        port = FakeOperationalDataPort(farms=[self._FARM_F1], cases=[self._case(verified=True)])
        service = OperationalContextService(port)
        assert len(_run(service.get_operational_context(_VET)).clinical_contexts) == 1

        port._cases = [self._case(verified=False, verified_at=None)]
        second = _run(service.get_operational_context(_VET))
        assert second.clinical_contexts == []

    def test_reverification_updates_verification_time_on_next_call(self):
        port = FakeOperationalDataPort(farms=[self._FARM_F1], cases=[self._case(verified_at="2026-01-02 10:00:00")])
        service = OperationalContextService(port)
        first = _run(service.get_operational_context(_VET))
        assert first.clinical_contexts[0].verification_time == "2026-01-02 10:00:00"

        port._cases = [self._case(verified_at="2026-02-15 14:30:00")]
        second = _run(service.get_operational_context(_VET))
        assert len(second.clinical_contexts) == 1
        assert second.clinical_contexts[0].verification_time == "2026-02-15 14:30:00"

    def test_farm_reassignment_to_a_still_assigned_farm_is_reflected(self):
        port = FakeOperationalDataPort(farms=[self._FARM_F1, self._FARM_F2], cases=[self._case(farm_id="F1")])
        service = OperationalContextService(port)
        assert _run(service.get_operational_context(_VET)).clinical_contexts[0].farm_id == "F1"

        port._cases = [self._case(farm_id="F2", verified_at="2026-01-03 08:00:00")]
        second = _run(service.get_operational_context(_VET))
        assert len(second.clinical_contexts) == 1
        assert second.clinical_contexts[0].farm_id == "F2"

    def test_farm_reassignment_to_an_unassigned_farm_excludes_the_case(self):
        # Section 3/5: the case's new farm_id is not one of THIS vet's
        # assigned farms -- it must be excluded, never shown under the
        # vet's old (no-longer-current) farm_id either.
        port = FakeOperationalDataPort(farms=[self._FARM_F1], cases=[self._case(farm_id="F1")])
        service = OperationalContextService(port)
        assert len(_run(service.get_operational_context(_VET)).clinical_contexts) == 1

        port._cases = [self._case(farm_id="F-not-assigned", verified_at="2026-01-03 08:00:00")]
        second = _run(service.get_operational_context(_VET))
        assert second.clinical_contexts == []

    def test_case_deleted_upstream_disappears_on_next_call(self):
        # GEO-OWNED-FINAL-08 Section 2: the host hard-deletes cases with no
        # tombstone. This service never remembers a case it previously
        # saw -- a case absent from THIS call's port result is simply
        # absent from the snapshot, with no fabricated "deleted" marker.
        port = FakeOperationalDataPort(farms=[self._FARM_F1], cases=[self._case()])
        service = OperationalContextService(port)
        assert len(_run(service.get_operational_context(_VET)).clinical_contexts) == 1

        port._cases = []
        second = _run(service.get_operational_context(_VET))
        assert second.clinical_contexts == []
        assert second.status == OperationalStatus.NO_VERIFIED_CLINICAL_CONTEXT.value

    def test_farm_gps_change_is_reflected_fresh_never_cached_stale(self):
        # GPS lives on the DTO's `farms` list (`OperationalFarm`), not on
        # `VerifiedClinicalContext` itself -- the frontend adapter joins a
        # clinical context to its farm's coordinate by `farm_id` (Section
        # 3). This proves the SERVICE side of that freshness guarantee:
        # `get_assigned_farms` is re-awaited on every call, never cached
        # from the first response.
        port = FakeOperationalDataPort(
            farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)],
            cases=[self._case()],
        )
        service = OperationalContextService(port)
        first = _run(service.get_operational_context(_VET))
        assert (first.farms[0].latitude, first.farms[0].longitude) == (6.9, 79.8)
        assert len(first.clinical_contexts) == 1

        port._farms = [HostFarmRecord(farm_id="F1", latitude=7.5, longitude=81.0)]
        second = _run(service.get_operational_context(_VET))
        assert (second.farms[0].latitude, second.farms[0].longitude) == (7.5, 81.0)
        assert len(second.clinical_contexts) == 1

    def test_farm_gps_becoming_invalid_makes_case_location_unavailable(self):
        port = FakeOperationalDataPort(
            farms=[HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8)],
            cases=[self._case()],
        )
        service = OperationalContextService(port)
        assert len(_run(service.get_operational_context(_VET)).clinical_contexts) == 1

        # GPS removed upstream (never inferred from district) -- the farm
        # itself still appears (Section 3 "missing GPS means operational
        # location unavailable", never a dropped farm), but the case can no
        # longer qualify as a VerifiedClinicalContext.
        port._farms = [HostFarmRecord(farm_id="F1", latitude=None, longitude=None)]
        second = _run(service.get_operational_context(_VET))
        assert len(second.farms) == 1
        assert second.clinical_contexts == []

    def test_same_case_re_observed_across_calls_never_duplicates(self):
        # Section 1 "same case re-reported/upserted": the upstream write
        # path re-uses the same _id on an existing-cattle case (an
        # `update_one`, never a second `insert_one` -- Mongo `_id`
        # uniqueness already guarantees a `find()` never returns the same
        # document twice in one call). What this service must get right is
        # the OTHER half: re-observing the identical case across repeated
        # calls (e.g. two successive polls before anything changed) must
        # keep producing exactly one context each time, never accumulating.
        port = FakeOperationalDataPort(farms=[self._FARM_F1], cases=[self._case()])
        service = OperationalContextService(port)
        first = _run(service.get_operational_context(_VET))
        second = _run(service.get_operational_context(_VET))
        assert len(first.clinical_contexts) == 1
        assert len(second.clinical_contexts) == 1
        assert first.clinical_contexts[0].case_id == second.clinical_contexts[0].case_id
