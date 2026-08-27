import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR.parent
DB_FILE = BASE_DIR / 'database.py'

def test_static_source_safety():
    source = DB_FILE.read_text(encoding='utf-8')
    assert "mongodb+srv://" not in source
    assert "username:password@" not in source
    assert "cluster0.8e4nq9e.mongodb.net" not in source
    assert "serverSelectionTimeoutMS=2000" in source

def test_default_environment_behavior():
    script = (
        "import os, sys\n"
        "if 'MONGODB_URL' in os.environ: del os.environ['MONGODB_URL']\n"
        "if 'MONGODB_DB_NAME' in os.environ: del os.environ['MONGODB_DB_NAME']\n"
        "from core.database import MONGODB_URL, MONGODB_DB_NAME, farms_collection, cattles_collection, vets_collection\n"
        "assert MONGODB_URL == 'mongodb://127.0.0.1:27017'\n"
        "assert MONGODB_DB_NAME == 'adrs_core'\n"
        "assert farms_collection.name == 'farms'\n"
        "assert cattles_collection.name == 'cattle'\n"
        "assert vets_collection.name == 'vets'\n"
        "print('SUCCESS_DEFAULT')\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, cwd=str(BACKEND_DIR))
    assert result.returncode == 0, f"Stdout: {result.stdout}, Stderr: {result.stderr}"
    assert "SUCCESS_DEFAULT" in result.stdout

def test_environment_override():
    script = (
        "import os, sys\n"
        "os.environ['MONGODB_URL'] = 'mongodb://127.0.0.1:27018'\n"
        "os.environ['MONGODB_DB_NAME'] = 'adrs_test_override'\n"
        "from core.database import MONGODB_URL, MONGODB_DB_NAME, farms_collection, cattles_collection, vets_collection\n"
        "assert MONGODB_URL == 'mongodb://127.0.0.1:27018'\n"
        "assert MONGODB_DB_NAME == 'adrs_test_override'\n"
        "assert farms_collection.name == 'farms'\n"
        "assert cattles_collection.name == 'cattle'\n"
        "assert vets_collection.name == 'vets'\n"
        "print('SUCCESS_OVERRIDE')\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, cwd=str(BACKEND_DIR))
    assert result.returncode == 0, f"Stdout: {result.stdout}, Stderr: {result.stderr}"
    assert "SUCCESS_OVERRIDE" in result.stdout
