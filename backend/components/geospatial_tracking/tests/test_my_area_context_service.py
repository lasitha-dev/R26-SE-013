"""GEO-AREA-01: end-to-end `MyAreaContextService` tests against the
in-memory fakes (`_operational_fakes.py`, `_my_area_fakes.py`). No real
Mongo/SQLite -- mirrors GEO-INT-01/02's testing convention exactly."""

import asyncio

from components.geospatial_tracking.domain.my_area_enums import MyAreaStatus
from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext, HostDiagnosticCase, HostFarmRecord
from components.geospatial_tracking.services.application.frozen_geospatial_analysis_10a import RuntimeAnalysisError10A
from components.geospatial_tracking.services.my_area.context_service import MyAreaContextService

from ._my_area_fakes import FakeScientificReadPort, make_forecast_origin, make_geospatial_snapshot, make_nominal_reach_days, make_source_point
from ._operational_fakes import FakeOperationalDataPort

_VET = AuthenticatedVetContext(email="vet@example.com", role="vet")
_NON_VET = AuthenticatedVetContext(email="farm@example.com", role="farm")


def _run(coro):
    return asyncio.run(coro)


def _one_farm_port(farm_id="F1", **overrides):
    fields = dict(farm_id=farm_id, latitude=6.9271, longitude=79.8612)
    fields.update(overrides)
    return FakeOperationalDataPort(farms=[HostFarmRecord(**fields)])


class TestAuthAndArea:
    # GEO-AREA-01H Section 11: My Area now requires an explicit disease --
    # every test in this class passes "lsd" explicitly so it keeps
    # exercising farm/auth logic rather than the (separately tested)
    # missing-disease gate.

    def test_no_authenticated_context_rejected(self):
        service = MyAreaContextService(FakeOperationalDataPort(), FakeScientificReadPort())
        result = _run(service.get_my_area_context(None, farm_id="F1", disease="lsd"))
        assert result.status == MyAreaStatus.UNAUTHORIZED.value

    def test_non_vet_rejected(self):
        service = MyAreaContextService(FakeOperationalDataPort(), FakeScientificReadPort())
        result = _run(service.get_my_area_context(_NON_VET, farm_id="F1", disease="lsd"))
        assert result.status == MyAreaStatus.NON_VET_FORBIDDEN.value

    def test_one_assigned_farm_accepted(self):
        service = MyAreaContextService(_one_farm_port("F1"), FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.area.farm_id == "F1"

    def test_multiple_assigned_farms_supported(self):
        port = FakeOperationalDataPort(farms=[
            HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8),
            HostFarmRecord(farm_id="F2", latitude=7.0, longitude=80.0),
        ])
        service = MyAreaContextService(port, FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F2", disease="lsd"))
        assert result.area.farm_id == "F2"

    def test_requested_assigned_farm_selected_correctly(self):
        port = FakeOperationalDataPort(farms=[
            HostFarmRecord(farm_id="F1", latitude=6.9, longitude=79.8),
            HostFarmRecord(farm_id="F2", latitude=7.0, longitude=80.0),
        ])
        service = MyAreaContextService(port, FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.area.latitude == 6.9

    def test_another_vets_farm_cannot_be_selected(self):
        # The fake port only ever returns THIS vet's assigned farms
        # (mirrors the real MongoOperationalDataPort's scoping) -- a
        # farm_id belonging to someone else is simply absent from that
        # list, so it resolves the same way as a nonexistent farm.
        port = _one_farm_port("F1")
        service = MyAreaContextService(port, FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="SOMEONE-ELSES-FARM", disease="lsd"))
        assert result.status == MyAreaStatus.ASSIGNED_AREA_NOT_FOUND.value

    def test_unknown_farm_is_a_safe_not_found_never_reveals_existence(self):
        port = _one_farm_port("F1")
        service = MyAreaContextService(port, FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F-GHOST", disease="lsd"))
        assert result.status == MyAreaStatus.ASSIGNED_AREA_NOT_FOUND.value
        assert result.area is None

    def test_missing_latitude_location_required(self):
        port = _one_farm_port("F1", latitude=None)
        service = MyAreaContextService(port, FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.status == MyAreaStatus.LOCATION_REQUIRED.value

    def test_missing_longitude_location_required(self):
        port = _one_farm_port("F1", longitude=None)
        service = MyAreaContextService(port, FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.status == MyAreaStatus.LOCATION_REQUIRED.value

    def test_invalid_coordinate_location_required(self):
        port = _one_farm_port("F1", latitude=999.0)
        service = MyAreaContextService(port, FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.status == MyAreaStatus.LOCATION_REQUIRED.value

    def test_request_cannot_override_stored_farm_coordinate(self):
        # The service signature takes no latitude/longitude parameter at
        # all -- there is structurally no way for a caller to supply one.
        import inspect

        signature = inspect.signature(MyAreaContextService.get_my_area_context)
        assert "latitude" not in signature.parameters
        assert "longitude" not in signature.parameters

    def test_no_assigned_farms_state(self):
        service = MyAreaContextService(FakeOperationalDataPort(farms=[]), FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.status == MyAreaStatus.NO_ASSIGNED_FARMS.value


class TestDiseaseAndOrigins:
    def test_lsd_handled(self):
        service = MyAreaContextService(_one_farm_port("F1"), FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.disease == "LSD"

    def test_fmd_handled_independently(self):
        service = MyAreaContextService(_one_farm_port("F1"), FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="fmd"))
        assert result.disease == "FMD"

    def test_unknown_disease_rejected(self):
        service = MyAreaContextService(_one_farm_port("F1"), FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="rabies"))
        assert result.status == MyAreaStatus.UNSUPPORTED_DISEASE.value

    def test_fmd_model_not_ready_remains_model_not_ready(self):
        origin = make_forecast_origin(forecast_origin_id="ORIGIN:X")
        port = FakeScientificReadPort(
            origins=[origin],
            origin_errors={"ORIGIN:X": RuntimeAnalysisError10A("ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY", "fmd not ready")},
        )
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="fmd", origin_id="ORIGIN:X"))
        assert result.status == MyAreaStatus.ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY.value

    def test_relevant_origins_are_real_existing_origins_only(self):
        origin = make_forecast_origin(forecast_origin_id="ORIGIN:REAL")
        port = FakeScientificReadPort(origins=[origin], trigger_locations_by_origin_id={"ORIGIN:REAL": [("S1", 7.0, 80.0)]})
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert [o.origin_id for o in result.relevant_origins] == ["ORIGIN:REAL"]

    def test_origin_from_wrong_disease_rejected(self):
        # get_origin_analysis is called with the SELECTED disease -- a
        # fake configured to raise ORIGIN_NOT_FOUND for that origin+
        # disease combination models "this origin doesn't exist under
        # this disease's scope".
        port = FakeScientificReadPort(origin_errors={"ORIGIN:LSD-ONLY": RuntimeAnalysisError10A("ORIGIN_NOT_FOUND", "not found for fmd")})
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="fmd", origin_id="ORIGIN:LSD-ONLY"))
        assert result.status == MyAreaStatus.ORIGIN_NOT_FOUND.value

    def test_nonexistent_origin_rejected(self):
        port = FakeScientificReadPort()  # no analyses registered at all
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id="ORIGIN:GHOST"))
        assert result.status == MyAreaStatus.ORIGIN_NOT_FOUND.value

    def test_no_silent_nearest_origin_auto_selection_when_origin_id_absent(self):
        origin = make_forecast_origin(forecast_origin_id="ORIGIN:REAL")
        port = FakeScientificReadPort(origins=[origin], trigger_locations_by_origin_id={"ORIGIN:REAL": [("S1", 7.0, 80.0)]})
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.selected_origin_context is None
        assert port.analysis_calls == []  # get_origin_analysis was never called

    def test_origin_less_response_still_returns_relevant_origin_choices(self):
        origin = make_forecast_origin(forecast_origin_id="ORIGIN:REAL")
        port = FakeScientificReadPort(origins=[origin], trigger_locations_by_origin_id={"ORIGIN:REAL": [("S1", 7.0, 80.0)]})
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.status == MyAreaStatus.OK.value
        assert len(result.relevant_origins) == 1

    def test_no_relevant_origins_state(self):
        port = FakeScientificReadPort(origins=[])
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.status == MyAreaStatus.NO_RELEVANT_ORIGINS.value


class TestSelectedOriginContext:
    def _service_with_snapshot(self, **snapshot_kwargs):
        snapshot = make_geospatial_snapshot(**snapshot_kwargs)
        port = FakeScientificReadPort(
            origins=[make_forecast_origin(forecast_origin_id=snapshot.forecast_origin_id)],
            analyses_by_origin_id={snapshot.forecast_origin_id: snapshot},
        )
        return MyAreaContextService(_one_farm_port("F1"), port), snapshot

    def test_selected_origin_context_built_from_real_summary_sources(self):
        service, snapshot = self._service_with_snapshot(
            eligible_sources=(make_source_point(source_id="S1", latitude=7.0, longitude=80.0),),
            nominal_reach_by_day=make_nominal_reach_days(),
        )
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id=snapshot.forecast_origin_id, forecast_day=1))
        assert result.status == MyAreaStatus.OK.value
        assert result.selected_origin_context.origin_id == snapshot.forecast_origin_id
        assert result.selected_origin_context.nearest_historical_source.source_id == "S1"

    def test_selected_origin_context_carries_the_real_t0(self):
        # GEO-AREA-01H Section 12: t0 must be present so the frontend can
        # derive a D+N date with its own existing utility.
        service, snapshot = self._service_with_snapshot(
            eligible_sources=(make_source_point(),), nominal_reach_by_day=make_nominal_reach_days(),
        )
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id=snapshot.forecast_origin_id, forecast_day=1))
        assert result.selected_origin_context.t0 == snapshot.transport_metadata["t0"]

    def test_forecast_frame_unavailable_when_day_missing_from_real_data(self):
        service, snapshot = self._service_with_snapshot(
            eligible_sources=(make_source_point(),),
            nominal_reach_by_day=make_nominal_reach_days(days=[1, 2]),  # day 3 missing
        )
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id=snapshot.forecast_origin_id, forecast_day=3))
        assert result.status == MyAreaStatus.FORECAST_FRAME_UNAVAILABLE.value


class TestClinicalFirewall:
    def _service_with_cases(self, cases, farm_id="F1"):
        operational_port = FakeOperationalDataPort(
            farms=[HostFarmRecord(farm_id=farm_id, latitude=6.9271, longitude=79.8612)], cases=cases,
        )
        return MyAreaContextService(operational_port, FakeScientificReadPort())

    def _case(self, **overrides):
        fields = dict(
            case_id="C1", farm_id="F1", disease_name="Lumpy Skin Disease", verified=True,
            created_at="2026-01-01 09:00:00", verified_at="2026-01-02 10:00:00",
        )
        fields.update(overrides)
        return HostDiagnosticCase(**fields)

    def test_selected_farms_verified_clinical_context_returned(self):
        service = self._service_with_cases([self._case()])
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert len(result.verified_clinical_contexts) == 1

    def test_unverified_case_excluded(self):
        service = self._service_with_cases([self._case(verified=False)])
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.verified_clinical_contexts == []

    def test_clinical_case_on_another_farm_excluded(self):
        service = self._service_with_cases([self._case(farm_id="F-OTHER")])
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.verified_clinical_contexts == []

    def test_verified_clinical_context_is_never_confirmed_outbreak(self):
        service = self._service_with_cases([self._case()])
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.verified_clinical_contexts[0].semantic_class == "VERIFIED_CLINICAL_CONTEXT"

    def test_verified_at_remains_verification_time(self):
        service = self._service_with_cases([self._case()])
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        ctx = result.verified_clinical_contexts[0]
        assert ctx.timestamp_basis == "VERIFICATION_TIME"
        assert ctx.verification_time == "2026-01-02 10:00:00"

    def test_clinical_context_never_becomes_a_relevant_origin_or_selected_origin_context(self):
        service = self._service_with_cases([self._case()])
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.relevant_origins == []
        assert result.selected_origin_context is None

    def test_disease_scoped_clinical_context_excludes_other_disease(self):
        service = self._service_with_cases([self._case(disease_name="Foot and Mouth Disease")])
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.verified_clinical_contexts == []


class TestNoScientificWrites:
    def test_context_service_constructor_only_accepts_the_two_read_ports(self):
        import inspect

        signature = inspect.signature(MyAreaContextService.__init__)
        param_names = [name for name in signature.parameters if name != "self"]
        assert param_names == ["operational_port", "scientific_port"]


class TestExplicitDiseaseHardening:
    """GEO-AREA-01H Section 11: My Area requires an explicit disease --
    unlike `resolve_disease_selection(None)`, which silently returns LSD
    for the generic /origins and /analysis routes (untouched, still
    tested by their own existing tests), this boundary must never do
    that."""

    def test_none_disease_does_not_silently_become_lsd(self):
        service = MyAreaContextService(_one_farm_port("F1"), FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease=None))
        assert result.status == MyAreaStatus.UNSUPPORTED_DISEASE.value
        assert result.disease is None  # never silently resolved to "LSD"

    def test_blank_disease_does_not_silently_become_lsd(self):
        service = MyAreaContextService(_one_farm_port("F1"), FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="   "))
        assert result.status == MyAreaStatus.UNSUPPORTED_DISEASE.value
        assert result.disease is None

    def test_empty_string_disease_does_not_silently_become_lsd(self):
        service = MyAreaContextService(_one_farm_port("F1"), FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease=""))
        assert result.status == MyAreaStatus.UNSUPPORTED_DISEASE.value

    def test_missing_disease_check_happens_before_any_farm_lookup(self):
        # Proves the guard is unconditional -- even a vet with zero
        # assigned farms gets UNSUPPORTED_DISEASE, not NO_ASSIGNED_FARMS,
        # when disease is missing (disease is validated first).
        service = MyAreaContextService(FakeOperationalDataPort(farms=[]), FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease=None))
        assert result.status == MyAreaStatus.UNSUPPORTED_DISEASE.value

    def test_explicit_lsd_still_accepted(self):
        service = MyAreaContextService(_one_farm_port("F1"), FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.disease == "LSD"

    def test_explicit_fmd_still_accepted_independently(self):
        service = MyAreaContextService(_one_farm_port("F1"), FakeScientificReadPort())
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="fmd"))
        assert result.disease == "FMD"


class TestDistanceSemantics:
    """GEO-AREA-01H Section 2/5/9/14: distance-field correctness."""

    def test_forecast_origin_has_no_coordinate_and_none_is_invented(self):
        origin = make_forecast_origin(forecast_origin_id="O1")
        assert not hasattr(origin, "latitude")
        assert not hasattr(origin, "longitude")

    def test_selected_origin_context_no_longer_carries_an_ambiguous_origin_distance_field(self):
        snapshot = make_geospatial_snapshot(
            eligible_sources=(make_source_point(source_id="S1", latitude=7.0, longitude=80.0),),
            nominal_reach_by_day=make_nominal_reach_days(),
        )
        port = FakeScientificReadPort(
            origins=[make_forecast_origin(forecast_origin_id=snapshot.forecast_origin_id)],
            analyses_by_origin_id={snapshot.forecast_origin_id: snapshot},
        )
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id=snapshot.forecast_origin_id, forecast_day=1))
        field_names = set(result.selected_origin_context.__dataclass_fields__)
        assert "distance_to_origin_km" not in field_names

    def test_nearest_historical_source_remains_its_own_separate_concept(self):
        snapshot = make_geospatial_snapshot(
            eligible_sources=(make_source_point(source_id="S1", latitude=7.0, longitude=80.0),),
            nominal_reach_by_day=make_nominal_reach_days(),
        )
        port = FakeScientificReadPort(
            origins=[make_forecast_origin(forecast_origin_id=snapshot.forecast_origin_id)],
            analyses_by_origin_id={snapshot.forecast_origin_id: snapshot},
        )
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id=snapshot.forecast_origin_id, forecast_day=1))
        # The nearest-source distance is still real and present, but only
        # ever surfaced under its own name -- never duplicated into the
        # nominal-reach context (which carries no distance field at all).
        assert result.selected_origin_context.nearest_historical_source.distance_from_area_km is not None
        assert not hasattr(result.selected_origin_context.nominal_reach_context, "distance_area_to_origin_km")

    def test_eligible_source_distance_never_silently_reused_as_relevant_origin_distance(self):
        # Relevant-origin ranking must use trigger-source locations, NOT
        # a selected origin's eligible sources (a different set/concept).
        origin = make_forecast_origin(forecast_origin_id="O1")
        port = FakeScientificReadPort(origins=[origin], trigger_locations_by_origin_id={"O1": [("TRIGGER-1", 7.0, 80.0)]})
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert port.list_origins_calls  # list_origins was used, not get_origin_analysis
        assert result.relevant_origins[0].distance_basis == "NEAREST_T0_TRIGGER_SOURCE"

    def test_relevant_origin_distance_basis_present_and_self_describing(self):
        origin = make_forecast_origin(forecast_origin_id="O1")
        port = FakeScientificReadPort(origins=[origin], trigger_locations_by_origin_id={"O1": [("S1", 7.0, 80.0)]})
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.relevant_origins[0].distance_basis == "NEAREST_T0_TRIGGER_SOURCE"

    def test_source_with_missing_gps_never_becomes_a_trigger_anchor(self):
        # get_origin_trigger_locations (the real port) already excludes
        # sources with no coordinate -- an origin whose ONLY trigger
        # source lacks GPS must be excluded from relevant_origins.
        origin = make_forecast_origin(forecast_origin_id="O1")
        port = FakeScientificReadPort(origins=[origin], trigger_locations_by_origin_id={"O1": []})
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.relevant_origins == []

    def test_no_fabricated_origin_centroid_anywhere_in_the_response(self):
        snapshot = make_geospatial_snapshot(eligible_sources=(), nominal_reach_by_day=make_nominal_reach_days())
        port = FakeScientificReadPort(
            origins=[make_forecast_origin(forecast_origin_id=snapshot.forecast_origin_id)],
            analyses_by_origin_id={snapshot.forecast_origin_id: snapshot},
        )
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id=snapshot.forecast_origin_id, forecast_day=1))
        # No eligible sources at all -- nearest_historical_source must be
        # None, never a guessed/fabricated stand-in coordinate.
        assert result.selected_origin_context.nearest_historical_source is None
