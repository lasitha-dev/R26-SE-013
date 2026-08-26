"""
Local CLI utility to check connectivity to the optional Disease Forecasting demo database.

Executes only a single MongoDB admin ping ('ping': 1) command.
Does NOT create, read, update, or delete any records or collections.
Exits with code 0 on success and non-zero code on failure.
"""

import sys
import asyncio
from pathlib import Path

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

# Ensure backend package can be imported regardless of execution working directory
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Load root .env file if present
ENV_PATH = ROOT_DIR / ".env"
if HAS_DOTENV and ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)

from backend.core.demo_database_config import load_demo_database_config, DemoDatabaseConfigError
from backend.core.demo_database_connection import (
    DemoDatabaseConnectionManager,
    DemoDatabaseConnectionError,
)


async def check_demo_database_connectivity() -> int:
    """
    Validates configuration, initiates client, performs admin ping, and closes connection.
    Returns 0 on success (or when safely disabled) and 1 on error.
    """
    try:
        config = load_demo_database_config()
    except DemoDatabaseConfigError as err:
        sys.stderr.write(f"Demo database configuration error: {err}\n")
        return 1

    if not config.enabled:
        print("Demo database is currently disabled (FORECASTING_DEMO_ENABLED=false).")
        return 0

    manager = DemoDatabaseConnectionManager(config)
    try:
        await manager.connect()
        ping_success = await manager.ping()
        if ping_success:
            print("Demo database connection successful.")
            return 0
        else:
            sys.stderr.write("Demo database connection failed: Ping response unverified.\n")
            return 1
    except DemoDatabaseConnectionError as err:
        sys.stderr.write(f"Demo database connection failed: {err}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"Demo database connection failed: Unexpected error ({exc.__class__.__name__}).\n")
        return 1
    finally:
        await manager.close()


def main() -> int:
    return asyncio.run(check_demo_database_connectivity())


if __name__ == "__main__":
    sys.exit(main())
