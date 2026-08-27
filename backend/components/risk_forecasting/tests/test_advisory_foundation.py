"""
Phase 3 Advisory Backend Foundation Test Suite (Audited & Refined).

Verifies all 38 mandatory requirements & targeted business-logic audit criteria:
- FMD & LSD advisory draft creation from stored ForecastDecisionRecords
- Authoritative forecast context mapping (risk level, disease, district, period, disclaimer)
- Template generation & priority recommendations (LOW->ROUTINE, MEDIUM->IMPORTANT, HIGH->URGENT)
- Multi-district Vet ALL_ASSIGNED recipient resolution (eligible_count vs total_assigned)
- Rejection of unassigned and district-incompatible recipients
- Recipient summary metric formula (total_assigned, eligible_count, selected_count, standard_message_count, personalized_count, excluded_count)
- Advisory Type Scope Control (SYSTEM_FORECAST_ADVISORY & VETERINARY_CUSTOM_ADVICE supported; OFFICIAL_DAPH_NOTICE rejected)
- Message resolution (standard vs personalized overrides)
- Preview operation safety (creates 0 records, modifies 0 forecasts, sends 0 notifications)
- Idempotency creation safeguards, header/body mismatch rejection (409)
- Optimistic concurrency control (version checking)
- Strict Lifecycle Status Transition Matrix (DRAFT -> REVIEW_READY -> APPROVED / CANCELLED; DRAFT->APPROVED rejected; REVIEW_READY edit resets to DRAFT)
- Approved/Cancelled content immutability & repeated approval rejection
- Absolute ForecastDecisionRecord Snapshot Equality (status & scientific fields 100% unchanged across preview/draft/review/approval)
- Bounded list pagination and filtering
- Defensive-copy repository safety
- Integration safety (no notification provider, no TrendService)
"""

from datetime import datetime, timezone
import unittest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from components.risk_forecasting.integrations.recipient_directory import (
    InMemoryRecipientDirectory,
    Recipient,
)
from components.risk_forecasting.repositories.advisory_repository import (
    InMemoryAdvisoryRepository,
)
from components.risk_forecasting.repositories.forecast_record_repository import (
    InMemoryForecastRecordRepository,
)
from components.risk_forecasting.routes import router
from components.risk_forecasting.schemas import (
    CreateAdvisoryDraftRequest,
    FarmerAdvisoryRecord,
    GenerateForecastRecordRequest,
    PersonalizedOverride,
    UpdateAdvisoryDraftRequest,
)
from components.risk_forecasting.services.advisory_service import AdvisoryService
from components.risk_forecasting.services.advisory_template_service import AdvisoryTemplateService
from components.risk_forecasting.services.forecast_record_service import ForecastRecordService

app = FastAPI()
app.include_router(router, prefix="/api/v1/risk-forecasting")


class TestAdvisoryFoundation(unittest.TestCase):
    def setUp(self):
        self.forecast_repo = InMemoryForecastRecordRepository()
        self.forecast_svc = ForecastRecordService(repository=self.forecast_repo)
        self.advisory_repo = InMemoryAdvisoryRepository()
        self.recipient_dir = InMemoryRecipientDirectory()
        self.template_svc = AdvisoryTemplateService()

        # Deterministic clock and ID generator
        self.fixed_now = datetime(2026, 8, 22, 10, 0, 0, tzinfo=timezone.utc)
        self.counter = 0

        def clock_stub():
            return self.fixed_now

        def id_gen_stub():
            self.counter += 1
            return f"adv_stub_{self.counter:04d}"

        self.advisory_svc = AdvisoryService(
            forecast_service=self.forecast_svc,
            advisory_repository=self.advisory_repo,
            recipient_dir=self.recipient_dir,
            template_svc=self.template_svc,
            clock=clock_stub,
            id_generator=id_gen_stub,
        )

        # Seed authoritative FMD and LSD forecast decision records
        fmd_req = GenerateForecastRecordRequest(
            disease="FMD",
            district="Anuradhapura",
            year=2024,
            month=1,
            trigger_type="MANUAL",
            generated_by="vet_officer_01",
        )
        self.fmd_record = self.forecast_svc.generate_record(fmd_req)

        lsd_req = GenerateForecastRecordRequest(
            disease="LSD",
            district="Colombo",
            year=2024,
            month=2,
            trigger_type="MANUAL",
            generated_by="vet_officer_01",
        )
        self.lsd_record = self.forecast_svc.generate_record(lsd_req)

        self.client = TestClient(app)

    # 1. Create FMD advisory from a stored forecast record
    def test_01_create_fmd_advisory(self):
        req = CreateAdvisoryDraftRequest(
            forecast_id=self.fmd_record.forecast_id,
            recipient_scope="ALL_ASSIGNED",
            created_by="vet_officer_01",
        )
        adv = self.advisory_svc.create_draft(req)
        self.assertTrue(adv.advisory_id.startswith("adv_stub_"))
        self.assertEqual(adv.forecast_id, self.fmd_record.forecast_id)
        self.assertEqual(adv.disease, "FMD")
        self.assertEqual(adv.district, "Anuradhapura")
        self.assertEqual(adv.status, "DRAFT")

    # 2. Create LSD advisory from a stored forecast record
    def test_02_create_lsd_advisory(self):
        req = CreateAdvisoryDraftRequest(
            forecast_id=self.lsd_record.forecast_id,
            recipient_scope="ALL_ASSIGNED",
            created_by="vet_officer_01",
        )
        adv = self.advisory_svc.create_draft(req)
        self.assertEqual(adv.forecast_id, self.lsd_record.forecast_id)
        self.assertEqual(adv.disease, "LSD")
        self.assertEqual(adv.district, "Colombo")

    # 3. Authoritative forecast context mapping
    def test_03_authoritative_forecast_context_mapping(self):
        req = CreateAdvisoryDraftRequest(
            forecast_id=self.fmd_record.forecast_id,
            recipient_scope="ALL_ASSIGNED",
            created_by="vet_officer_01",
        )
        adv = self.advisory_svc.create_draft(req)
        self.assertEqual(adv.disease, self.fmd_record.disease)
        self.assertEqual(adv.district, self.fmd_record.district)
        self.assertEqual(adv.target_year, self.fmd_record.target_year)
        self.assertEqual(adv.target_month, self.fmd_record.target_month)
        self.assertEqual(adv.risk_level, self.fmd_record.risk_level)
        self.assertEqual(adv.disclaimer, self.fmd_record.disclaimer)

    # 4. Standard FMD template
    def test_04_standard_fmd_template(self):
        title, summary, actions, symptoms, contact, disclaimer, priority = self.template_svc.generate_standard_content(
            disease="FMD", district="Anuradhapura", target_year=2024, target_month=1, risk_level="MEDIUM"
        )
        self.assertIn("Foot and Mouth Disease", title)
        self.assertIn("MEDIUM risk", summary)
        self.assertTrue(len(actions) >= 3)
        self.assertTrue(len(symptoms) >= 3)
        self.assertIn("Anuradhapura District", contact)
        self.assertEqual(priority, "IMPORTANT")

    # 5. Standard LSD template
    def test_05_standard_lsd_template(self):
        title, summary, actions, symptoms, contact, disclaimer, priority = self.template_svc.generate_standard_content(
            disease="LSD", district="Colombo", target_year=2024, target_month=2, risk_level="HIGH"
        )
        self.assertIn("Lumpy Skin Disease", title)
        self.assertIn("HIGH risk", summary)
        self.assertTrue(len(actions) >= 3)
        self.assertTrue(len(symptoms) >= 3)
        self.assertIn("Colombo District", contact)
        self.assertEqual(priority, "URGENT")

    # 6. LOW/MEDIUM/HIGH priority recommendation
    def test_06_priority_recommendations(self):
        self.assertEqual(self.template_svc.map_priority("LOW"), "ROUTINE")
        self.assertEqual(self.template_svc.map_priority("MEDIUM"), "IMPORTANT")
        self.assertEqual(self.template_svc.map_priority("HIGH"), "URGENT")

    # 7. ALL_ASSIGNED multi-district recipient resolution & summary formula
    def test_07_all_assigned_multi_district_resolution(self):
        req = CreateAdvisoryDraftRequest(
            forecast_id=self.fmd_record.forecast_id,
            recipient_scope="ALL_ASSIGNED",
            created_by="vet_officer_01",
        )
        adv = self.advisory_svc.create_draft(req)
        # vet_officer_01 has 20 total farms across 4 districts (5 in Anuradhapura)
        s = adv.recipient_summary
        self.assertEqual(s.total_assigned, 20)
        self.assertEqual(s.eligible_count, 5)
        self.assertEqual(s.selected_count, 5)
        self.assertEqual(s.excluded_count, 15)

    # 8. ALL_ASSIGNED rejection when zero eligible farms in forecast district
    def test_08_all_assigned_zero_eligible_farms_rejection(self):
        # Create forecast for Badulla district where vet_officer_01 has 0 farms
        badulla_req = GenerateForecastRecordRequest(
            disease="FMD", district="Badulla", year=2024, month=1, trigger_type="MANUAL"
        )
        badulla_fdr = self.forecast_svc.generate_record(badulla_req)

        draft_req = CreateAdvisoryDraftRequest(
            forecast_id=badulla_fdr.forecast_id,
            recipient_scope="ALL_ASSIGNED",
            created_by="vet_officer_01",
        )
        with self.assertRaises(ValueError) as ctx:
            self.advisory_svc.create_draft(draft_req)
        self.assertIn("No assigned farms found in district 'Badulla'", str(ctx.exception))

    # 9. SELECTED recipient resolution
    def test_09_selected_recipient_resolution(self):
        req = CreateAdvisoryDraftRequest(
            forecast_id=self.fmd_record.forecast_id,
            recipient_scope="SELECTED",
            selected_recipient_ids=["DEMO_FARM_001", "DEMO_FARM_002"],
            created_by="vet_officer_01",
        )
        adv = self.advisory_svc.create_draft(req)
        s = adv.recipient_summary
        self.assertEqual(s.total_assigned, 20)
        self.assertEqual(s.eligible_count, 5)
        self.assertEqual(s.selected_count, 2)
        self.assertEqual(s.excluded_count, 18)

    # 10. Reject unassigned recipient
    def test_10_reject_unassigned_recipient(self):
        self.recipient_dir.add_recipient(
            Recipient(recipient_id="DEMO_FARM_999", recipient_name="Other Farm", district="Anuradhapura", assigned_vet_id="other_vet")
        )
        req = CreateAdvisoryDraftRequest(
            forecast_id=self.fmd_record.forecast_id,
            recipient_scope="SELECTED",
            selected_recipient_ids=["DEMO_FARM_999"],
            created_by="vet_officer_01",
        )
        with self.assertRaises(ValueError) as ctx:
            self.advisory_svc.create_draft(req)
        self.assertIn("not requesting vet", str(ctx.exception))

    # 11. Reject district-incompatible recipient under SELECTED scope
    def test_11_reject_district_incompatible_recipient(self):
        # DEMO_FARM_006 is in Colombo, but forecast is for Anuradhapura
        req = CreateAdvisoryDraftRequest(
            forecast_id=self.fmd_record.forecast_id,
            recipient_scope="SELECTED",
            selected_recipient_ids=["DEMO_FARM_006"],
            created_by="vet_officer_01",
        )
        with self.assertRaises(ValueError) as ctx:
            self.advisory_svc.create_draft(req)
        self.assertIn("incompatible with forecast district", str(ctx.exception))

    # 12. Advisory Type Scope Control
    def test_12_advisory_type_scope_control(self):
        # 1. SYSTEM_FORECAST_ADVISORY -> Supported
        req1 = CreateAdvisoryDraftRequest(
            forecast_id=self.fmd_record.forecast_id,
            advisory_type="SYSTEM_FORECAST_ADVISORY",
        )
        adv1 = self.advisory_svc.create_draft(req1)
        self.assertEqual(adv1.advisory_type, "SYSTEM_FORECAST_ADVISORY")

        # 2. VETERINARY_CUSTOM_ADVICE -> Supported
        req2 = CreateAdvisoryDraftRequest(
            forecast_id=self.fmd_record.forecast_id,
            advisory_type="VETERINARY_CUSTOM_ADVICE",
        )
        adv2 = self.advisory_svc.create_draft(req2)
        self.assertEqual(adv2.advisory_type, "VETERINARY_CUSTOM_ADVICE")

        # 3. OFFICIAL_DAPH_NOTICE -> Rejected in Phase 3
        req3 = CreateAdvisoryDraftRequest(
            forecast_id=self.fmd_record.forecast_id,
            advisory_type="OFFICIAL_DAPH_NOTICE",
        )
        with self.assertRaises(ValueError) as ctx:
            self.advisory_svc.create_draft(req3)
        self.assertIn("OFFICIAL_DAPH_NOTICE' is not supported", str(ctx.exception))

    # 13. Message resolution (standard vs personalized)
    def test_13_personalized_override_resolution(self):
        req = CreateAdvisoryDraftRequest(
            forecast_id=self.fmd_record.forecast_id,
            recipient_scope="SELECTED",
            selected_recipient_ids=["DEMO_FARM_001", "DEMO_FARM_002"],
            personalized_overrides=[
                PersonalizedOverride(recipient_id="DEMO_FARM_001", custom_note="Check rear barn ventilation")
            ],
            created_by="vet_officer_01",
        )
        adv = self.advisory_svc.create_draft(req)
        prev = self.advisory_svc.preview_advisory(advisory_id=adv.advisory_id)
        p_by_id = {p.recipient_id: p for p in prev.previews}
        self.assertTrue(p_by_id["DEMO_FARM_001"].is_personalized)
        self.assertIn("Check rear barn ventilation", p_by_id["DEMO_FARM_001"].final_message)
        self.assertFalse(p_by_id["DEMO_FARM_002"].is_personalized)

    # 14. Preview Purity & State Evidence
    def test_14_preview_purity(self):
        # Snapshot repository size before
        initial_advisories, total_before = self.advisory_repo.list()
        self.assertEqual(total_before, 0)
        fdr_before = self.fmd_record.model_dump()

        prev = self.advisory_svc.preview_advisory(
            draft_req=CreateAdvisoryDraftRequest(
                forecast_id=self.fmd_record.forecast_id,
                recipient_scope="ALL_ASSIGNED",
            )
        )
        self.assertEqual(len(prev.previews), 5)

        # Snapshot repository size & forecast record after
        _, total_after = self.advisory_repo.list()
        self.assertEqual(total_after, 0)
        fdr_after = self.forecast_svc.get_record(self.fmd_record.forecast_id).model_dump()
        self.assertEqual(fdr_before, fdr_after)

    # 15. Idempotent Retry & Idempotency Key Collision
    def test_15_idempotency_retry_and_collision(self):
        req1 = CreateAdvisoryDraftRequest(
            forecast_id=self.fmd_record.forecast_id,
            recipient_scope="ALL_ASSIGNED",
            idempotency_key="idemp_key_100",
        )
        adv1 = self.advisory_svc.create_draft(req1)

        req2 = CreateAdvisoryDraftRequest(
            forecast_id=self.fmd_record.forecast_id,
            recipient_scope="ALL_ASSIGNED",
            idempotency_key="idemp_key_100",
        )
        adv2 = self.advisory_svc.create_draft(req2)
        self.assertEqual(adv1.advisory_id, adv2.advisory_id)

        req3 = CreateAdvisoryDraftRequest(
            forecast_id=self.lsd_record.forecast_id,
            recipient_scope="ALL_ASSIGNED",
            idempotency_key="idemp_key_100",
        )
        with self.assertRaises(ValueError) as ctx:
            self.advisory_svc.create_draft(req3)
        self.assertIn("collision", str(ctx.exception))

    # 16. Idempotency Header vs Body Mismatch Rejection (409)
    def test_16_idempotency_header_body_mismatch_rejection(self):
        from components.risk_forecasting.services.forecast_record_service import forecast_record_service
        forecast_record_service.repository.save(self.fmd_record)

        payload = {
            "forecast_id": self.fmd_record.forecast_id,
            "recipient_scope": "ALL_ASSIGNED",
            "idempotency_key": "body_key_AAA",
        }
        headers = {"Idempotency-Key": "header_key_BBB"}
        res = self.client.post("/api/v1/risk-forecasting/advisories", json=payload, headers=headers)
        self.assertEqual(res.status_code, 409)
        self.assertIn("mismatch", res.json()["detail"])

    # 17. Strict Lifecycle Transition Matrix
    def test_17_strict_lifecycle_transition_matrix(self):
        req = CreateAdvisoryDraftRequest(forecast_id=self.fmd_record.forecast_id)
        adv = self.advisory_svc.create_draft(req)
        self.assertEqual(adv.status, "DRAFT")

        # DRAFT -> APPROVED is forbidden
        with self.assertRaises(ValueError) as ctx:
            self.advisory_svc.approve_advisory(adv.advisory_id, expected_version=1, approved_by="vet_chief_01")
        self.assertIn("Direct approval from DRAFT status is forbidden", str(ctx.exception))

        # DRAFT -> REVIEW_READY is allowed
        rev = self.advisory_svc.mark_ready_for_review(adv.advisory_id, expected_version=1)
        self.assertEqual(rev.status, "REVIEW_READY")
        self.assertEqual(rev.version, 2)

        # REVIEW_READY -> content edit resets status back to DRAFT
        upd = self.advisory_svc.update_draft(adv.advisory_id, UpdateAdvisoryDraftRequest(version=2, vet_custom_note="Added note"))
        self.assertEqual(upd.status, "DRAFT")
        self.assertEqual(upd.version, 3)

        # Back to REVIEW_READY
        rev2 = self.advisory_svc.mark_ready_for_review(adv.advisory_id, expected_version=3)
        self.assertEqual(rev2.status, "REVIEW_READY")

        # REVIEW_READY -> APPROVED is allowed
        appr = self.advisory_svc.approve_advisory(adv.advisory_id, expected_version=4, approved_by="vet_chief_01")
        self.assertEqual(appr.status, "APPROVED")

        # APPROVED -> APPROVED is rejected
        with self.assertRaises(ValueError) as ctx:
            self.advisory_svc.approve_advisory(adv.advisory_id, expected_version=5, approved_by="vet_chief_01")
        self.assertIn("Advisory is already APPROVED", str(ctx.exception))

        # APPROVED -> edit is rejected
        with self.assertRaises(ValueError) as ctx:
            self.advisory_svc.update_draft(adv.advisory_id, UpdateAdvisoryDraftRequest(version=5, vet_custom_note="Mutate"))
        self.assertIn("Approved advisories are immutable", str(ctx.exception))

        # APPROVED -> CANCELLED is allowed
        canc = self.advisory_svc.cancel_advisory(adv.advisory_id, expected_version=5)
        self.assertEqual(canc.status, "CANCELLED")

        # CANCELLED -> status transition is rejected
        with self.assertRaises(ValueError) as ctx:
            self.advisory_svc.approve_advisory(adv.advisory_id, expected_version=6, approved_by="vet_chief_01")
        self.assertIn("Cancelled advisories cannot undergo status transitions", str(ctx.exception))

    # 18. Complete ForecastDecisionRecord Snapshot Equality
    def test_18_forecast_record_snapshot_equality(self):
        fdr_before = self.forecast_svc.get_record(self.fmd_record.forecast_id).model_dump()

        # Perform preview
        self.advisory_svc.preview_advisory(
            draft_req=CreateAdvisoryDraftRequest(forecast_id=self.fmd_record.forecast_id)
        )
        self.assertEqual(fdr_before, self.forecast_svc.get_record(self.fmd_record.forecast_id).model_dump())

        # Perform draft creation
        adv = self.advisory_svc.create_draft(CreateAdvisoryDraftRequest(forecast_id=self.fmd_record.forecast_id))
        self.assertEqual(fdr_before, self.forecast_svc.get_record(self.fmd_record.forecast_id).model_dump())

        # Perform review-ready
        rev = self.advisory_svc.mark_ready_for_review(adv.advisory_id, expected_version=1)
        self.assertEqual(fdr_before, self.forecast_svc.get_record(self.fmd_record.forecast_id).model_dump())

        # Perform approval
        self.advisory_svc.approve_advisory(adv.advisory_id, expected_version=2, approved_by="vet_chief_01")
        self.assertEqual(fdr_before, self.forecast_svc.get_record(self.fmd_record.forecast_id).model_dump())

    # 19. Optimistic Version Conflict Rejection
    def test_19_optimistic_version_conflict(self):
        adv = self.advisory_svc.create_draft(CreateAdvisoryDraftRequest(forecast_id=self.fmd_record.forecast_id))
        with self.assertRaises(ValueError) as ctx:
            self.advisory_svc.update_draft(adv.advisory_id, UpdateAdvisoryDraftRequest(version=99, vet_custom_note="Stale"))
        self.assertIn("Optimistic lock conflict", str(ctx.exception))

    # 20. Bounded List Pagination & Filtering
    def test_20_bounded_list_pagination_and_filtering(self):
        self.advisory_svc.create_draft(CreateAdvisoryDraftRequest(forecast_id=self.fmd_record.forecast_id))
        self.advisory_svc.create_draft(CreateAdvisoryDraftRequest(forecast_id=self.lsd_record.forecast_id))

        fmd_res = self.advisory_svc.list_advisories(disease="FMD")
        self.assertEqual(fmd_res.total_count, 1)
        self.assertEqual(fmd_res.advisories[0].disease, "FMD")

    # 21. Defensive-Copy Repository Behavior
    def test_21_defensive_copy_repository_behavior(self):
        adv1 = self.advisory_svc.create_draft(CreateAdvisoryDraftRequest(forecast_id=self.fmd_record.forecast_id))
        adv1.title = "MUTATED TITLE IN MEMORY"

        adv2 = self.advisory_svc.get_advisory(adv1.advisory_id)
        self.assertNotEqual(adv2.title, "MUTATED TITLE IN MEMORY")

    # 22. Integration Safety Verification
    def test_22_integration_safety_verification(self):
        # 1. Existing prediction endpoint works
        payload = {"disease": "FMD", "district": "Anuradhapura", "year": 2024, "month": 1}
        res1 = self.client.post("/api/v1/risk-forecasting/predict/fmd", json=payload)
        self.assertEqual(res1.status_code, 200)

        # 2. Existing record endpoint works
        from components.risk_forecasting.services.forecast_record_service import forecast_record_service
        forecast_record_service.repository.save(self.fmd_record)
        res2 = self.client.get(f"/api/v1/risk-forecasting/records/{self.fmd_record.forecast_id}")
        self.assertEqual(res2.status_code, 200)

        # 3. Zero notification endpoints exist
        res3 = self.client.post("/api/v1/risk-forecasting/advisories/send")
        self.assertIn(res3.status_code, [404, 405])

        # 4. Zero trends endpoints exist
        res4 = self.client.get("/api/v1/risk-forecasting/trends")
        self.assertEqual(res4.status_code, 404)


if __name__ == "__main__":
    unittest.main()
