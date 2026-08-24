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
    YOLO_MODEL_PATH: str = Field("components/smart_diagnostics/models/yolo_smart_diag_best.pt", env="YOLO_MODEL_PATH")
    VIT_MODEL_PATH: str = Field("components/smart_diagnostics/models/best_vit_model.pth", env="VIT_MODEL_PATH")
    MASK_RCNN_MODEL_PATH: str = Field("components/smart_diagnostics/models/mask_rcnn_cow_symptoms_refined.keras", env="MASK_RCNN_MODEL_PATH")
    VIT_IMAGE_SIZE: int = Field(224, env="VIT_IMAGE_SIZE")
    YOLO_CONF_THRESHOLD: float = Field(0.25, env="YOLO_CONF_THRESHOLD")
    CLASS_NAMES: List[str] = Field(default_factory=lambda: [
        "cattle",
        "foot_and_mouth",
        "lumpy_skin",
        "mastitis",
    ])
    CLASS_DISPLAY_NAMES: Dict[str, str] = Field(default_factory=lambda: {
        "cattle": "Cattle (Healthy)",
        "foot_and_mouth": "Foot and Mouth Disease",
        "lumpy_skin": "Lumpy Skin Disease",
        "mastitis": "Mastitis",
    })

    if _PYDANTIC_V2:
        model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")
    else:
        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"


settings = Settings()
