"""GEO-AREA-01S Sections 16-19: My Area Sri Lanka study-scope hardening
tests.

Two layers of proof, mirroring GEO-ANALYSIS-01H's own approach:

  1. Unit-level (fakes): `MyAreaContextService` always passes
     `country=GEOSPATIAL_STUDY_COUNTRY` ("Sri Lanka") to `list_origins`
     in BOTH the relevant-origins listing path and the selected-origin
     path, and the selected-origin firewall rejects any `origin_id` not
     present in the already-loaded, country-scoped ledger -- by real set
     membership, never a string-prefix parse.
  2. Integration-level (a real, ephemeral, tmp_path-backed
     `SQLiteOutbreakRepository`): a genuine end-to-end proof that a Sri
     Lanka forecast origin is included and Afghanistan/India origins are
     excluded from `relevant_origins`, exercising the REAL
     `build_forecast_origin_ledger` function, never mocked out.
"""

from __future__ import annotations

import pytest

from components.geospatial_tracking.domain.my_area_enums import GEOSPATIAL_STUDY_COUNTRY, MyAreaStatus
from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext, HostFarmRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.application.frozen_geospatial_analysis_10a import RuntimeAnalysisError10A
from components.geospatial_tracking.services.forecast_origin import build_forecast_origin_ledger
from components.geospatial_tracking.services.my_area.context_service import MyAreaContextService

from ._my_area_fakes import FakeScientificReadPort, make_forecast_origin, make_geospatial_snapshot, make_nominal_reach_days
from ._operational_fakes import FakeOperationalDataPort

_VET = AuthenticatedVetContext(email="vet@example.com", role="vet")


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def _one_farm_port(farm_id="F1", latitude=6.9271, longitude=79.8612):
    return FakeOperationalDataPort(farms=[HostFarmRecord(farm_id=farm_id, latitude=latitude, longitude=longitude)])


# ---------------------------------------------------------------------------
# Unit-level: fakes prove the service ALWAYS requests Sri Lanka.
# ---------------------------------------------------------------------------


class TestServiceAlwaysRequestsSriLanka:
    def test_relevant_origins_path_requests_list_origins_with_sri_lanka_country(self):
        port = FakeScientificReadPort(origins=[make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07")])
        service = MyAreaContextService(_one_farm_port("F1"), port)
        _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert port.list_origins_calls == [{"disease": "Lumpy skin disease", "country": "Sri Lanka"}]

    def test_selected_origin_path_also_requests_list_origins_with_sri_lanka_country(self):
        snapshot = make_geospatial_snapshot(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07")
        port = FakeScientificReadPort(
            origins=[make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07")],
            analyses_by_origin_id={"ORIGIN:Sri Lanka:2020-09-07": snapshot},
        )
        service = MyAreaContextService(_one_farm_port("F1"), port)
        _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id="ORIGIN:Sri Lanka:2020-09-07"))
        assert port.list_origins_calls == [{"disease": "Lumpy skin disease", "country": "Sri Lanka"}]

    def test_never_requests_country_none(self):
        port = FakeScientificReadPort(origins=[make_forecast_origin()])
        service = MyAreaContextService(_one_farm_port("F1"), port)
        _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert port.list_origins_calls[0]["country"] is not None
        assert port.list_origins_calls[0]["country"] == GEOSPATIAL_STUDY_COUNTRY

    def test_fmd_relevant_origins_also_requested_with_sri_lanka_country(self):
        port = FakeScientificReadPort(origins=[])
        service = MyAreaContextService(_one_farm_port("F1"), port)
        _run(service.get_my_area_context(_VET, farm_id="F1", disease="fmd"))
        assert port.list_origins_calls == [{"disease": "Foot and mouth disease", "country": "Sri Lanka"}]


class TestSelectedOriginCountryFirewall:
    def test_real_sri_lanka_origin_accepted(self):
        snapshot = make_geospatial_snapshot(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07")
        port = FakeScientificReadPort(
            origins=[make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07")],
            analyses_by_origin_id={"ORIGIN:Sri Lanka:2020-09-07": snapshot},
        )
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id="ORIGIN:Sri Lanka:2020-09-07"))
        assert result.status == MyAreaStatus.OK.value
        assert result.selected_origin_context is not None

    def test_real_foreign_country_origin_rejected_as_origin_not_found(self):
        # The ledger the service actually loaded is Sri-Lanka-scoped
        # (only a Sri Lanka origin is present) -- a real Afghanistan
        # origin id simply never appears in it.
        port = FakeScientificReadPort(origins=[make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07")])
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id="ORIGIN:Afghanistan:2022-05-29"))
        assert result.status == MyAreaStatus.ORIGIN_NOT_FOUND.value

    def test_foreign_origin_never_calls_get_origin_analysis(self):
        port = FakeScientificReadPort(origins=[make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07")])
        service = MyAreaContextService(_one_farm_port("F1"), port)
        _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id="ORIGIN:Afghanistan:2022-05-29"))
        assert port.analysis_calls == []

    def test_real_india_origin_also_rejected(self):
        port = FakeScientificReadPort(origins=[make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07")])
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id="ORIGIN:India:2021-03-10"))
        assert result.status == MyAreaStatus.ORIGIN_NOT_FOUND.value

    def test_no_origin_id_performs_no_selected_origin_scientific_analysis(self):
        port = FakeScientificReadPort(origins=[make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07")])
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id=None))
        assert result.selected_origin_context is None
        assert port.analysis_calls == []

    def test_firewall_uses_real_ledger_membership_not_string_prefix_parsing(self):
        # A fake id that LOOKS like a Sri Lanka id by string convention
        # but was never actually returned by list_origins must still be
        # rejected -- proves this is a set-membership check against the
        # real loaded ledger, never `origin_id.startswith("ORIGIN:Sri Lanka:")`.
        port = FakeScientificReadPort(origins=[make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07")])
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id="ORIGIN:Sri Lanka:1899-01-01"))
        assert result.status == MyAreaStatus.ORIGIN_NOT_FOUND.value
        assert port.analysis_calls == []

    def test_ledger_origin_with_unconventional_id_shape_is_still_accepted(self):
        weird_id = "not-a-conventional-origin-id-at-all"
        snapshot = make_geospatial_snapshot(forecast_origin_id=weird_id)
        port = FakeScientificReadPort(
            origins=[make_forecast_origin(forecast_origin_id=weird_id)],
            analyses_by_origin_id={weird_id: snapshot},
        )
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id=weird_id))
        assert result.status == MyAreaStatus.OK.value
        assert result.selected_origin_context is not None

    def test_wrong_disease_origin_rejected(self):
        # An origin real for LSD's Sri-Lanka-scoped ledger is not
        # present in a request scoped to FMD's own (different) ledger.
        port = FakeScientificReadPort(origins=[])  # FMD ledger empty in this fake
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="fmd", origin_id="ORIGIN:Sri Lanka:2020-09-07"))
        assert result.status == MyAreaStatus.ORIGIN_NOT_FOUND.value

    def test_nonexistent_origin_rejected(self):
        port = FakeScientificReadPort(origins=[make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07")])
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id="ORIGIN:GHOST:1999-01-01"))
        assert result.status == MyAreaStatus.ORIGIN_NOT_FOUND.value


class TestRelevantOriginFilteringOrderAndTruncation:
    def test_foreign_origins_never_affect_relevant_origin_sort_order(self):
        # Ranking is computed only over the (already country-scoped)
        # `origins` list the fake returns -- there is no foreign origin
        # in it for the ranking function to ever see.
        sl_near = make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07", t0="2020-09-07")
        sl_far = make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-10-28", t0="2020-10-28")
        port = FakeScientificReadPort(
            origins=[sl_near, sl_far],
            trigger_locations_by_origin_id={
                "ORIGIN:Sri Lanka:2020-09-07": [("S1", 6.93, 79.85)],  # very close to the farm
                "ORIGIN:Sri Lanka:2020-10-28": [("S2", 9.0, 82.0)],  # far
            },
        )
        service = MyAreaContextService(_one_farm_port("F1", latitude=6.9271, longitude=79.8612), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert [o.origin_id for o in result.relevant_origins] == ["ORIGIN:Sri Lanka:2020-09-07", "ORIGIN:Sri Lanka:2020-10-28"]

    def test_top_n_truncation_only_ever_sees_scoped_origins(self):
        origins = [make_forecast_origin(forecast_origin_id=f"ORIGIN:Sri Lanka:2020-0{i}-01", t0=f"2020-0{i}-01") for i in range(1, 8)]
        locations = {o.forecast_origin_id: [("S", 6.9271 + i * 0.01, 79.8612)] for i, o in enumerate(origins, start=1)}
        port = FakeScientificReadPort(origins=origins, trigger_locations_by_origin_id=locations)
        service = MyAreaContextService(_one_farm_port("F1", latitude=6.9271, longitude=79.8612), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert len(result.relevant_origins) == 5  # rank_relevant_origins' own limit=5, unaffected by scope filtering

    def test_distance_calculation_only_run_for_allowed_sri_lanka_origins(self):
        # get_origin_trigger_locations is only ever called for origins
        # actually present in the (already Sri-Lanka-scoped) list --
        # never for a foreign one, because none is ever in that list.
        sl_origin = make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07")
        port = FakeScientificReadPort(origins=[sl_origin], trigger_locations_by_origin_id={"ORIGIN:Sri Lanka:2020-09-07": [("S1", 6.93, 79.85)]})
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert len(result.relevant_origins) == 1
        assert result.relevant_origins[0].origin_id == "ORIGIN:Sri Lanka:2020-09-07"


class TestRegressionSemanticsUnchanged:
    """GEO-AREA-01S Section 18: proves the country-scope firewall did not
    disturb farm authorization, distance semantics, nominal reach,
    Relative Spatial Score, or FMD readiness behavior."""

    def test_another_vets_farm_still_rejected(self):
        port = FakeScientificReadPort(origins=[])
        service = MyAreaContextService(_one_farm_port("F-MINE"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F-NOT-MINE", disease="lsd"))
        assert result.status == MyAreaStatus.ASSIGNED_AREA_NOT_FOUND.value

    def test_stored_gps_remains_authoritative_no_request_coordinate_accepted(self):
        import inspect

        from components.geospatial_tracking.services.my_area import context_service

        signature = inspect.signature(context_service.MyAreaContextService.get_my_area_context)
        assert "latitude" not in signature.parameters
        assert "longitude" not in signature.parameters

    def test_relevant_origin_distance_basis_still_nearest_t0_trigger_source(self):
        origin = make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07")
        port = FakeScientificReadPort(origins=[origin], trigger_locations_by_origin_id={"ORIGIN:Sri Lanka:2020-09-07": [("S1", 6.93, 79.85)]})
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))
        assert result.relevant_origins[0].distance_basis == "NEAREST_T0_TRIGGER_SOURCE"

    def test_nominal_reach_relation_still_not_applicable(self):
        snapshot = make_geospatial_snapshot(forecast_origin_id="O1", nominal_reach_by_day=make_nominal_reach_days())
        port = FakeScientificReadPort(origins=[make_forecast_origin(forecast_origin_id="O1")], analyses_by_origin_id={"O1": snapshot})
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id="O1", forecast_day=1))
        assert result.selected_origin_context.nominal_reach_context.relation == "NOT_APPLICABLE"
        assert result.selected_origin_context.nominal_reach_context.anchor_basis == "NO_SCIENTIFICALLY_DEFINED_REACH_ANCHOR"

    def test_relative_spatial_score_still_unavailable(self):
        snapshot = make_geospatial_snapshot(forecast_origin_id="O1", nominal_reach_by_day=make_nominal_reach_days())
        port = FakeScientificReadPort(origins=[make_forecast_origin(forecast_origin_id="O1")], analyses_by_origin_id={"O1": snapshot})
        service = MyAreaContextService(_one_farm_port("F1"), port)
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id="O1", forecast_day=1))
        assert result.selected_origin_context.relative_spatial_score.value is None
        assert result.selected_origin_context.relative_spatial_score.status == "SCORE_UNAVAILABLE_CELL_GEOMETRY_NOT_EXPOSED_FOR_CONTAINMENT"

    def test_fmd_real_relevant_origin_may_list_but_selecting_it_stays_model_not_ready(self):
        fmd_origin = make_forecast_origin(forecast_origin_id="ORIGIN:Sri Lanka:2009-09-09", t0="2009-09-09")
        port = FakeScientificReadPort(
            origins=[fmd_origin], trigger_locations_by_origin_id={"ORIGIN:Sri Lanka:2009-09-09": [("S1", 6.93, 79.85)]},
        )
        service = MyAreaContextService(_one_farm_port("F1"), port)
        listing = _run(service.get_my_area_context(_VET, farm_id="F1", disease="fmd"))
        assert len(listing.relevant_origins) == 1  # real historical FMD origin listed

        port2 = FakeScientificReadPort(origins=[fmd_origin], origin_errors={
            "ORIGIN:Sri Lanka:2009-09-09": RuntimeAnalysisError10A("ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY", "fmd not ready"),
        })
        service2 = MyAreaContextService(_one_farm_port("F1"), port2)
        selected = _run(service2.get_my_area_context(_VET, farm_id="F1", disease="fmd", origin_id="ORIGIN:Sri Lanka:2009-09-09"))
        assert selected.status == MyAreaStatus.ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY.value


# ---------------------------------------------------------------------------
# Integration-level: a REAL, ephemeral SQLite repository -- proves actual
# country filtering, not merely that the right kwarg was passed.
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    r = SQLiteOutbreakRepository(tmp_path / "test.db")
    r.init_schema()
    yield r
    r.close()


def _historical(**overrides) -> HistoricalOutbreakRecord:
    fields = dict(
        source_record_id="H1", country="Sri Lanka", disease="Lumpy skin disease",
        outbreak_start_date="2020-09-07", proxy_availability_date="2020-09-07",
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        latitude=7.0, longitude=80.0, gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value, model_candidate=True,
    )
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


class _RealPortOverRepo:
    """Mirrors GEO-ANALYSIS-01H's own integration-test adapter -- a
    minimal `ScientificReadPort`-shaped wrapper exercising the REAL
    `build_forecast_origin_ledger` function directly, never mocked out.

    `MyAreaContextService` is `async def` and dispatches every scientific
    read through `fastapi.concurrency.run_in_threadpool`, which may run
    on a different OS thread than the one that opened the ephemeral
    SQLite connection -- raw `sqlite3` connections are not safe to share
    across threads (`SQLiteOutbreakRepository`'s own docstring says so).
    This adapter therefore opens a FRESH `SQLiteOutbreakRepository`
    per call and closes it immediately after, exactly mirroring the real
    production `managed_repository_10b()` open/close-per-call idiom --
    never holds one connection open across an await boundary."""

    def __init__(self, db_path):
        self._db_path = db_path

    def list_origins(self, *, disease, country=None):
        repo = SQLiteOutbreakRepository(self._db_path)
        try:
            return build_forecast_origin_ledger(repo, disease=disease, country_scope=country)
        finally:
            repo.close()

    def get_origin_trigger_locations(self, origin):
        repo = SQLiteOutbreakRepository(self._db_path)
        try:
            locations = []
            for source_id in origin.trigger_source_ids_at_t0:
                record = repo.get_historical_record(source_id)
                if record is not None and record.latitude is not None and record.longitude is not None:
                    locations.append((source_id, record.latitude, record.longitude))
            return locations
        finally:
            repo.close()

    def get_origin_analysis(self, forecast_origin_id, *, disease):
        raise RuntimeAnalysisError10A("ORIGIN_NOT_FOUND", "not exercised by this integration test")

    def list_historical_trigger_candidates(self, *, disease, country=None):
        raise NotImplementedError("not exercised by My Area")


class TestRealRepositoryCountryFiltering:
    def test_sri_lanka_origin_included_foreign_origins_excluded_from_relevant_origins(self, repo):
        repo.add_historical_record(_historical(source_record_id="LK1", country="Sri Lanka", outbreak_start_date="2020-09-07", proxy_availability_date="2020-09-07"))
        repo.add_historical_record(_historical(source_record_id="AF1", country="Afghanistan", outbreak_start_date="2022-05-29", proxy_availability_date="2022-05-29", latitude=34.5, longitude=69.2))
        repo.add_historical_record(_historical(source_record_id="IN1", country="India", outbreak_start_date="2021-03-10", proxy_availability_date="2021-03-10", latitude=28.6, longitude=77.2))

        service = MyAreaContextService(_one_farm_port("F1", latitude=7.0, longitude=80.0), _RealPortOverRepo(repo.db_path))
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))

        assert len(result.relevant_origins) == 1
        assert result.relevant_origins[0].origin_id == "ORIGIN:Sri Lanka:2020-09-07"

    def test_no_sri_lanka_origins_but_foreign_origins_exist_is_honestly_empty(self, repo):
        repo.add_historical_record(_historical(source_record_id="AF1", country="Afghanistan", outbreak_start_date="2022-05-29", proxy_availability_date="2022-05-29", latitude=34.5, longitude=69.2))

        service = MyAreaContextService(_one_farm_port("F1", latitude=7.0, longitude=80.0), _RealPortOverRepo(repo.db_path))
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd"))

        # A populated GLOBAL ledger must never leak into "relevant" Sri
        # Lanka origins -- this is the exact original defect.
        assert result.status == MyAreaStatus.NO_RELEVANT_ORIGINS.value
        assert result.relevant_origins == []

    def test_real_foreign_origin_id_cannot_become_a_selected_origin(self, repo):
        repo.add_historical_record(_historical(source_record_id="LK1", country="Sri Lanka", outbreak_start_date="2020-09-07", proxy_availability_date="2020-09-07"))
        repo.add_historical_record(_historical(source_record_id="AF1", country="Afghanistan", outbreak_start_date="2022-05-29", proxy_availability_date="2022-05-29", latitude=34.5, longitude=69.2))

        service = MyAreaContextService(_one_farm_port("F1", latitude=7.0, longitude=80.0), _RealPortOverRepo(repo.db_path))
        # The real Afghanistan origin id, exactly as it would appear from a global (unscoped) ledger query.
        result = _run(service.get_my_area_context(_VET, farm_id="F1", disease="lsd", origin_id="ORIGIN:Afghanistan:2022-05-29"))

        assert result.status == MyAreaStatus.ORIGIN_NOT_FOUND.value
