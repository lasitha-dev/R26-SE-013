from pydantic import BaseSettings, Field
from typing import List, Dict


class Settings(BaseSettings):
    YOLO_MODEL_PATH: str = Field("models/best.pt", env="YOLO_MODEL_PATH")
    VIT_MODEL_PATH: str = Field("models/vision_transformer_cow_disease.pth", env="VIT_MODEL_PATH")
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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
