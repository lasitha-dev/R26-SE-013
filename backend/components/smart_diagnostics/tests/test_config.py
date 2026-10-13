import os
import pytest
from pydantic import ValidationError
from components.smart_diagnostics.config import Settings

def test_settings_ignores_unrelated_mongodb_env():
    """Prove that Settings ignores unrelated MONGODB environment variables and still parses its own fields."""
    os.environ["MONGODB_URL"] = "mongodb://synthetic-test:27017"
    os.environ["MONGODB_DB_NAME"] = "synthetic_db"
    os.environ["YOLO_CONF_THRESHOLD"] = "0.75"
    
    settings = Settings()
    
    assert settings.YOLO_CONF_THRESHOLD == 0.75
    assert not hasattr(settings, "MONGODB_URL")
    
    del os.environ["MONGODB_URL"]
    del os.environ["MONGODB_DB_NAME"]
    del os.environ["YOLO_CONF_THRESHOLD"]

def test_settings_validates_declared_fields():
    """Prove that invalid values for typed fields still fail validation."""
    os.environ["YOLO_CONF_THRESHOLD"] = "not_a_float"
    
    with pytest.raises(ValidationError):
        Settings()
        
    del os.environ["YOLO_CONF_THRESHOLD"]
