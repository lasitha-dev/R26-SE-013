"""Backend-wide pytest guard: tests that write to / delete from the real database must be opted into.

test_diagnostic_cases.py and test_farm_vet_linking.py import the application against the configured
MongoDB (Atlas in this project) and insert/delete real documents. They are skipped, without even being
imported, unless ALLOW_LIVE_DB_TESTS=1 is set deliberately.
"""

import os
from pathlib import Path

LIVE_DB_FILES = {"test_diagnostic_cases.py", "test_farm_vet_linking.py"}


def _live_db_allowed() -> bool:
    return os.environ.get("ALLOW_LIVE_DB_TESTS") == "1"


def pytest_ignore_collect(collection_path, config):
    if Path(str(collection_path)).name in LIVE_DB_FILES and not _live_db_allowed():
        return True
    return None
