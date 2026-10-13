"""
Guarded CLI command to safely seed temporary synthetic demo users into MongoDB.

Modes:
- Default: Dry-run only (performs checks and reports actions without database writes).
- Real write: Must specify --apply.

Safety guardrails:
- Refuses execution in production environments (APP_ENV='production'/'prod').
- Requires FORECASTING_DEMO_ENABLED=true and target DB 'r26_disease_forecasting_demo'.
- Strictly isolates passwords and secrets; never prints or logs sensitive values.
"""

import sys
import argparse
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional

# Ensure backend package can be imported if run from CLI
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.core.demo_database_config import load_demo_database_config, DemoDatabaseConfigError, DISALLOWED_ENVS
from backend.core.demo_database_connection import DemoDatabaseConnectionManager, DemoDatabaseConnectionError
from backend.core.demo_security import hash_password, verify_password
from backend.components.demo_auth.models import (
    Role,
    ScopeLevel,
    DemoUserDocument,
)
from backend.components.demo_auth.repository import (
    DemoUserRepository,
    DemoUserRepositoryError,
)
from backend.components.risk_forecasting.config import SRI_LANKA_DISTRICTS


TARGET_DATABASE_NAME = "r26_disease_forecasting_demo"
MIN_PASSWORD_LENGTH = 8


# Canonical Seed User Definitions
SEED_USERS = [
    {
        "userId": "DEMO_USER_FARMER_JAFFNA",
        "loginName": "demo_farmer_jaffna",
        "role": Role.FARMER,
        "password_env_var": "FORECASTING_DEMO_FARMER_PASSWORD",
        "authorization": {
            "scopeLevel": ScopeLevel.FARM,
            "registeredFarmDistrict": "Jaffna",
            "authorizedDistricts": ["Jaffna"],
            "assignedFarmIds": [],
        },
        "permissions": {
            "viewDataQuality": True,
            "viewModelTransparency": False,
            "manageAlerts": False,
            "recordResponse": False,
            "viewReports": True,
        },
    },
    {
        "userId": "DEMO_USER_VET_NORTH",
        "loginName": "demo_vet_north",
        "role": Role.VETERINARY_OFFICER,
        "password_env_var": "FORECASTING_DEMO_VET_PASSWORD",
        "authorization": {
            "scopeLevel": ScopeLevel.PROVINCE,
            "registeredFarmDistrict": None,
            "authorizedDistricts": ["Jaffna", "Kilinochchi", "Mannar", "Mullaitivu", "Vavuniya"],
            "assignedFarmIds": [
                "DEMO_FARM_JAFFNA_001",
                "DEMO_FARM_KILINOCHCHI_001",
                "DEMO_FARM_VAVUNIYA_001",
            ],
        },
        "permissions": {
            "viewDataQuality": False,
            "viewModelTransparency": True,
            "manageAlerts": True,
            "recordResponse": True,
            "viewReports": True,
        },
    },
    {
        "userId": "DEMO_USER_DAPH_OFFICIAL",
        "loginName": "demo_daph_official",
        "role": Role.DAPH_OFFICIAL,
        "password_env_var": "FORECASTING_DEMO_DAPH_PASSWORD",
        "authorization": {
            "scopeLevel": ScopeLevel.NATIONAL,
            "registeredFarmDistrict": None,
            "authorizedDistricts": list(SRI_LANKA_DISTRICTS),
            "assignedFarmIds": [],
        },
        "permissions": {
            "viewDataQuality": True,
            "viewModelTransparency": True,
            "manageAlerts": True,
            "recordResponse": True,
            "viewReports": True,
        },
    },
]


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
        description="Guarded CLI command to seed synthetic demo auth users into MongoDB."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute real database writes (default is dry-run mode).",
    )
    return parser.parse_args(args_list)


async def run_seed(apply: bool, env_dict: Optional[Dict[str, str]] = None) -> int:
    """
    Main async seeding routine.
    - Dry-run mode (apply=False): Strictly offline. Performs zero database, network, password-read,
      or hash operations. Validates only safe non-secret configuration variables.
    - Apply mode (apply=True): Guarded write execution. Requires password variables, connects/pings
      the demo MongoDB database, ensures indexes, and executes narrow idempotent updates.
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

    # 2. Offline Dry-Run Mode
    if not apply:
        print("==================================================")
        print("  Demo User Seeding Execution Mode: DRY-RUN (No Database Writes)")
        print(f"  Target Database: {TARGET_DATABASE_NAME}")
        print("  Target Collection: demo_users")
        print("==================================================")
        for user_def in SEED_USERS:
            login_name = user_def["loginName"]
            role = user_def["role"]
            print(f"  [?] Account '{login_name}' ({role.value}): WOULD CREATE OR UPDATE")
        print("--------------------------------------------------")
        print("Summary: Planned accounts=3, Database writes=0, Network calls=0")
        print("==================================================")
        return 0

    # 3. Real Apply Mode: Strict database connection & secret validation
    try:
        db_config = load_demo_database_config(env_dict)
    except DemoDatabaseConfigError as e:
        print(f"[ERROR] Demo database configuration error: {e}", file=sys.stderr)
        return 1

    passwords: Dict[str, str] = {}
    for user_def in SEED_USERS:
        var_name = user_def["password_env_var"]
        raw_pass = env_dict.get(var_name)
        if not raw_pass or not raw_pass.strip():
            print(f"[ERROR] Missing required password environment variable '{var_name}' for --apply.", file=sys.stderr)
            return 1
        if len(raw_pass.strip()) < MIN_PASSWORD_LENGTH:
            print(f"[ERROR] Password in '{var_name}' must be at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
            return 1
        passwords[user_def["userId"]] = raw_pass.strip()

    print("==================================================")
    print("  Demo User Seeding Execution Mode: REAL WRITE (--apply)")
    print(f"  Target Database: {db_config.database_name}")
    print("  Target Collection: demo_users")
    print("==================================================")

    manager = DemoDatabaseConnectionManager(db_config)
    try:
        await manager.connect()
        await manager.ping()
        db = manager.get_database()
        repo = DemoUserRepository(db)

        await repo.ensure_indexes()
        print("[INFO] Indexes verified and ensured successfully.")

        created_count = 0
        updated_count = 0
        unchanged_count = 0

        now = datetime.now(timezone.utc)

        for user_def in SEED_USERS:
            user_id = user_def["userId"]
            login_name = user_def["loginName"]
            role = user_def["role"]
            plain_pass = passwords[user_id]

            existing = await repo.find_by_user_id(user_id)

            if existing is None:
                pass_hash = hash_password(plain_pass)
                doc = DemoUserDocument(
                    schemaVersion="1.0",
                    userId=user_id,
                    loginName=login_name,
                    passwordHash=pass_hash,
                    role=role,
                    authorization=user_def["authorization"],
                    permissions=user_def["permissions"],
                    enabled=True,
                    tokenVersion=1,
                    isSynthetic=True,
                    dataOrigin="SYNTHETIC_DEMO",
                    scientificUseAllowed=False,
                    createdAt=now,
                    updatedAt=now,
                )
                await repo.insert_user(doc)
                created_count += 1
                print(f"  [+] Account '{login_name}' ({role.value}): CREATED")
            else:
                if not existing.isSynthetic or existing.dataOrigin != "SYNTHETIC_DEMO":
                    print(f"[ERROR] Target user '{user_id}' exists but lacks synthetic markers.", file=sys.stderr)
                    return 1

                pass_matches = verify_password(plain_pass, existing.passwordHash)
                contract_changed = (
                    existing.loginName != login_name or
                    existing.role != role or
                    existing.authorization.model_dump() != user_def["authorization"] or
                    existing.permissions.model_dump() != user_def["permissions"] or
                    not existing.enabled
                )

                if pass_matches and not contract_changed:
                    unchanged_count += 1
                    print(f"  [=] Account '{login_name}' ({role.value}): UNCHANGED")
                else:
                    new_hash = existing.passwordHash if pass_matches else hash_password(plain_pass)
                    updated_doc = DemoUserDocument(
                        schemaVersion="1.0",
                        userId=user_id,
                        loginName=login_name,
                        passwordHash=new_hash,
                        role=role,
                        authorization=user_def["authorization"],
                        permissions=user_def["permissions"],
                        enabled=True,
                        tokenVersion=existing.tokenVersion,
                        isSynthetic=True,
                        dataOrigin="SYNTHETIC_DEMO",
                        scientificUseAllowed=False,
                        createdAt=existing.createdAt,
                        updatedAt=now,
                    )
                    await repo.replace_user(updated_doc, upsert=False)
                    updated_count += 1
                    print(f"  [*] Account '{login_name}' ({role.value}): UPDATED")

        print("--------------------------------------------------")
        print(f"Summary: Created={created_count}, Updated={updated_count}, Unchanged={unchanged_count}")
        print("==================================================")
        return 0

    except (DemoDatabaseConnectionError, DemoUserRepositoryError) as e:
        print(f"[ERROR] Database operation failed: {e}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[ERROR] Unexpected error during seeding execution ({exc.__class__.__name__}).", file=sys.stderr)
        return 1
    finally:
        await manager.close()


def main():
    args = parse_args()
    exit_code = asyncio.run(run_seed(apply=args.apply))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
