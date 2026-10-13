"""GEO29A Phase 4/21: registered-district surveillance regression tests.

Real host evidence that motivated this feature (read-only, against the
live host `adrs_core` database this checkpoint): a real veterinarian
(license VET-LK-44444, district "Matara") has ZERO personally-assigned
farms, so `get_verified_clinical_cases` correctly returns an empty list
for them today -- but the underlying `diagnostic_cases` collection DOES
contain real verified FMD/LSD records (for a farm in a completely
different district, "Anuradhapura", assigned to two other vets). This
file proves the NEW district-surveillance path with synthetic fixtures
matching those real document shapes, never against the live database.
"""

import asyncio

from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext
from components.geospatial_tracking.repositories.host_operational_adapter import (
    MongoOperationalDataPort,
    district_matches,
)
from components.geospatial_tracking.services.operational.context_service import OperationalContextService

from ._operational_fakes import (
    FakeCollection,
    FakeOperationalDataPort,
    make_diagnostic_case_document,
    make_farm_document,
    make_vet_document,
)


def _run(coro):
    return asyncio.run(coro)


VET = AuthenticatedVetContext(email="vet@example.com", role="vet")


class TestDistrictMatches:
    """Phase 4/7: the real `location_district` string is messy
    (`"8.4162, 80.0261 (Anuradhapura District)"`, verified read-only
    against the live host database) -- never a clean district name."""

    def test_district_name_matches_inside_the_real_composite_string(self):
        assert district_matches("Anuradhapura", "8.4162, 80.0261 (Anuradhapura District)") is True

    def test_case_insensitive(self):
        assert district_matches("anuradhapura", "8.4162, 80.0261 (ANURADHAPURA DISTRICT)") is True

    def test_a_different_district_does_not_match(self):
        assert district_matches("Matara", "8.4162, 80.0261 (Anuradhapura District)") is False

    def test_all_districts_matches_any_farm_with_a_real_district_on_file(self):
        assert district_matches("ALL_DISTRICTS", "8.4162, 80.0261 (Anuradhapura District)") is True
        assert district_matches("all_districts", "Kegalle") is True

    def test_all_districts_never_matches_a_farm_with_no_district_at_all(self):
        assert district_matches("ALL_DISTRICTS", None) is False
        assert district_matches("ALL_DISTRICTS", "") is False

    def test_missing_vet_district_never_matches(self):
        assert district_matches(None, "Kegalle") is False
        assert district_matches("", "Kegalle") is False

    def test_missing_farm_district_never_matches(self):
        assert district_matches("Kegalle", None) is False


class TestVetWithDistrictButZeroAssignedFarms:
    """Regression item 1/2/3: exactly the real Dr. Thushan / VET-LK-44444
    shape -- a vet with a real registered district and zero personally-
    assigned farms still gets a real district-surveillance case."""

    def _make_port(self, vet_doc, farm_docs, case_docs) -> MongoOperationalDataPort:
        return MongoOperationalDataPort(
            vets_collection=FakeCollection([vet_doc]),
            farms_collection=FakeCollection(farm_docs),
            diagnostic_cases_collection=FakeCollection(case_docs),
        )

    def test_assigned_farm_scope_is_empty_but_district_scope_finds_the_real_case(self):
        vet = make_vet_document(email="vet@example.com", district="Anuradhapura", assigned_farm_ids=[], assigned_farms=[])
        farm = make_farm_document(location_district="8.4162, 80.0261 (Anuradhapura District)", assigned_vet_ids=[], assigned_vet_emails=[])
        case = make_diagnostic_case_document(farm_id=str(farm["_id"]), disease_name="Foot and Mouth Disease", verified=True, verified_at="2026-08-29 10:00:00")
        port = self._make_port(vet, [farm], [case])

        # The pre-existing assigned-farm path is untouched and correctly empty.
        assigned = _run(port.get_assigned_farms(VET))
        assert assigned == []
        assigned_cases = _run(port.get_verified_clinical_cases(VET))
        assert assigned_cases == []

        # The new district-surveillance path finds the real farm and case.
        district = _run(port.get_vet_district(VET))
        assert district == "Anuradhapura"
        district_farms = _run(port.get_district_surveillance_farms(VET, district))
        assert [f.farm_id for f in district_farms] == [str(farm["_id"])]
        district_cases = _run(port.get_verified_clinical_cases_for_farm_ids([f.farm_id for f in district_farms]))
        assert len(district_cases) == 1
        assert district_cases[0].disease_name == "Foot and Mouth Disease"

    def test_a_district_outside_the_vet_is_excluded(self):
        vet = make_vet_document(email="vet@example.com", district="Matara")
        farm = make_farm_document(location_district="8.4162, 80.0261 (Anuradhapura District)")
        port = self._make_port(vet, [farm], [])

        district = _run(port.get_vet_district(VET))
        assert district == "Matara"
        district_farms = _run(port.get_district_surveillance_farms(VET, district))
        assert district_farms == []

    def test_no_district_on_file_yields_none_never_a_guess(self):
        vet = make_vet_document(email="vet@example.com")
        del vet["district"]
        port = self._make_port(vet, [], [])
        assert _run(port.get_vet_district(VET)) is None


class TestAssignedFarmBehaviorRemainsIntact:
    """Regression item 8: the district-surveillance feature must never
    change the pre-existing assigned-farm path's own result."""

    def test_assigned_farm_flow_identical_to_before(self):
        vet = make_vet_document(email="vet@example.com", district="Colombo")
        own_farm = make_farm_document(assigned_vet_emails=["vet@example.com"], location_district="Colombo")
        case = make_diagnostic_case_document(farm_id=str(own_farm["_id"]), verified=True)
        port = MongoOperationalDataPort(
            vets_collection=FakeCollection([vet]),
            farms_collection=FakeCollection([own_farm]),
            diagnostic_cases_collection=FakeCollection([case]),
        )
        assigned = _run(port.get_assigned_farms(VET))
        assert [f.farm_id for f in assigned] == [str(own_farm["_id"])]
        cases = _run(port.get_verified_clinical_cases(VET))
        assert len(cases) == 1


class TestContextServiceSurveillanceAssembly:
    """Regression items 3/9/11: the service-level orchestration -- a vet
    with zero assigned farms (status NO_ASSIGNED_FARMS, unchanged) still
    gets a populated `surveillance_contexts`/`surveillance_farms`, and a
    scientific/host failure on ONE side never blanks the other."""

    def test_zero_assigned_farms_status_unchanged_but_surveillance_populated(self):
        from components.geospatial_tracking.domain.operational_models import HostDiagnosticCase, HostFarmRecord

        farm = HostFarmRecord(farm_id="farm-1", latitude=8.31, longitude=80.40, location_district="Anuradhapura District")
        case = HostDiagnosticCase(
            case_id="case-1", farm_id="farm-1", disease_name="Foot and Mouth Disease",
            verified=True, verified_at="2026-08-29 10:00:00",
        )
        port = FakeOperationalDataPort(
            farms=[], cases=[],
            district="Anuradhapura", district_farms=[farm], district_cases_by_farm_id={"farm-1": [case]},
        )
        result = _run(OperationalContextService(port).get_operational_context(VET))

        assert result.status == "NO_ASSIGNED_FARMS"  # Section 19 semantics unchanged
        assert result.farms == []
        assert result.clinical_contexts == []
        assert result.vet_district == "Anuradhapura"
        assert [f.farm_id for f in result.surveillance_farms] == ["farm-1"]
        assert result.surveillance_farms[0].personally_assigned is False
        assert len(result.surveillance_contexts) == 1
        assert result.surveillance_contexts[0].disease == "FMD"

    def test_district_lookup_failure_never_breaks_the_assigned_farm_response(self):
        from components.geospatial_tracking.domain.operational_models import HostFarmRecord

        farm = HostFarmRecord(farm_id="farm-1", latitude=6.9, longitude=79.9, location_district="Colombo")
        port = FakeOperationalDataPort(farms=[farm], cases=[], raise_on_district=True)
        result = _run(OperationalContextService(port).get_operational_context(VET))

        assert result.status == "NO_VERIFIED_CLINICAL_CONTEXT"
        assert [f.farm_id for f in result.farms] == ["farm-1"]
        assert result.vet_district is None
        assert result.surveillance_farms == []
        assert result.surveillance_contexts == []

    def test_personally_assigned_farm_is_flagged_true_inside_surveillance_scope(self):
        """A farm that is BOTH assigned to the vet AND inside their
        district appears in `surveillance_farms` with
        `personally_assigned=True`, not the district-only default."""
        from components.geospatial_tracking.domain.operational_models import HostFarmRecord

        farm = HostFarmRecord(farm_id="farm-1", latitude=6.9, longitude=79.9, location_district="Colombo")
        port = FakeOperationalDataPort(
            farms=[farm], cases=[],
            district="Colombo", district_farms=[farm], district_cases_by_farm_id={},
        )
        result = _run(OperationalContextService(port).get_operational_context(VET))
        assert result.surveillance_farms[0].personally_assigned is True
        # Herd size is not redacted for a personally-assigned farm.
        # (total_animals is None here only because the fixture omitted it.)


class TestPrivacyFirewall:
    """Regression item 9: no herd-size/private detail leaks for a
    district-only (not personally assigned) farm."""

    def test_total_animals_redacted_for_district_only_farm(self):
        from components.geospatial_tracking.services.operational.farm_normalization import normalize_assigned_farm
        from components.geospatial_tracking.domain.operational_models import HostFarmRecord

        raw = HostFarmRecord(farm_id="farm-1", latitude=6.9, longitude=79.9, total_animals=42)
        district_only = normalize_assigned_farm(raw, personally_assigned=False)
        assert district_only.total_animals is None

        assigned = normalize_assigned_farm(raw, personally_assigned=True)
        assert assigned.total_animals == 42

    def test_default_personally_assigned_is_true_for_backward_compatibility(self):
        from components.geospatial_tracking.services.operational.farm_normalization import normalize_assigned_farm
        from components.geospatial_tracking.domain.operational_models import HostFarmRecord

        raw = HostFarmRecord(farm_id="farm-1", latitude=6.9, longitude=79.9, total_animals=42)
        farm = normalize_assigned_farm(raw)
        assert farm.personally_assigned is True
        assert farm.total_animals == 42
