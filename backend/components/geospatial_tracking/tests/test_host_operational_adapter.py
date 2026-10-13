"""GEO-INT-02 Section 15: `MongoOperationalDataPort` tests against
`FakeCollection` — realistic vet/farm/diagnostic-case document shapes
(Section 14), no real Mongo/network."""

import asyncio

import pytest
from bson import ObjectId

from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext
from components.geospatial_tracking.repositories.host_operational_adapter import MongoOperationalDataPort
from components.geospatial_tracking.services.operational.context_service import OperationalContextService

from ._operational_fakes import FakeCollection, make_diagnostic_case_document, make_farm_document, make_vet_document


def _run(coro):
    return asyncio.run(coro)


def _make_port(vets=None, farms=None, cases=None) -> MongoOperationalDataPort:
    return MongoOperationalDataPort(
        vets_collection=FakeCollection(vets or []),
        farms_collection=FakeCollection(farms or []),
        diagnostic_cases_collection=FakeCollection(cases or []),
    )


class TestAssignedFarmResolution:
    def test_resolves_only_own_assigned_farms(self):
        vet = make_vet_document(email="vet@example.com")
        own_farm = make_farm_document(assigned_vet_emails=["vet@example.com"])
        other_farm = make_farm_document(assigned_vet_emails=["other-vet@example.com"])
        port = _make_port(vets=[vet], farms=[own_farm, other_farm])

        result = _run(port.get_assigned_farms(AuthenticatedVetContext(email="vet@example.com", role="vet")))

        assert [f.farm_id for f in result] == [str(own_farm["_id"])]

    def test_another_vets_farms_excluded(self):
        vet_a = make_vet_document(email="vet-a@example.com")
        vet_b = make_vet_document(email="vet-b@example.com")
        farm_for_b = make_farm_document(assigned_vet_emails=["vet-b@example.com"])
        port = _make_port(vets=[vet_a, vet_b], farms=[farm_for_b])

        result = _run(port.get_assigned_farms(AuthenticatedVetContext(email="vet-a@example.com", role="vet")))

        assert result == []

    def test_no_vet_record_is_a_safe_empty_outcome(self):
        port = _make_port(vets=[], farms=[make_farm_document()])
        result = _run(port.get_assigned_farms(AuthenticatedVetContext(email="ghost@example.com", role="vet")))
        assert result == []

    def test_empty_assignment_returns_empty_result(self):
        vet = make_vet_document(email="vet@example.com", assigned_farm_ids=[], assigned_farms=[])
        unrelated_farm = make_farm_document(assigned_vet_ids=[], assigned_vet_emails=[])
        port = _make_port(vets=[vet], farms=[unrelated_farm])
        result = _run(port.get_assigned_farms(AuthenticatedVetContext(email="vet@example.com", role="vet")))
        assert result == []

    def test_assignment_via_vet_assigned_farm_ids(self):
        farm = make_farm_document()
        vet = make_vet_document(email="vet@example.com", assigned_farm_ids=[str(farm["_id"])])
        port = _make_port(vets=[vet], farms=[farm])
        result = _run(port.get_assigned_farms(AuthenticatedVetContext(email="vet@example.com", role="vet")))
        assert [f.farm_id for f in result] == [str(farm["_id"])]

    def test_assignment_via_farm_assigned_vet_ids(self):
        vet = make_vet_document(email="vet@example.com")
        farm = make_farm_document(assigned_vet_ids=[str(vet["_id"])])
        port = _make_port(vets=[vet], farms=[farm])
        result = _run(port.get_assigned_farms(AuthenticatedVetContext(email="vet@example.com", role="vet")))
        assert [f.farm_id for f in result] == [str(farm["_id"])]


class TestFarmGpsMapping:
    def test_valid_gps_mapped(self):
        farm = make_farm_document(assigned_vet_emails=["vet@example.com"], latitude=6.9271, longitude=79.8612)
        vet = make_vet_document(email="vet@example.com")
        port = _make_port(vets=[vet], farms=[farm])
        result = _run(port.get_assigned_farms(AuthenticatedVetContext(email="vet@example.com", role="vet")))
        assert result[0].latitude == 6.9271
        assert result[0].longitude == 79.8612

    def test_missing_gps_preserved_not_fabricated(self):
        # GEO-INT-01's farm_normalization.py, not this adapter, decides
        # LOCATION_REQUIRED -- the adapter must pass None through as-is.
        farm = make_farm_document(assigned_vet_emails=["vet@example.com"], latitude=None, longitude=None)
        vet = make_vet_document(email="vet@example.com")
        port = _make_port(vets=[vet], farms=[farm])
        result = _run(port.get_assigned_farms(AuthenticatedVetContext(email="vet@example.com", role="vet")))
        assert result[0].latitude is None
        assert result[0].longitude is None


class TestIdNormalization:
    def test_farm_id_matches_between_farms_and_cases(self):
        farm = make_farm_document(assigned_vet_emails=["vet@example.com"])
        vet = make_vet_document(email="vet@example.com")
        case = make_diagnostic_case_document(farm_id=str(farm["_id"]), verified=True)
        port = _make_port(vets=[vet], farms=[farm], cases=[case])

        vet_ctx = AuthenticatedVetContext(email="vet@example.com", role="vet")
        farms = _run(port.get_assigned_farms(vet_ctx))
        cases = _run(port.get_verified_clinical_cases(vet_ctx))

        assert farms[0].farm_id == cases[0].farm_id  # both str(ObjectId), same representation


class TestVerifiedClinicalCaseResolution:
    def _vet_and_farm(self, email="vet@example.com"):
        farm = make_farm_document(assigned_vet_emails=[email])
        vet = make_vet_document(email=email)
        return vet, farm

    def test_verified_lsd_case_returned(self):
        vet, farm = self._vet_and_farm()
        case = make_diagnostic_case_document(farm_id=str(farm["_id"]), disease_name="Lumpy Skin Disease", verified=True)
        port = _make_port(vets=[vet], farms=[farm], cases=[case])
        result = _run(port.get_verified_clinical_cases(AuthenticatedVetContext(email=vet["email"], role="vet")))
        assert result[0].disease_name == "Lumpy Skin Disease"

    def test_verified_fmd_case_returned(self):
        vet, farm = self._vet_and_farm()
        case = make_diagnostic_case_document(farm_id=str(farm["_id"]), disease_name="Foot and Mouth Disease", verified=True)
        port = _make_port(vets=[vet], farms=[farm], cases=[case])
        result = _run(port.get_verified_clinical_cases(AuthenticatedVetContext(email=vet["email"], role="vet")))
        assert result[0].disease_name == "Foot and Mouth Disease"

    def test_unverified_case_excluded(self):
        vet, farm = self._vet_and_farm()
        case = make_diagnostic_case_document(farm_id=str(farm["_id"]), verified=False)
        port = _make_port(vets=[vet], farms=[farm], cases=[case])
        result = _run(port.get_verified_clinical_cases(AuthenticatedVetContext(email=vet["email"], role="vet")))
        assert result == []

    def test_case_for_unassigned_farm_excluded(self):
        vet, farm = self._vet_and_farm()
        unassigned_farm = make_farm_document(assigned_vet_emails=["someone-else@example.com"])
        case = make_diagnostic_case_document(farm_id=str(unassigned_farm["_id"]), verified=True)
        port = _make_port(vets=[vet], farms=[farm, unassigned_farm], cases=[case])
        result = _run(port.get_verified_clinical_cases(AuthenticatedVetContext(email=vet["email"], role="vet")))
        assert result == []

    def test_malformed_farm_id_excluded_safely(self):
        vet, farm = self._vet_and_farm()
        case = make_diagnostic_case_document(farm_id="not-a-real-id", verified=True)
        port = _make_port(vets=[vet], farms=[farm], cases=[case])
        result = _run(port.get_verified_clinical_cases(AuthenticatedVetContext(email=vet["email"], role="vet")))
        assert result == []

    def test_unsupported_disease_still_crosses_the_raw_adapter(self):
        # The adapter is not responsible for disease classification --
        # GEO-INT-01's disease_normalization.py/clinical_context.py is.
        # A raw "Mastitis" case is returned here (unclassified); a full
        # OperationalContextService run (below) proves it never reaches
        # the final context as LSD/FMD.
        vet, farm = self._vet_and_farm()
        case = make_diagnostic_case_document(farm_id=str(farm["_id"]), disease_name="Mastitis", verified=True)
        port = _make_port(vets=[vet], farms=[farm], cases=[case])
        result = _run(port.get_verified_clinical_cases(AuthenticatedVetContext(email=vet["email"], role="vet")))
        assert result[0].disease_name == "Mastitis"

    def test_unsupported_disease_never_reaches_final_context_as_lsd_or_fmd(self):
        vet, farm = self._vet_and_farm()
        case = make_diagnostic_case_document(farm_id=str(farm["_id"]), disease_name="Mastitis", verified=True)
        port = _make_port(vets=[vet], farms=[farm], cases=[case])
        context = _run(OperationalContextService(port).get_operational_context(AuthenticatedVetContext(email=vet["email"], role="vet")))
        assert context.clinical_contexts == []


class TestDataMinimizationAndPii:
    def test_farm_record_has_no_owner_pii(self):
        vet, farm = self._farm_with_pii()
        port = _make_port(vets=[vet], farms=[farm])
        result = _run(port.get_assigned_farms(AuthenticatedVetContext(email=vet["email"], role="vet")))
        record = result[0]
        for forbidden_attr in ("owner_name", "email", "phone", "password"):
            assert not hasattr(record, forbidden_attr)

    def test_case_record_has_no_images_or_reasoning(self):
        vet, farm = self._farm_with_pii()
        case = make_diagnostic_case_document(
            farm_id=str(farm["_id"]),
            verified=True,
            symptoms_image="data:image/jpeg;base64,xxx",
            cropped_image="data:image/jpeg;base64,yyy",
            llm_reasoning="some reasoning text",
            clinical_notes="private notes",
        )
        port = _make_port(vets=[vet], farms=[farm], cases=[case])
        result = _run(port.get_verified_clinical_cases(AuthenticatedVetContext(email=vet["email"], role="vet")))
        record = result[0]
        for forbidden_attr in ("symptoms_image", "cropped_image", "llm_reasoning", "clinical_notes", "cattle_id", "animal_identifier"):
            assert not hasattr(record, forbidden_attr)

    @staticmethod
    def _farm_with_pii():
        vet = make_vet_document(email="vet@example.com", full_name="Dr. Real Name", phone="0771234567")
        farm = make_farm_document(
            assigned_vet_emails=["vet@example.com"], owner_name="Real Farmer Name", email="farmer@example.com", password="hashed-secret"
        )
        return vet, farm


class TestCollectionFailureHandledByService:
    def test_collection_failure_maps_to_operational_data_unavailable(self):
        class _RaisingCollection:
            async def find_one(self, filter):
                raise RuntimeError("simulated Mongo outage")

            def find(self, filter):
                raise RuntimeError("simulated Mongo outage")

        port = MongoOperationalDataPort(
            vets_collection=_RaisingCollection(),
            farms_collection=FakeCollection([]),
            diagnostic_cases_collection=FakeCollection([]),
        )
        from components.geospatial_tracking.domain.operational_enums import OperationalStatus

        context = _run(
            OperationalContextService(port).get_operational_context(
                AuthenticatedVetContext(email="vet@example.com", role="vet")
            )
        )
        assert context.status == OperationalStatus.OPERATIONAL_DATA_UNAVAILABLE.value


class TestReadOnlyGuarantee:
    def test_adapter_source_contains_no_mutation_calls(self):
        import ast
        import inspect

        from components.geospatial_tracking.repositories import host_operational_adapter

        tree = ast.parse(inspect.getsource(host_operational_adapter))
        forbidden = {"insert_one", "insert_many", "update_one", "update_many", "replace_one", "delete_one", "delete_many"}
        called_attribute_names = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert called_attribute_names.isdisjoint(forbidden)

    def test_fake_collection_exposes_no_mutation_methods(self):
        collection = FakeCollection([])
        for forbidden in ("insert_one", "insert_many", "update_one", "update_many", "replace_one", "delete_one", "delete_many"):
            assert not hasattr(collection, forbidden)


class TestOrderingPassThrough:
    def test_adapter_does_not_need_to_sort_its_own_output(self):
        # Determinism is OperationalContextService's job (Section 20,
        # GEO-INT-01); the adapter just needs to not scramble whatever the
        # collection yields, which FakeCollection/find() already preserves
        # insertion order for.
        vet = make_vet_document(email="vet@example.com")
        farm_b = make_farm_document(assigned_vet_emails=["vet@example.com"])
        farm_a = make_farm_document(assigned_vet_emails=["vet@example.com"])
        port = _make_port(vets=[vet], farms=[farm_b, farm_a])
        result = _run(port.get_assigned_farms(AuthenticatedVetContext(email="vet@example.com", role="vet")))
        assert [f.farm_id for f in result] == [str(farm_b["_id"]), str(farm_a["_id"])]
