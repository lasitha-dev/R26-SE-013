import os
from core.database import MONGODB_URL, MONGODB_DB_NAME, client, db

def test_database_configuration():
    assert "mongodb+srv://" not in MONGODB_URL
    assert MONGODB_URL == os.getenv("MONGODB_URL", "mongodb://127.0.0.1:27017")
    assert MONGODB_DB_NAME == os.getenv("MONGODB_DB_NAME", "adrs_core")
    assert db.name == MONGODB_DB_NAME
    # motor sets topology configuration internally; we ensure client connects to the expected URI
    assert str(client.topology_settings.seeds[0][0]) in MONGODB_URL or "127.0.0.1" in MONGODB_URL
