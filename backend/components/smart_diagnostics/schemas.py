from pydantic import BaseModel
from typing import List, Dict, Optional


class Detection(BaseModel):
    bbox: List[float]
    confidence: float
    class_name: str


class BoundingBoxNormalized(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class BestDetection(BaseModel):
    bbox: List[float]
    confidence: float
    bbox_normalized: BoundingBoxNormalized


class Disease(BaseModel):
    name: str
    confidence: float
    all_probabilities: Dict[str, float]


class DetectResponse(BaseModel):
    cattle_detected: bool
    detections: List[Detection]
    best_detection: Optional[BestDetection]
    disease: Optional[Disease]
    cropped_image: Optional[str]
    image_size: Optional[Dict[str, int]]
    device: Optional[str]
