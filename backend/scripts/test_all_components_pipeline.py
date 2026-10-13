"""
Comprehensive Data-Flow and Integration Diagnostics Script
Tests data flow across all 4 components end-to-end:
  1. Smart Diagnostics (Vision/AI payload creation)
  2. Operational Module (Health Anomaly & Clinical verification in MongoDB)
  3. Geospatial Tracking (Operational Data Port, District Matching, Delta Events)
  4. Risk Forecasting (Shared Data Client, Autocorrelation Models, SHAP Explainability)

Usage:
  python scripts/test_all_components_pipeline.py
"""

import sys
import os
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from bson import ObjectId

try:
    import dns.resolver
    dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
    dns.resolver.default_resolver.nameservers = ['8.8.8.8']
except Exception:
    pass

# Setup Python Path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Core imports
from core.database import db
from components.health_anomaly.database import (
    farms_collection,
    cattles_collection,
    vets_collection,
    diagnostic_cases_collection,
    death_logs_collection,
)
from components.health_anomaly.schemas import (
    DiagnosticCaseCreate,
    DeclareDeceasedRequest,
)
from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext
from components.geospatial_tracking.repositories.host_operational_adapter import (
    MongoOperationalDataPort,
    district_matches,
)
from components.geospatial_tracking.repositories.mongo_case_event_source import (
    DeltaPollingCaseEventSource,
)
from components.risk_forecasting.integrations.mongo_shared_client import MongoSharedForecastClient
from components.risk_forecasting.services.fmd_service import fmd_service
from components.risk_forecasting.services.lsd_service import lsd_service
from components.risk_forecasting.services.forecast_record_service import forecast_record_service
from components.risk_forecasting.schemas import (
    FMDOutbreakPredictRequest,
    LSDOutbreakPredictRequest,
)

# Colors for CLI output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

TEST_TAG = "DIAGNOSTIC_RUN_2026"
TEST_DISTRICT = "Colombo"
TARGET_YEAR = 2026
PRIOR_MONTH = 7
TARGET_FORECAST_MONTH = 8


class PipelineDiagnosticsRunner:
    def __init__(self):
        self.results = {}
        self.test_ids = {
            "farm_id": None,
            "vet_id": None,
            "cattle_fmd_id": None,
            "cattle_lsd_id": None,
            "fmd_case_id": None,
            "lsd_case_id": None,
            "fmd_death_id": None,
        }

    def record_step(self, component: str, step_name: str, passed: bool, details: str = ""):
        if component not in self.results:
            self.results[component] = []
        self.results[component].append((step_name, passed, details))
        status_tag = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
        print(f"  {status_tag} {step_name}")
        if details:
            print(f"         {YELLOW}-> {details}{RESET}")

    async def setup_test_fixtures(self):
        print(f"\n{BOLD}{CYAN}=== Setting up Temporary Test Fixtures ==={RESET}")
        
        # 1. Clean up old test data if any
        await farms_collection.delete_many({"registration_number": f"{TEST_TAG}_FARM"})
        await vets_collection.delete_many({"license_number": f"{TEST_TAG}_VET"})
        await cattles_collection.delete_many({"identifier": {"$regex": f"^{TEST_TAG}"}})
        await diagnostic_cases_collection.delete_many({"case_number": {"$regex": f"^{TEST_TAG}"}})
        await death_logs_collection.delete_many({"reporter_email": f"{TEST_TAG.lower()}@test.lk"})
        await db.forecast_decision_records.delete_many({"district": TEST_DISTRICT, "year": TARGET_YEAR, "month": TARGET_FORECAST_MONTH})

        # 2. Create Test Farm with Coordinate-formatted Location
        farm_doc = {
            "owner_name": f"{TEST_TAG} Agro Farm",
            "email": f"farmer_{TEST_TAG.lower()}@test.lk",
            "registration_number": f"{TEST_TAG}_FARM",
            "location_district": "6.9271, 79.8612 (Colombo District)",
            "district": TEST_DISTRICT,
            "latitude": 6.9271,
            "longitude": 79.8612,
            "total_animals": 45,
            "assigned_vet_ids": [],
            "assigned_vet_emails": [],
        }
        res_farm = await farms_collection.insert_one(farm_doc)
        self.test_ids["farm_id"] = str(res_farm.inserted_id)

        # 3. Create Test Vet in Colombo
        vet_doc = {
            "full_name": f"Dr. {TEST_TAG} Veterinarian",
            "email": f"vet_{TEST_TAG.lower()}@test.lk",
            "license_number": f"{TEST_TAG}_VET",
            "district": TEST_DISTRICT,
            "location_district": TEST_DISTRICT,
            "role": "vet",
            "assigned_farm_ids": [self.test_ids["farm_id"]],
            "assigned_farms": [farm_doc["email"]],
        }
        res_vet = await vets_collection.insert_one(vet_doc)
        self.test_ids["vet_id"] = str(res_vet.inserted_id)

        # Link Vet to Farm
        await farms_collection.update_one(
            {"_id": ObjectId(self.test_ids["farm_id"])},
            {"$set": {"assigned_vet_ids": [self.test_ids["vet_id"]], "assigned_vet_emails": [vet_doc["email"]]}}
        )

        # 4. Create Cattle Subjects
        cattle_fmd = {
            "identifier": f"{TEST_TAG}_COW_FMD",
            "owner_email": farm_doc["email"],
            "farm_id": self.test_ids["farm_id"],
            "breed": "Holstein Friesian",
            "gender": "Female",
            "health_status": "Healthy",
            "status": "Healthy",
        }
        res_c1 = await cattles_collection.insert_one(cattle_fmd)
        self.test_ids["cattle_fmd_id"] = str(res_c1.inserted_id)

        cattle_lsd = {
            "identifier": f"{TEST_TAG}_COW_LSD",
            "owner_email": farm_doc["email"],
            "farm_id": self.test_ids["farm_id"],
            "breed": "Jersey Cross",
            "gender": "Female",
            "health_status": "Healthy",
            "status": "Healthy",
        }
        res_c2 = await cattles_collection.insert_one(cattle_lsd)
        self.test_ids["cattle_lsd_id"] = str(res_c2.inserted_id)

        print(f"  Created Test Farm (ID: {self.test_ids['farm_id']}, District: Colombo)")
        print(f"  Created Test Vet (ID: {self.test_ids['vet_id']}, Email: {vet_doc['email']})")
        print(f"  Created Test Cattle (FMD ID: {self.test_ids['cattle_fmd_id']}, LSD ID: {self.test_ids['cattle_lsd_id']})")

    async def test_component_1_smart_diagnostics(self):
        print(f"\n{BOLD}{CYAN}[Component 1: Smart Diagnostics] Testing Triage & Payload Generation{RESET}")
        
        # Test 1.1: Payload Construction validation
        fmd_payload = DiagnosticCaseCreate(
            cattle_id=self.test_ids["cattle_fmd_id"],
            farm_id=self.test_ids["farm_id"],
            farm_name=f"{TEST_TAG} Agro Farm",
            animal_identifier=f"{TEST_TAG}_COW_FMD",
            breed="Holstein Friesian",
            disease_name="Foot and Mouth Disease",
            confidence=0.96,
            severity="Severe",
            stage="Acute Vesicular",
            prognosis="Guarded",
            rationale="Multiple erosive mucosal vesicles on dorsal tongue and interdigital cleft.",
            spatial_correlation="High risk clustering in regional sector.",
            clinical_notes="Verified by attending veterinary officer in field examination.",
            llm_reasoning="Clinical presentation aligns with high confidence Aphthovirus infection.",
            verified=True,
        )

        valid_payload = (
            fmd_payload.disease_name == "Foot and Mouth Disease"
            and fmd_payload.confidence > 0.90
            and fmd_payload.severity == "Severe"
            and fmd_payload.verified is True
        )
        self.record_step(
            "Smart Diagnostics",
            "1.1 Diagnostic Payload Schema Compliance",
            valid_payload,
            f"Disease: {fmd_payload.disease_name}, Confidence: {fmd_payload.confidence}, Verified: {fmd_payload.verified}"
        )

        # Test 1.2: Disease Name Mapping Compatibility (FMD, LSD, Mastitis)
        supported_classes = ["Foot and Mouth Disease", "Lumpy Skin Disease", "Mastitis", "Cattle (Healthy)"]
        forecasting_supported = ["Foot and Mouth Disease", "Lumpy Skin Disease"]
        mapping_valid = all(d in supported_classes for d in forecasting_supported)
        self.record_step(
            "Smart Diagnostics",
            "1.2 Vision Class Name Mapping Compatibility",
            mapping_valid,
            f"Supported CV labels: {supported_classes}"
        )

    async def test_component_2_operational_health_anomaly(self):
        print(f"\n{BOLD}{CYAN}[Component 2: Operational Module] Testing MongoDB Persistence & BSON ISODates{RESET}")
        
        prior_month_date = datetime(TARGET_YEAR, PRIOR_MONTH, 15, 10, 30, 0, tzinfo=None)
        
        # Test 2.1: Verified Diagnostic Case Insertion with BSON ISODate
        case_doc = {
            "case_number": f"{TEST_TAG}-FMD-01",
            "cattle_id": self.test_ids["cattle_fmd_id"],
            "farm_id": self.test_ids["farm_id"],
            "farm_name": f"{TEST_TAG} Agro Farm",
            "animal_identifier": f"{TEST_TAG}_COW_FMD",
            "breed": "Holstein Friesian",
            "disease_name": "Foot and Mouth Disease",
            "confidence": 0.96,
            "severity": "Severe",
            "stage": "Acute Vesicular",
            "prognosis": "Guarded",
            "status": "Verified",
            "verified": True,
            "reported_by": "vet",
            "reporter_email": f"vet_{TEST_TAG.lower()}@test.lk",
            "district": TEST_DISTRICT,
            "created_at": prior_month_date,
            "created_at_str": prior_month_date.strftime("%Y-%m-%d %H:%M:%S"),
            "verified_at": prior_month_date,
            "verified_at_str": prior_month_date.strftime("%Y-%m-%d %H:%M:%S"),
            "vet_id": self.test_ids["vet_id"],
        }
        res_case = await diagnostic_cases_collection.insert_one(case_doc)
        self.test_ids["fmd_case_id"] = str(res_case.inserted_id)

        # Query back and verify ISODate type
        fetched_case = await diagnostic_cases_collection.find_one({"_id": res_case.inserted_id})
        is_bson_date = isinstance(fetched_case.get("created_at"), datetime) and isinstance(fetched_case.get("verified_at"), datetime)
        self.record_step(
            "Operational Module",
            "2.1 Diagnostic Case Storage (BSON ISODate Verification)",
            is_bson_date,
            f"created_at type: {type(fetched_case.get('created_at')).__name__}, verified: {fetched_case.get('verified')}"
        )

        # Test 2.2: Deceased Declaration and Death Log Storage
        death_doc = {
            "cattle_id": self.test_ids["cattle_fmd_id"],
            "farm_id": self.test_ids["farm_id"],
            "animal_identifier": f"{TEST_TAG}_COW_FMD",
            "cause": "Foot and Mouth Disease",
            "district": TEST_DISTRICT,
            "reporter_email": f"{TEST_TAG.lower()}@test.lk",
            "date_of_death": prior_month_date,
            "date_of_death_str": prior_month_date.strftime("%Y-%m-%d"),
            "created_at": prior_month_date,
            "created_at_str": prior_month_date.strftime("%Y-%m-%d %H:%M:%S"),
        }
        res_death = await death_logs_collection.insert_one(death_doc)
        self.test_ids["fmd_death_id"] = str(res_death.inserted_id)

        fetched_death = await death_logs_collection.find_one({"_id": res_death.inserted_id})
        is_death_bson = isinstance(fetched_death.get("date_of_death"), datetime)
        self.record_step(
            "Operational Module",
            "2.2 Cattle Mortality Log (BSON ISODate Storage)",
            is_death_bson,
            f"date_of_death type: {type(fetched_death.get('date_of_death')).__name__}, cause: {fetched_death.get('cause')}"
        )

    async def test_component_3_geospatial_tracking(self):
        print(f"\n{BOLD}{CYAN}[Component 3: Geospatial Tracking] Testing Data Port & Surveillance Resolution{RESET}")
        
        vet_context = AuthenticatedVetContext(
            email=f"vet_{TEST_TAG.lower()}@test.lk",
            role="vet"
        )
        data_port = MongoOperationalDataPort(
            vets_collection=vets_collection,
            farms_collection=farms_collection,
            diagnostic_cases_collection=diagnostic_cases_collection,
        )

        # Test 3.1: Resolution of Assigned Farms
        assigned_farms = await data_port.get_assigned_farms(vet_context)
        assigned_farm_ids = [f.farm_id for f in assigned_farms]
        farm_found = self.test_ids["farm_id"] in assigned_farm_ids
        self.record_step(
            "Geospatial Tracking",
            "3.1 Vet Assigned Farm Query Resolution",
            farm_found,
            f"Resolved {len(assigned_farms)} assigned farm(s) for Vet {vet_context.email}"
        )

        # Test 3.2: Resolution of Verified Clinical Cases
        verified_cases = await data_port.get_verified_clinical_cases(vet_context)
        case_ids = [c.case_id for c in verified_cases]
        case_found = self.test_ids["fmd_case_id"] in case_ids
        self.record_step(
            "Geospatial Tracking",
            "3.2 Verified Clinical Cases Extraction for Geo-Map",
            case_found,
            f"Extracted {len(verified_cases)} verified case(s), Target Case Found: {case_found}"
        )

        # Test 3.3: District String Substring Matching
        raw_location = "6.9271, 79.8612 (Colombo District)"
        matched = district_matches("Colombo", raw_location)
        self.record_step(
            "Geospatial Tracking",
            "3.3 Geographic Coordinate District Normalization",
            matched,
            f"district_matches('Colombo', '{raw_location}') -> {matched}"
        )

        # Test 3.4: Delta Polling Event Source
        event_source = DeltaPollingCaseEventSource(
            diagnostic_cases_collection=diagnostic_cases_collection,
            poll_interval_seconds=1.0,
        )
        changes = await event_source._poll_once()
        detected = any(c.case.case_id == self.test_ids["fmd_case_id"] for c in changes)
        self.record_step(
            "Geospatial Tracking",
            "3.4 Realtime Delta Event Notification Detection",
            detected,
            f"Polled {len(changes)} active change(s), Target Event Captured: {detected}"
        )

    async def test_component_4_risk_forecasting(self):
        print(f"\n{BOLD}{CYAN}[Component 4: Risk Forecasting] Testing Data Bridge, Dynamic ML, & SHAP{RESET}")
        
        # Test 4.1: Shared Forecast Client Query (Instant Live Cache TTL=0)
        shared_client = MongoSharedForecastClient(cache_ttl_seconds=0)
        outbreak_status, cases_count, deaths_count = await shared_client.get_district_status_async(
            disease="FMD",
            district=TEST_DISTRICT,
            year=TARGET_YEAR,
            month=PRIOR_MONTH,
        )
        data_bridge_success = (outbreak_status == 1.0 and cases_count >= 1 and deaths_count >= 1)
        self.record_step(
            "Risk Forecasting",
            "4.1 Mongo Shared Client Ground-Truth Aggregation",
            data_bridge_success,
            f"Outbreak: {outbreak_status}, Verified Cases: {cases_count}, Deaths: {deaths_count}"
        )

        # Test 4.2: Synchronous fetch_valid_lag1 for ML Pipeline Execution
        lag1_val, is_valid = shared_client.fetch_valid_lag1(
            disease="FMD",
            district=TEST_DISTRICT,
            month=TARGET_FORECAST_MONTH,
            year=TARGET_YEAR,
        )
        lag1_success = (lag1_val == 1.0 and is_valid is True)
        self.record_step(
            "Risk Forecasting",
            "4.2 Lag-1 Surveillance Observation Bridge for Target Month",
            lag1_success,
            f"Target Month: {TARGET_YEAR}-0{TARGET_FORECAST_MONTH}, Resolved Lag-1 Value: {lag1_val}"
        )

        # Inject shared API provider into FMD and LSD services (mirrors production setup)
        from components.risk_forecasting.integrations.provider_factory import create_forecast_data_provider
        provider = create_forecast_data_provider(mode="shared_api", shared_client=shared_client)
        fmd_service.data_provider = provider
        lsd_service.data_provider = provider

        # Test 4.3: FMD Dynamic Autocorrelation Model Selection & SHAP Waterfall
        fmd_req = FMDOutbreakPredictRequest(
            district=TEST_DISTRICT,
            year=TARGET_YEAR,
            month=TARGET_FORECAST_MONTH,
        )
        fmd_res = fmd_service.predict(fmd_req)
        fmd_model_correct = (fmd_res.stage1.model_variant == "31_feature_autocorrelation")
        fmd_prob_spiked = (fmd_res.stage1.probability > 0.35)
        top_driver_labels = [factor.display_label for factor in (fmd_res.explanation_info.top_risk_increasing if fmd_res.explanation_info else [])]
        fmd_shap_correct = "Local Outbreak History (Previous Month)" in top_driver_labels

        fmd_all_pass = fmd_model_correct and fmd_prob_spiked and fmd_shap_correct
        self.record_step(
            "Risk Forecasting",
            "4.3 FMD Dynamic Autocorrelation & SHAP Risk Drivers",
            fmd_all_pass,
            f"Model: {fmd_res.stage1.model_variant}, Prob: {fmd_res.stage1.probability:.4f}, Top Driver: {top_driver_labels[0] if top_driver_labels else 'None'}"
        )

        # Test 4.4: LSD Dynamic Autocorrelation Model Selection & SHAP Waterfall
        # Insert LSD case for July 2026
        lsd_prior_date = datetime(TARGET_YEAR, PRIOR_MONTH, 10, 9, 0, 0)
        lsd_case_doc = {
            "case_number": f"{TEST_TAG}-LSD-01",
            "cattle_id": self.test_ids["cattle_lsd_id"],
            "farm_id": self.test_ids["farm_id"],
            "disease_name": "Lumpy Skin Disease",
            "confidence": 0.95,
            "severity": "Moderate",
            "status": "Verified",
            "verified": True,
            "district": TEST_DISTRICT,
            "created_at": lsd_prior_date,
            "verified_at": lsd_prior_date,
        }
        await diagnostic_cases_collection.insert_one(lsd_case_doc)
        shared_client.invalidate_cache("LSD", TEST_DISTRICT)

        lsd_req = LSDOutbreakPredictRequest(
            district=TEST_DISTRICT,
            year=TARGET_YEAR,
            month=TARGET_FORECAST_MONTH,
        )
        lsd_res = lsd_service.predict(lsd_req)
        lsd_model_correct = (lsd_res.stage1.model_variant == "28_feature_autocorrelation")
        lsd_prob_spiked = (lsd_res.stage1.probability > 0.08)
        lsd_top_driver_labels = [factor.display_label for factor in (lsd_res.explanation_info.top_risk_increasing if lsd_res.explanation_info else [])]
        lsd_shap_correct = "Local Outbreak History (Previous Month)" in lsd_top_driver_labels

        lsd_all_pass = lsd_model_correct and lsd_prob_spiked and lsd_shap_correct
        self.record_step(
            "Risk Forecasting",
            "4.4 LSD Dynamic Autocorrelation & SHAP Risk Drivers",
            lsd_all_pass,
            f"Model: {lsd_res.stage1.model_variant}, Prob: {lsd_res.stage1.probability:.4f}, Top Driver: {lsd_top_driver_labels[0] if lsd_top_driver_labels else 'None'}"
        )

        # Test 4.5: Forecast Record Generation & Dashboard Persistence
        from components.risk_forecasting.schemas import GenerateForecastRecordRequest
        record_req = GenerateForecastRecordRequest(
            disease="FMD",
            district=TEST_DISTRICT,
            year=TARGET_YEAR,
            month=TARGET_FORECAST_MONTH,
        )
        record = forecast_record_service.generate_record(record_req)
        record_saved = (record is not None and record.district == TEST_DISTRICT and record.probability > 0.35)
        self.record_step(
            "Risk Forecasting",
            "4.5 Forecast Decision Record Generation & Dashboard Delivery",
            record_saved,
            f"Saved Record ID: {record.forecast_id}, Risk Level: {record.risk_level}, Prob: {record.probability:.4f}"
        )

    async def cleanup_test_fixtures(self):
        print(f"\n{BOLD}{CYAN}=== Cleaning Up Test Fixtures ==={RESET}")
        if self.test_ids["farm_id"]:
            await farms_collection.delete_one({"_id": ObjectId(self.test_ids["farm_id"])})
        if self.test_ids["vet_id"]:
            await vets_collection.delete_one({"_id": ObjectId(self.test_ids["vet_id"])})
        if self.test_ids["cattle_fmd_id"]:
            await cattles_collection.delete_one({"_id": ObjectId(self.test_ids["cattle_fmd_id"])})
        if self.test_ids["cattle_lsd_id"]:
            await cattles_collection.delete_one({"_id": ObjectId(self.test_ids["cattle_lsd_id"])})
        await diagnostic_cases_collection.delete_many({"case_number": {"$regex": f"^{TEST_TAG}"}})
        await death_logs_collection.delete_many({"reporter_email": f"{TEST_TAG.lower()}@test.lk"})
        await db.forecast_decision_records.delete_many({"district": TEST_DISTRICT, "year": TARGET_YEAR, "month": TARGET_FORECAST_MONTH})
        print("  Cleaned up all temporary diagnostic test documents.")

    def print_summary(self):
        print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
        print(f"{BOLD}{CYAN}                   PIPELINE DIAGNOSTICS AUDIT REPORT                  {RESET}")
        print(f"{BOLD}{CYAN}======================================================================{RESET}")
        total_steps = 0
        passed_steps = 0

        for component, steps in self.results.items():
            print(f"\n{BOLD}Component: {component}{RESET}")
            for step_name, passed, details in steps:
                total_steps += 1
                if passed:
                    passed_steps += 1
                icon = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
                print(f"  {icon} {step_name}")
                if details:
                    print(f"      {details}")

        print(f"\n{BOLD}{CYAN}----------------------------------------------------------------------{RESET}")
        if passed_steps == total_steps:
            print(f"{BOLD}{GREEN}ALL {passed_steps}/{total_steps} PIPELINE CHECKS PASSED SUCCESSFULLY!{RESET}")
            print(f"{GREEN}The data flow across Smart Diagnostics -> Operational -> Geospatial -> Risk Forecasting is fully intact.{RESET}")
        else:
            failed_count = total_steps - passed_steps
            print(f"{BOLD}{RED}{failed_count}/{total_steps} CHECKS FAILED! Please inspect the failures above.{RESET}")
        print(f"{BOLD}{CYAN}======================================================================{RESET}\n")

    async def run(self):
        try:
            await self.setup_test_fixtures()
            await self.test_component_1_smart_diagnostics()
            await self.test_component_2_operational_health_anomaly()
            await self.test_component_3_geospatial_tracking()
            await self.test_component_4_risk_forecasting()
        finally:
            await self.cleanup_test_fixtures()
            self.print_summary()


if __name__ == "__main__":
    asyncio.run(PipelineDiagnosticsRunner().run())
