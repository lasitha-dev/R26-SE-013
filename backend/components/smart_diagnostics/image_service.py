import io
import base64
from typing import List
from PIL import Image


def open_image_from_bytes(raw: bytes) -> Image.Image:
    return Image.open(io.BytesIO(raw)).convert("RGB")


def crop_image(image: Image.Image, bbox: List[float]) -> Image.Image:
    x1, y1, x2, y2 = bbox
    return image.crop((int(x1), int(y1), int(x2), int(y2)))


def encode_image_base64(image: Image.Image, format: str = "JPEG") -> str:
    buf = io.BytesIO()
    image.save(buf, format=format)
    return base64.b64encode(buf.getvalue()).decode("utf-8")
