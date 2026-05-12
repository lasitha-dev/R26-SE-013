from typing import List, Dict

# Support both pydantic v1 (BaseSettings in pydantic) and
# pydantic v2 where BaseSettings was moved to pydantic-settings.
try:
    from pydantic_settings import BaseSettings
    from pydantic import Field, ConfigDict
    _PYDANTIC_V2 = True
except Exception:
    try:
        from pydantic import BaseSettings, Field
        _PYDANTIC_V2 = False
        ConfigDict = None
    except Exception as exc:  # pragma: no cover - environment issue
        raise RuntimeError(
            "pydantic BaseSettings import failed. If you are using pydantic v2, "
            "install pydantic-settings: pip install pydantic-settings"
        ) from exc


class Settings(BaseSettings):
    YOLO_MODEL_PATH: str = Field("components/smart_diagnostics/models/best.pt", env="YOLO_MODEL_PATH")
    VIT_MODEL_PATH: str = Field("components/smart_diagnostics/models/vision_transformer_cow_disease.pth", env="VIT_MODEL_PATH")
    VIT_IMAGE_SIZE: int = Field(224, env="VIT_IMAGE_SIZE")
    YOLO_CONF_THRESHOLD: float = Field(0.25, env="YOLO_CONF_THRESHOLD")
    CLASS_NAMES: List[str] = Field(default_factory=lambda: [
        "dermatophilosis",
        "fmd",
        "healthy",
        "lumpy",
        "mastitis",
        "pediculosis",
        "ringworm",
    ])
    CLASS_DISPLAY_NAMES: Dict[str, str] = Field(default_factory=lambda: {
        "dermatophilosis": "Dermatophilosis",
        "fmd": "Foot and Mouth Disease",
        "healthy": "Healthy",
        "lumpy": "Lumpy Skin Disease",
        "mastitis": "Mastitis",
        "pediculosis": "Pediculosis",
        "ringworm": "Ringworm",
    })

    if _PYDANTIC_V2:
        model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")
    else:
        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"


settings = Settings()
