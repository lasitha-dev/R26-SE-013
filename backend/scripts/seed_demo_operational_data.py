"""
Guarded CLI command to safely seed synthetic operational demo data into MongoDB.

Seeds:
- demo_farms (3 synthetic farms)
- demo_surveillance_records (8 synthetic surveillance records)
- demo_alerts (4 synthetic operational alerts)
- demo_response_tasks (5 synthetic response tasks)

Never modifies 'demo_users'.

Modes:
- Default: Dry-run mode (offline, zero network/database writes, zero secrets loaded).
- Real write: Must specify --apply.
"""

import sys
import argparse
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional

# Ensure backend package can be imported if run from CLI
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.core.demo_database_config import load_demo_database_config, DemoDatabaseConfigError, DISALLOWED_ENVS
from backend.core.demo_database_connection import DemoDatabaseConnectionManager, DemoDatabaseConnectionError
from backend.components.demo_operational.models import (
    LivestockType,
    DiseaseCode,
    EvidenceType,
    VerificationStatus,
    SourceModule,
    AlertStatus,
    AlertPriority,
    TaskType,
    TaskStatus,
    DemoFarm,
    DemoSurveillanceRecord,
    DemoAlert,
    DemoResponseTask,
)
from backend.components.demo_operational.repositories import (
    DemoFarmRepository,
    DemoSurveillanceRepository,
    DemoAlertRepository,
    DemoResponseTaskRepository,
    DemoOperationalRepositoryError,
)

TARGET_DATABASE_NAME = "r26_disease_forecasting_demo"

# Fixed deterministic UTC timestamps
BASE_TIME = datetime(2026, 8, 1, 8, 0, 0, tzinfo=timezone.utc)
TIME_1 = datetime(2026, 8, 1, 9, 0, 0, tzinfo=timezone.utc)
TIME_2 = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)
TIME_3 = datetime(2026, 8, 1, 11, 0, 0, tzinfo=timezone.utc)
TIME_4 = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
TIME_5 = datetime(2026, 8, 1, 13, 0, 0, tzinfo=timezone.utc)
TIME_6 = datetime(2026, 8, 1, 14, 0, 0, tzinfo=timezone.utc)
TIME_7 = datetime(2026, 8, 1, 15, 0, 0, tzinfo=timezone.utc)
TIME_8 = datetime(2026, 8, 1, 16, 0, 0, tzinfo=timezone.utc)


def build_synthetic_dataset() -> Tuple[
    List[DemoFarm],
    List[DemoSurveillanceRecord],
    List[DemoAlert],
    List[DemoResponseTask],
]:
    """
    Pure deterministic builder for synthetic operational records.
    Returns validated list of farms, surveillance records, alerts, and response tasks.
    Validates referential integrity before returning.
    """
    # 1. Synthetic Farms (3)
    farms = [
        DemoFarm(
            farmId="DEMO_FARM_JAFFNA_001",
            displayName="Synthetic Jaffna Cattle Farm 001",
            district="Jaffna",
            ownerUserId="DEMO_USER_FARMER_JAFFNA",
            assignedVetUserIds=["DEMO_USER_VET_NORTH"],
            livestockTypes=[LivestockType.CATTLE, LivestockType.BUFFALO],
            active=True,
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoFarm(
            farmId="DEMO_FARM_KILINOCHCHI_001",
            displayName="Synthetic Kilinochchi Cattle Farm 001",
            district="Kilinochchi",
            ownerUserId="DEMO_USER_REFERENCE_OWNER_KILINOCHCHI",
            assignedVetUserIds=["DEMO_USER_VET_NORTH"],
            livestockTypes=[LivestockType.CATTLE],
            active=True,
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoFarm(
            farmId="DEMO_FARM_VAVUNIYA_001",
            displayName="Synthetic Vavuniya Mixed Farm 001",
            district="Vavuniya",
            ownerUserId="DEMO_USER_REFERENCE_OWNER_VAVUNIYA",
            assignedVetUserIds=["DEMO_USER_VET_NORTH"],
            livestockTypes=[LivestockType.CATTLE, LivestockType.GOAT],
            active=True,
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
    ]

    # 2. Synthetic Surveillance Records (8)
    surveillance_records = [
        DemoSurveillanceRecord(
            surveillanceRecordId="DEMO_SURV_JAFFNA_FMD_001",
            farmId="DEMO_FARM_JAFFNA_001",
            district="Jaffna",
            diseaseCode=DiseaseCode.FMD,
            observedAt=TIME_1,
            evidenceType=EvidenceType.FARMER_REPORT,
            verificationStatus=VerificationStatus.REPORTED,
            sourceModule=SourceModule.SYNTHETIC_FARM_REPORTING,
            sourceRecordId="DEMO_SOURCE_FARMER_REPORT_001",
            summary="Synthetic farmer report of elevated fever in cattle herd",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoSurveillanceRecord(
            surveillanceRecordId="DEMO_SURV_JAFFNA_LSD_001",
            farmId="DEMO_FARM_JAFFNA_001",
            district="Jaffna",
            diseaseCode=DiseaseCode.LSD,
            observedAt=TIME_2,
            evidenceType=EvidenceType.AI_IMAGE_SCREENING,
            verificationStatus=VerificationStatus.AI_SCREENED,
            sourceModule=SourceModule.SYNTHETIC_AI_DIAGNOSIS,
            sourceRecordId="DEMO_SOURCE_AI_IMAGE_001",
            sourceProvidedSeverityLabel="SUSPECTED_NODULES",
            summary="Synthetic AI screening flagged suspected skin lesions, unverified",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoSurveillanceRecord(
            surveillanceRecordId="DEMO_SURV_JAFFNA_FMD_002",
            farmId="DEMO_FARM_JAFFNA_001",
            district="Jaffna",
            diseaseCode=DiseaseCode.FMD,
            observedAt=TIME_3,
            evidenceType=EvidenceType.VET_FIELD_OBSERVATION,
            verificationStatus=VerificationStatus.VET_REVIEWED,
            sourceModule=SourceModule.SYNTHETIC_VETERINARY_SERVICE,
            sourceRecordId="DEMO_SOURCE_VET_OBS_001",
            summary="Synthetic veterinary field observation confirmed clinical oral lesions",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoSurveillanceRecord(
            surveillanceRecordId="DEMO_SURV_KILINOCHCHI_LSD_001",
            farmId="DEMO_FARM_KILINOCHCHI_001",
            district="Kilinochchi",
            diseaseCode=DiseaseCode.LSD,
            observedAt=TIME_4,
            evidenceType=EvidenceType.LAB_RESULT,
            verificationStatus=VerificationStatus.LAB_CONFIRMED,
            sourceModule=SourceModule.SYNTHETIC_LAB_SERVICE,
            sourceRecordId="DEMO_SOURCE_LAB_RESULT_001",
            summary="Synthetic lab PCR test positive for LSD viral DNA",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoSurveillanceRecord(
            surveillanceRecordId="DEMO_SURV_VAVUNIYA_FMD_001",
            farmId="DEMO_FARM_VAVUNIYA_001",
            district="Vavuniya",
            diseaseCode=DiseaseCode.FMD,
            observedAt=TIME_5,
            evidenceType=EvidenceType.VET_FIELD_OBSERVATION,
            verificationStatus=VerificationStatus.REJECTED,
            sourceModule=SourceModule.SYNTHETIC_VETERINARY_SERVICE,
            sourceRecordId="DEMO_SOURCE_VET_OBS_002",
            summary="Synthetic vet examination rejected suspected FMD; non-infectious trauma",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoSurveillanceRecord(
            surveillanceRecordId="DEMO_SURV_VAVUNIYA_LSD_001",
            farmId="DEMO_FARM_VAVUNIYA_001",
            district="Vavuniya",
            diseaseCode=DiseaseCode.LSD,
            observedAt=TIME_6,
            evidenceType=EvidenceType.WELLNESS_MONITORING,
            verificationStatus=VerificationStatus.REPORTED,
            sourceModule=SourceModule.SYNTHETIC_WELLNESS_MANAGEMENT,
            sourceRecordId="DEMO_SOURCE_WELLNESS_001",
            summary="Synthetic automated wellness monitoring detected feed intake drop",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoSurveillanceRecord(
            surveillanceRecordId="DEMO_SURV_KILINOCHCHI_FMD_001",
            farmId="DEMO_FARM_KILINOCHCHI_001",
            district="Kilinochchi",
            diseaseCode=DiseaseCode.FMD,
            observedAt=TIME_7,
            evidenceType=EvidenceType.AI_IMAGE_SCREENING,
            verificationStatus=VerificationStatus.AI_SCREENED,
            sourceModule=SourceModule.SYNTHETIC_AI_DIAGNOSIS,
            sourceRecordId="DEMO_SOURCE_AI_IMAGE_002",
            summary="Synthetic AI screening flagged possible lameness, pending vet review",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoSurveillanceRecord(
            surveillanceRecordId="DEMO_SURV_JAFFNA_LSD_002",
            farmId="DEMO_FARM_JAFFNA_001",
            district="Jaffna",
            diseaseCode=DiseaseCode.LSD,
            observedAt=TIME_8,
            evidenceType=EvidenceType.LAB_RESULT,
            verificationStatus=VerificationStatus.LAB_CONFIRMED,
            sourceModule=SourceModule.SYNTHETIC_LAB_SERVICE,
            sourceRecordId="DEMO_SOURCE_LAB_RESULT_002",
            summary="Synthetic lab serology confirmed LSD antibody titers",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
    ]

    # 3. Synthetic Alerts (4)
    alerts = [
        DemoAlert(
            alertId="DEMO_ALERT_JAFFNA_FMD_001",
            district="Jaffna",
            diseaseCode=DiseaseCode.FMD,
            status=AlertStatus.OPEN,
            priority=AlertPriority.HIGH,
            issuedAt=TIME_3,
            closedAt=None,
            sourceSurveillanceRecordIds=["DEMO_SURV_JAFFNA_FMD_002"],
            affectedFarmIds=["DEMO_FARM_JAFFNA_001"],
            title="Synthetic High Risk FMD Operational Alert - Jaffna",
            message="Synthetic high-priority FMD alert triggered by vet field observation",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoAlert(
            alertId="DEMO_ALERT_KILINOCHCHI_LSD_001",
            district="Kilinochchi",
            diseaseCode=DiseaseCode.LSD,
            status=AlertStatus.ACKNOWLEDGED,
            priority=AlertPriority.MEDIUM,
            issuedAt=TIME_4,
            closedAt=None,
            sourceSurveillanceRecordIds=["DEMO_SURV_KILINOCHCHI_LSD_001"],
            affectedFarmIds=["DEMO_FARM_KILINOCHCHI_001"],
            title="Synthetic Medium Risk LSD Operational Alert - Kilinochchi",
            message="Synthetic lab-confirmed LSD alert acknowledged by veterinary team",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoAlert(
            alertId="DEMO_ALERT_JAFFNA_LSD_001",
            district="Jaffna",
            diseaseCode=DiseaseCode.LSD,
            status=AlertStatus.OPEN,
            priority=AlertPriority.MEDIUM,
            issuedAt=TIME_8,
            closedAt=None,
            sourceSurveillanceRecordIds=["DEMO_SURV_JAFFNA_LSD_002"],
            affectedFarmIds=["DEMO_FARM_JAFFNA_001"],
            title="Synthetic Medium Risk LSD Operational Alert - Jaffna",
            message="Synthetic lab-confirmed LSD record created open alert",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoAlert(
            alertId="DEMO_ALERT_VAVUNIYA_FMD_001",
            district="Vavuniya",
            diseaseCode=DiseaseCode.FMD,
            status=AlertStatus.CLOSED,
            priority=AlertPriority.LOW,
            issuedAt=TIME_5,
            closedAt=TIME_6,
            sourceSurveillanceRecordIds=["DEMO_SURV_VAVUNIYA_FMD_001"],
            affectedFarmIds=["DEMO_FARM_VAVUNIYA_001"],
            title="Synthetic Low Risk FMD Review Alert - Vavuniya",
            message="Synthetic FMD alert closed following negative vet review",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
    ]

    # 4. Synthetic Response Tasks (5)
    tasks = [
        DemoResponseTask(
            responseTaskId="DEMO_TASK_JAFFNA_FMD_REVIEW_001",
            alertId="DEMO_ALERT_JAFFNA_FMD_001",
            assignedOfficerUserId="DEMO_USER_VET_NORTH",
            district="Jaffna",
            farmId="DEMO_FARM_JAFFNA_001",
            taskType=TaskType.FIELD_REVIEW,
            status=TaskStatus.ASSIGNED,
            dueAt=TIME_4,
            completedAt=None,
            notes="Synthetic task: Conduct urgent field review of reported FMD symptoms",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoResponseTask(
            responseTaskId="DEMO_TASK_KILINOCHCHI_LSD_SAMPLE_001",
            alertId="DEMO_ALERT_KILINOCHCHI_LSD_001",
            assignedOfficerUserId="DEMO_USER_VET_NORTH",
            district="Kilinochchi",
            farmId="DEMO_FARM_KILINOCHCHI_001",
            taskType=TaskType.SAMPLE_COLLECTION,
            status=TaskStatus.IN_PROGRESS,
            dueAt=TIME_5,
            completedAt=None,
            notes="Synthetic task: Collect confirmation blood samples for LSD lab verification",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoResponseTask(
            responseTaskId="DEMO_TASK_JAFFNA_LSD_BIOSECURITY_001",
            alertId="DEMO_ALERT_JAFFNA_LSD_001",
            assignedOfficerUserId="DEMO_USER_VET_NORTH",
            district="Jaffna",
            farmId="DEMO_FARM_JAFFNA_001",
            taskType=TaskType.BIOSECURITY_GUIDANCE,
            status=TaskStatus.ASSIGNED,
            dueAt=TIME_8,
            completedAt=None,
            notes="Synthetic task: Provide biosecurity guidance and vector control instructions",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoResponseTask(
            responseTaskId="DEMO_TASK_VAVUNIYA_FMD_FOLLOWUP_001",
            alertId="DEMO_ALERT_VAVUNIYA_FMD_001",
            assignedOfficerUserId="DEMO_USER_VET_NORTH",
            district="Vavuniya",
            farmId="DEMO_FARM_VAVUNIYA_001",
            taskType=TaskType.FOLLOW_UP,
            status=TaskStatus.COMPLETED,
            dueAt=TIME_6,
            completedAt=TIME_7,
            notes="Synthetic task: Completed follow-up inspection confirming healthy animals",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
        DemoResponseTask(
            responseTaskId="DEMO_TASK_VAVUNIYA_LSD_REVIEW_001",
            alertId="DEMO_ALERT_VAVUNIYA_FMD_001",
            assignedOfficerUserId="DEMO_USER_VET_NORTH",
            district="Vavuniya",
            farmId="DEMO_FARM_VAVUNIYA_001",
            taskType=TaskType.FIELD_REVIEW,
            status=TaskStatus.CANCELLED,
            dueAt=TIME_7,
            completedAt=None,
            notes="Synthetic task: Field review cancelled as initial report was rejected",
            createdAt=BASE_TIME,
            updatedAt=BASE_TIME,
        ),
    ]

    # Referential Integrity Checks
    farm_ids = {f.farmId for f in farms}
    surv_ids = {s.surveillanceRecordId for s in surveillance_records}
    alert_ids = {a.alertId for a in alerts}

    for s in surveillance_records:
        if s.farmId not in farm_ids:
            raise ValueError(f"Surveillance record {s.surveillanceRecordId} references non-existent farm {s.farmId}")

    for a in alerts:
        for fid in a.affectedFarmIds:
            if fid not in farm_ids:
                raise ValueError(f"Alert {a.alertId} references non-existent farm {fid}")
        for sid in a.sourceSurveillanceRecordIds:
            if sid not in surv_ids:
                raise ValueError(f"Alert {a.alertId} references non-existent surveillance record {sid}")

    for t in tasks:
        if t.alertId not in alert_ids:
            raise ValueError(f"Task {t.responseTaskId} references non-existent alert {t.alertId}")
        if t.farmId and t.farmId not in farm_ids:
            raise ValueError(f"Task {t.responseTaskId} references non-existent farm {t.farmId}")
        if t.assignedOfficerUserId != "DEMO_USER_VET_NORTH":
            raise ValueError(f"Task {t.responseTaskId} assigned officer must be DEMO_USER_VET_NORTH")

    return farms, surveillance_records, alerts, tasks


def load_env_file(dotenv_path: Path) -> Dict[str, str]:
    """Safely loads variables from .env file into a dictionary without logging values."""
    env_vars = {}
    if dotenv_path.is_file():
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                env_vars[k] = v
    return env_vars


def parse_args(args_list: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Guarded CLI command to seed synthetic operational demo data into MongoDB."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute real database writes (default is dry-run mode).",
    )
    return parser.parse_args(args_list)


async def run_operational_seed(apply: bool, env_dict: Optional[Dict[str, str]] = None) -> int:
    """
    Main async seeding routine for synthetic operational data.
    - Dry-run mode (apply=False): Offline dry-run. Zero database, network, secret operations.
    - Apply mode (apply=True): Connects to demo MongoDB, ensures indexes, and idempotently inserts/updates records.
    Returns 0 on success, 1 on failure.
    """
    if env_dict is None:
        dotenv_path = REPO_ROOT / ".env"
        merged_env = dict(load_env_file(dotenv_path))
        import os
        merged_env.update(os.environ)
        env_dict = merged_env

    # 1. Non-secret Environment & Config Validation
    app_env = env_dict.get("APP_ENV", "development").strip().lower()
    if app_env in DISALLOWED_ENVS or app_env == "test":
        print(f"[ERROR] Seeding refused in environment '{app_env}'. Allowed: development, demo.", file=sys.stderr)
        return 1

    raw_enabled = env_dict.get("FORECASTING_DEMO_ENABLED")
    if raw_enabled is None or raw_enabled.strip().lower() in ("false", "0", "no", "off"):
        print("[ERROR] Seeding refused: FORECASTING_DEMO_ENABLED is false.", file=sys.stderr)
        return 1
    elif raw_enabled.strip().lower() not in ("true", "1", "yes", "on"):
        print("[ERROR] Demo database configuration error: Invalid boolean value for FORECASTING_DEMO_ENABLED.", file=sys.stderr)
        return 1

    raw_db_name = env_dict.get("FORECASTING_DEMO_DATABASE")
    if not raw_db_name or raw_db_name.strip() != TARGET_DATABASE_NAME:
        print(f"[ERROR] Seeding refused: Database name must be '{TARGET_DATABASE_NAME}'.", file=sys.stderr)
        return 1

    # 2. Build and Validate Dataset Deterministically
    try:
        farms, surv_records, alerts, tasks = build_synthetic_dataset()
    except Exception as exc:
        print(f"[ERROR] Dataset validation failed ({exc.__class__.__name__}): {exc}", file=sys.stderr)
        return 1

    # 3. Offline Dry-Run Mode
    if not apply:
        print("==================================================")
        print("  Operational Demo Seeding Mode: DRY-RUN (No Database Writes)")
        print(f"  Target Database: {TARGET_DATABASE_NAME}")
        print("==================================================")
        print("  Planned Collections & Records:")
        print(f"  - demo_farms ({len(farms)} records):")
        for f in farms:
            print(f"    * {f.farmId} ({f.displayName}, {f.district})")
        print(f"  - demo_surveillance_records ({len(surv_records)} records):")
        for s in surv_records:
            print(f"    * {s.surveillanceRecordId} ({s.diseaseCode.value}, {s.verificationStatus.value})")
        print(f"  - demo_alerts ({len(alerts)} records):")
        for a in alerts:
            print(f"    * {a.alertId} ({a.diseaseCode.value}, {a.status.value}, {a.priority.value})")
        print(f"  - demo_response_tasks ({len(tasks)} records):")
        for t in tasks:
            print(f"    * {t.responseTaskId} ({t.taskType.value}, {t.status.value})")
        print("--------------------------------------------------")
        print(
            f"Summary: Planned farms={len(farms)}, surveillance={len(surv_records)}, "
            f"alerts={len(alerts)}, tasks={len(tasks)} | Database writes=0, Network calls=0"
        )
        print("==================================================")
        return 0

    # 4. Real Apply Mode: Connect to MongoDB demo database
    try:
        db_config = load_demo_database_config(env_dict)
    except DemoDatabaseConfigError as e:
        print(f"[ERROR] Demo database configuration error: {e}", file=sys.stderr)
        return 1

    conn_mgr = DemoDatabaseConnectionManager(db_config)
    try:
        await conn_mgr.connect()
        await conn_mgr.ping()
        db = conn_mgr.get_database()
    except DemoDatabaseConnectionError as e:
        print(f"[ERROR] Database connection failed: {e}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[ERROR] Unexpected database connection error ({exc.__class__.__name__})", file=sys.stderr)
        return 1

    try:
        farm_repo = DemoFarmRepository(db)
        surv_repo = DemoSurveillanceRepository(db)
        alert_repo = DemoAlertRepository(db)
        task_repo = DemoResponseTaskRepository(db)

        # Ensure Indexes
        await farm_repo.ensure_indexes()
        await surv_repo.ensure_indexes()
        await alert_repo.ensure_indexes()
        await task_repo.ensure_indexes()
        print("[INFO] Operational collection indexes verified and ensured successfully.")

        now_utc = datetime.now(timezone.utc)

        # Helper for comparing non-timestamp fields
        def _content_equal(m1: Any, m2: Any) -> bool:
            d1 = m1.model_dump()
            d2 = m2.model_dump()
            for key in ("createdAt", "updatedAt"):
                d1.pop(key, None)
                d2.pop(key, None)
            return d1 == d2

        # 4a. Process Farms
        farms_created = 0
        farms_updated = 0
        farms_unchanged = 0
        for farm in farms:
            existing = await farm_repo.find_by_farm_id(farm.farmId)
            if existing is None:
                await farm_repo.insert_farm(farm)
                farms_created += 1
                print(f"  [+] Farm '{farm.farmId}': CREATED")
            elif _content_equal(existing, farm):
                farms_unchanged += 1
                print(f"  [=] Farm '{farm.farmId}': UNCHANGED")
            else:
                updated_farm = farm.model_copy(update={"createdAt": existing.createdAt, "updatedAt": now_utc})
                await farm_repo.replace_farm(updated_farm, upsert=False)
                farms_updated += 1
                print(f"  [*] Farm '{farm.farmId}': UPDATED")

        # 4b. Process Surveillance Records
        surv_created = 0
        surv_updated = 0
        surv_unchanged = 0
        for surv in surv_records:
            existing = await surv_repo.find_by_record_id(surv.surveillanceRecordId)
            if existing is None:
                await surv_repo.insert_record(surv)
                surv_created += 1
                print(f"  [+] Surveillance Record '{surv.surveillanceRecordId}': CREATED")
            elif _content_equal(existing, surv):
                surv_unchanged += 1
                print(f"  [=] Surveillance Record '{surv.surveillanceRecordId}': UNCHANGED")
            else:
                updated_surv = surv.model_copy(update={"createdAt": existing.createdAt, "updatedAt": now_utc})
                await surv_repo.replace_record(updated_surv, upsert=False)
                surv_updated += 1
                print(f"  [*] Surveillance Record '{surv.surveillanceRecordId}': UPDATED")

        # 4c. Process Alerts
        alerts_created = 0
        alerts_updated = 0
        alerts_unchanged = 0
        for alert in alerts:
            existing = await alert_repo.find_by_alert_id(alert.alertId)
            if existing is None:
                await alert_repo.insert_alert(alert)
                alerts_created += 1
                print(f"  [+] Alert '{alert.alertId}': CREATED")
            elif _content_equal(existing, alert):
                alerts_unchanged += 1
                print(f"  [=] Alert '{alert.alertId}': UNCHANGED")
            else:
                updated_alert = alert.model_copy(update={"createdAt": existing.createdAt, "updatedAt": now_utc})
                await alert_repo.replace_alert(updated_alert, upsert=False)
                alerts_updated += 1
                print(f"  [*] Alert '{alert.alertId}': UPDATED")

        # 4d. Process Response Tasks
        tasks_created = 0
        tasks_updated = 0
        tasks_unchanged = 0
        for task in tasks:
            existing = await task_repo.find_by_task_id(task.responseTaskId)
            if existing is None:
                await task_repo.insert_task(task)
                tasks_created += 1
                print(f"  [+] Task '{task.responseTaskId}': CREATED")
            elif _content_equal(existing, task):
                tasks_unchanged += 1
                print(f"  [=] Task '{task.responseTaskId}': UNCHANGED")
            else:
                updated_task = task.model_copy(update={"createdAt": existing.createdAt, "updatedAt": now_utc})
                await task_repo.replace_task(updated_task, upsert=False)
                tasks_updated += 1
                print(f"  [*] Task '{task.responseTaskId}': UPDATED")

        total_created = farms_created + surv_created + alerts_created + tasks_created
        total_updated = farms_updated + surv_updated + alerts_updated + tasks_updated
        total_unchanged = farms_unchanged + surv_unchanged + alerts_unchanged + tasks_unchanged

        print("--------------------------------------------------")
        print(f"Farms Summary: Created={farms_created}, Updated={farms_updated}, Unchanged={farms_unchanged}")
        print(f"Surveillance Summary: Created={surv_created}, Updated={surv_updated}, Unchanged={surv_unchanged}")
        print(f"Alerts Summary: Created={alerts_created}, Updated={alerts_updated}, Unchanged={alerts_unchanged}")
        print(f"Tasks Summary: Created={tasks_created}, Updated={tasks_updated}, Unchanged={tasks_unchanged}")
        print(f"Total Operational Records: Created={total_created}, Updated={total_updated}, Unchanged={total_unchanged}")
        print("==================================================")
        return 0

    except DemoOperationalRepositoryError as e:
        print(f"[ERROR] Repository error during operational seeding: {e}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[ERROR] Unexpected error during operational seeding ({exc.__class__.__name__})", file=sys.stderr)
        return 1
    finally:
        await conn_mgr.close()


def main() -> None:
    args = parse_args()
    exit_code = asyncio.run(run_operational_seed(apply=args.apply))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
