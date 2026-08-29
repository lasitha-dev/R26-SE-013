"""GEO-LIVE-05 Section 15: focused tests for
`services/operational/event_normalization.py` -- the gate that decides
whether a raw case change becomes a `VerifiedClinicalEvent`."""

from __future__ import annotations

from components.geospatial_tracking.domain.operational_enums import LocationStatus
from components.geospatial_tracking.domain.operational_events import CaseChangeKind, RawCaseChange
from components.geospatial_tracking.domain.operational_models import HostDiagnosticCase, OperationalFarm
from components.geospatial_tracking.services.operational.event_normalization import normalize_case_event

_VALID_FARM = OperationalFarm(farm_id="F1", latitude=6.9, longitude=79.8, location_status=LocationStatus.VALID.value)
_INVALID_GPS_FARM = OperationalFarm(farm_id="F2", latitude=None, longitude=None, location_status=LocationStatus.LOCATION_REQUIRED.value)


def _case(**overrides) -> HostDiagnosticCase:
    fields = dict(
        case_id="C1",
        farm_id="F1",
        disease_name="Lumpy Skin Disease",
        verified=True,
        created_at="2026-01-01 09:00:00",
        verified_at="2026-01-02 10:00:00",
    )
    fields.update(overrides)
    return HostDiagnosticCase(**fields)


class TestAcceptedCases:
    def test_verified_lsd_event_accepted(self):
        change = RawCaseChange(case=_case(disease_name="Lumpy Skin Disease"), change_kind=CaseChangeKind.CREATED)
        event = normalize_case_event(change, assigned_farms_by_id={"F1": _VALID_FARM})
        assert event is not None
        assert event.disease == "LSD"
        assert event.event_type == "VERIFIED_CLINICAL_CONTEXT_CREATED"

    def test_verified_fmd_event_accepted(self):
        change = RawCaseChange(case=_case(disease_name="Foot and Mouth Disease"), change_kind=CaseChangeKind.UPDATED)
        event = normalize_case_event(change, assigned_farms_by_id={"F1": _VALID_FARM})
        assert event is not None
        assert event.disease == "FMD"
        assert event.event_type == "VERIFIED_CLINICAL_CONTEXT_UPDATED"


class TestRejectedCases:
    def test_unverified_case_ignored(self):
        change = RawCaseChange(case=_case(verified=False), change_kind=CaseChangeKind.CREATED)
        assert normalize_case_event(change, assigned_farms_by_id={"F1": _VALID_FARM}) is None

    def test_unsupported_disease_ignored(self):
        change = RawCaseChange(case=_case(disease_name="Mastitis"), change_kind=CaseChangeKind.CREATED)
        assert normalize_case_event(change, assigned_farms_by_id={"F1": _VALID_FARM}) is None

    def test_unassigned_farm_excluded(self):
        change = RawCaseChange(case=_case(farm_id="F-NOT-ASSIGNED"), change_kind=CaseChangeKind.CREATED)
        assert normalize_case_event(change, assigned_farms_by_id={"F1": _VALID_FARM}) is None

    def test_missing_farm_identity_rejected(self):
        change = RawCaseChange(case=_case(farm_id=None), change_kind=CaseChangeKind.CREATED)
        assert normalize_case_event(change, assigned_farms_by_id={"F1": _VALID_FARM}) is None

    def test_invalid_gps_farm_excluded(self):
        change = RawCaseChange(case=_case(farm_id="F2"), change_kind=CaseChangeKind.CREATED)
        assert normalize_case_event(change, assigned_farms_by_id={"F2": _INVALID_GPS_FARM}) is None

    def test_missing_verified_at_rejected(self):
        change = RawCaseChange(case=_case(verified_at=None), change_kind=CaseChangeKind.CREATED)
        assert normalize_case_event(change, assigned_farms_by_id={"F1": _VALID_FARM}) is None


class TestEventShape:
    def test_event_id_is_deterministic_by_case_and_verification_time(self):
        change = RawCaseChange(case=_case(), change_kind=CaseChangeKind.CREATED)
        event_a = normalize_case_event(change, assigned_farms_by_id={"F1": _VALID_FARM})
        event_b = normalize_case_event(change, assigned_farms_by_id={"F1": _VALID_FARM})
        assert event_a.event_id == event_b.event_id == "vcc:C1:2026-01-02 10:00:00"

    def test_event_never_uses_confirmed_outbreak_wording(self):
        change = RawCaseChange(case=_case(), change_kind=CaseChangeKind.CREATED)
        event = normalize_case_event(change, assigned_farms_by_id={"F1": _VALID_FARM})
        serialized = str(event.as_dict())
        assert "CONFIRMED_OUTBREAK" not in serialized
        assert "outbreak" not in serialized.lower()
        assert event.semantic_class == "VERIFIED_CLINICAL_CONTEXT"

    def test_no_pii_fields_present(self):
        change = RawCaseChange(case=_case(), change_kind=CaseChangeKind.CREATED)
        event = normalize_case_event(change, assigned_farms_by_id={"F1": _VALID_FARM})
        payload = event.as_dict()
        for forbidden_key in ("email", "phone", "owner", "image", "confidence", "vet_name", "password", "reasoning"):
            assert forbidden_key not in payload

    def test_deep_link_context_identifies_the_case_not_an_outbreak(self):
        change = RawCaseChange(case=_case(), change_kind=CaseChangeKind.CREATED)
        event = normalize_case_event(change, assigned_farms_by_id={"F1": _VALID_FARM})
        assert event.deep_link_context == {
            "target": "geospatial_clinical_case",
            "case_id": "C1",
            "farm_id": "F1",
            "disease": "LSD",
        }
        assert "selectedOutbreakId" not in event.deep_link_context
        assert "outbreak_id" not in event.deep_link_context
