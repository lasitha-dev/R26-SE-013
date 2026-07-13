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
    calving_date: Optional[str] = None
    status: str = "Healthy"
    health_status: str = "Healthy"

class CattleResponse(BaseModel):
    id: str
    identifier: str
    gender: str
    dob: str
    breed: str
    weight: float
    profile_photo: Optional[str] = None
    calving_date: Optional[str] = None
    status: str
    health_status: str = "Healthy"



class DailyLogCreate(BaseModel):
    cattle_id: str = Field(..., min_length=1)
    date: str = Field(..., min_length=1)
    milk_yield: float = Field(..., ge=0.0)
    weight: float = Field(..., ge=0.1)

class DailyLogResponse(BaseModel):
    id: str
    cattle_id: str
    date: str
    milk_yield: float
    weight: float

class PredictPayload(BaseModel):
    cattle_id: str
    Breed: str
    Age_Months: int
    Weight_kg: float
    Milk_Yield_L: float
    Days_in_Milk: int
    Lactation_Stage: str
    Previous_Week_Avg_Yield: float
    Day_Minus_3_Milk: float
    Day_Minus_3_Weight: float
    Manual_Avg_Milk: Optional[float] = None
    Manual_Avg_Weight: Optional[float] = None


class PredictResponse(BaseModel):
    is_anomaly: bool


