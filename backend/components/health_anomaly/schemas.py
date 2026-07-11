from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class FarmRegister(BaseModel):
    owner_name: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=4)
    location_district: str = Field(..., min_length=1)
    registration_number: Optional[str] = None
    veterinarian_name: str = Field(..., min_length=1)
    total_animals: int = Field(default=0, ge=0)

class FarmLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    owner_name: str
    email: str
    veterinarian_name: str

class CattleCreate(BaseModel):
    identifier: str = Field(..., min_length=1)
    gender: str = Field(..., min_length=1)
    dob: str = Field(..., min_length=1)
    breed: str = Field(..., min_length=1)
    weight: float = Field(..., ge=0.1)
    profile_photo: Optional[str] = None
    status: str = "Healthy"

class CattleResponse(BaseModel):
    id: str
    identifier: str
    gender: str
    dob: str
    breed: str
    weight: float
    profile_photo: Optional[str] = None
    status: str
