from typing import List, Dict
from pathlib import Path
from pydantic import AliasChoices

from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict, model_validator

class Settings(BaseSettings):
    YOLO_MODEL_PATH: str = str(Path(__file__).parent / "models/yolo_smart_diag_best.pt")
    VIT_MODEL_PATH: str = str(Path(__file__).parent / "models/best_vit_model.pth")
    SEGMENTER_MODEL_PATH: str = Field(str(Path(__file__).parent / "models/mask_rcnn_cow_symptoms_refined.keras"), validation_alias=AliasChoices("SEGMENTER_MODEL_PATH", "MASK_RCNN_MODEL_PATH"))
    SEGMENTER_MANIFEST_PATH: str = str(Path(__file__).parent / "models/segmenter_manifest.json")
    SEGMENTER_THRESHOLD: float = Field(0.5, gt=0, lt=1)
    SEGMENTER_MIN_REGION_FRACTION: float = Field(15 / (224 * 224), ge=0, lt=1)
    REASONING_TIMEOUT_SECONDS: float = Field(30, gt=0, le=120)
    REASONING_MAX_RETRIES: int = Field(0, ge=0, le=2)

    @property
    def MASK_RCNN_MODEL_PATH(self):
        """Temporary configuration compatibility alias."""
        return self.SEGMENTER_MODEL_PATH
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

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def resolve_model_paths(self):
        backend = Path(__file__).resolve().parents[2]
        for name in ('YOLO_MODEL_PATH', 'VIT_MODEL_PATH', 'SEGMENTER_MODEL_PATH', 'SEGMENTER_MANIFEST_PATH'):
            value = Path(getattr(self, name))
            if not value.is_absolute():
                setattr(self, name, str(backend / value))
        return self


settings = Settings()
