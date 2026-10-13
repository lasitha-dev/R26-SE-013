"""GEO-INT-01 Section 11-14: the verified-clinical-context filter, plus the
semantic-firewall and timestamp-semantics proofs (Section I/J of the
required report)."""

from components.geospatial_tracking.domain.operational_enums import ClinicalSemanticClass, LocationStatus, TimestampBasis
from components.geospatial_tracking.domain.operational_models import HostDiagnosticCase, OperationalFarm
from components.geospatial_tracking.services.operational.clinical_context import build_verified_clinical_context

_VALID_FARM = OperationalFarm(
    farm_id="F1", latitude=6.9, longitude=79.8, location_status=LocationStatus.VALID.value
)
_UNGEOLOCATED_FARM = OperationalFarm(
    farm_id="F2", latitude=None, longitude=None, location_status=LocationStatus.LOCATION_REQUIRED.value
)
_FARMS_BY_ID = {"F1": _VALID_FARM, "F2": _UNGEOLOCATED_FARM}


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


class TestQualifyingGates:
    def test_verified_lsd_case_qualifies(self):
        ctx = build_verified_clinical_context(_case(), assigned_farms_by_id=_FARMS_BY_ID)
        assert ctx is not None
        assert ctx.disease == "LSD"

    def test_verified_fmd_case_qualifies_independently(self):
        ctx = build_verified_clinical_context(
            _case(case_id="C2", disease_name="Foot and Mouth Disease"), assigned_farms_by_id=_FARMS_BY_ID
        )
        assert ctx is not None
        assert ctx.disease == "FMD"

    def test_unverified_case_excluded(self):
        ctx = build_verified_clinical_context(_case(verified=False), assigned_farms_by_id=_FARMS_BY_ID)
        assert ctx is None

    def test_case_for_unassigned_farm_excluded(self):
        ctx = build_verified_clinical_context(_case(farm_id="F-NOT-ASSIGNED"), assigned_farms_by_id=_FARMS_BY_ID)
        assert ctx is None

    def test_missing_farm_id_excluded(self):
        ctx = build_verified_clinical_context(_case(farm_id=None), assigned_farms_by_id=_FARMS_BY_ID)
        assert ctx is None

    def test_case_for_ungeolocated_farm_excluded(self):
        ctx = build_verified_clinical_context(_case(farm_id="F2"), assigned_farms_by_id=_FARMS_BY_ID)
        assert ctx is None

    def test_unsupported_disease_excluded(self):
        ctx = build_verified_clinical_context(_case(disease_name="Mastitis"), assigned_farms_by_id=_FARMS_BY_ID)
        assert ctx is None

    def test_missing_case_identity_excluded(self):
        ctx = build_verified_clinical_context(_case(case_id=""), assigned_farms_by_id=_FARMS_BY_ID)
        assert ctx is None

    def test_missing_verification_timestamp_excluded(self):
        ctx = build_verified_clinical_context(_case(verified_at=None), assigned_farms_by_id=_FARMS_BY_ID)
        assert ctx is None

    def test_malformed_record_is_excluded_not_repaired(self):
        # farm_id present but pointing nowhere real -- must be dropped,
        # never "fixed" by attaching it to some other assigned farm.
        ctx = build_verified_clinical_context(_case(farm_id=""), assigned_farms_by_id=_FARMS_BY_ID)
        assert ctx is None


class TestFarmAndHealthAlertNeverBecomeClinicalContext:
    def test_farm_registration_alone_is_not_a_clinical_context(self):
        # A farm with zero diagnostic cases yields zero clinical contexts --
        # build_verified_clinical_context is simply never invoked for it.
        # Nothing about an OperationalFarm alone can produce one.
        assert not hasattr(_VALID_FARM, "semantic_class")

    def test_health_alert_alone_cannot_reach_this_boundary(self):
        # HostDiagnosticCase (the only case-shaped input this filter
        # accepts) has no cattle/health-alert field at all -- a cattle
        # health_status change cannot be expressed as one, structurally.
        case_fields = set(HostDiagnosticCase.__dataclass_fields__)
        assert case_fields.isdisjoint({"health_status", "cattle_health_status", "alert", "status"})


class TestSemanticFirewall:
    def test_verified_clinical_context_is_never_labelled_confirmed_outbreak(self):
        ctx = build_verified_clinical_context(_case(), assigned_farms_by_id=_FARMS_BY_ID)
        assert ctx.semantic_class == ClinicalSemanticClass.VERIFIED_CLINICAL_CONTEXT.value
        assert ctx.semantic_class not in ("CONFIRMED_OUTBREAK", "Confirmed Outbreak", "OUTBREAK")

    def test_clinical_semantic_class_enum_has_no_outbreak_member(self):
        member_values = {member.value for member in ClinicalSemanticClass}
        assert member_values == {"VERIFIED_CLINICAL_CONTEXT"}


class TestTimestampSemantics:
    def test_verified_at_is_labelled_verification_time(self):
        ctx = build_verified_clinical_context(_case(), assigned_farms_by_id=_FARMS_BY_ID)
        assert ctx.timestamp_basis == TimestampBasis.VERIFICATION_TIME.value
        assert ctx.verification_time == "2026-01-02 10:00:00"

    def test_created_at_is_not_interpreted_as_onset_time(self):
        ctx = build_verified_clinical_context(_case(), assigned_farms_by_id=_FARMS_BY_ID)
        assert ctx.case_creation_time == "2026-01-01 09:00:00"
        # the DTO has no onset/observation field at all to accidentally
        # populate from created_at:
        assert not hasattr(ctx, "onset_date")
        assert not hasattr(ctx, "observation_date")
        assert not hasattr(ctx, "outbreak_start_date")


class TestDeterministicFiltering:
    def test_same_input_produces_identical_output(self):
        ctx_a = build_verified_clinical_context(_case(), assigned_farms_by_id=_FARMS_BY_ID)
        ctx_b = build_verified_clinical_context(_case(), assigned_farms_by_id=_FARMS_BY_ID)
        assert ctx_a == ctx_b
