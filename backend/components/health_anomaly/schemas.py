from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List

class FarmRegister(BaseModel):
    owner_name: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=4)
    location_district: str = Field(..., min_length=1)
    registration_number: Optional[str] = None
    veterinarian_name: str = Field(..., min_length=1)
    total_animals: int = Field(default=0, ge=0)
    assigned_vet_ids: List[str] = []
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class FarmLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    owner_name: str
    email: str
    veterinarian_name: str

class VetRegister(BaseModel):
    full_name: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=4)
    license_number: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=7)
    district: Optional[str] = None
    role: str = "vet"
    assigned_farms: List[str] = []
    assigned_farm_ids: List[str] = []

class VetLogin(BaseModel):
    email: EmailStr
    password: str

class VetTokenResponse(BaseModel):
    access_token: str
    token_type: str
    full_name: str
    email: str
    role: str = "vet"
    license_number: Optional[str] = None
    phone: Optional[str] = None
    district: Optional[str] = None

class VetProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    license_number: Optional[str] = None
    phone: Optional[str] = None
    district: Optional[str] = None

class VetSearchResponse(BaseModel):
    id: str
    full_name: str
    email: str
    license_number: str
    phone: Optional[str] = None
    district: Optional[str] = None
    assigned: bool = False

class AssignVetRequest(BaseModel):
    vet_id: Optional[str] = None
    vet_email: Optional[str] = None

class UnassignVetRequest(BaseModel):
    vet_id: Optional[str] = None
    vet_email: Optional[str] = None

class FarmSummaryResponse(BaseModel):
    id: str
    owner_name: str
    email: str
    location_district: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    registration_number: Optional[str] = None
    total_animals: int = 0
    alert_count: int = 0
    status: str = "Active Synchronization"

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
    bcs_score: Optional[float] = None
    last_scored_date: Optional[str] = None

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
    bcs_score: Optional[float] = None
    last_scored_date: Optional[str] = None



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


from typing import List

class TriagePredictPayload(BaseModel):
    bcs_score: float
    age_months: int
    days_in_milk: int
    breed: str
    genetic_group: str
    lactation_stage: str
    ambient_temp: List[float]
    humidity: List[float]
    thi: List[float]
    body_temp: List[float]
    milk_yield: List[float]
    water_intake: List[float]
    feed_intake: List[float]
    weight: List[float]


