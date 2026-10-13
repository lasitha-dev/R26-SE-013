from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal, Union
from datetime import datetime

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
    role: Literal["vet", "daph"] = "vet"
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
    role: Literal["vet", "daph"] = "vet"
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
    death_date: Optional[str] = None
    death_cause: Optional[Literal["FMD", "LSD", "Other"]] = None

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
    death_date: Optional[str] = None
    death_cause: Optional[Literal["FMD", "LSD", "Other"]] = None



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


class DiagnosticCaseCreate(BaseModel):
    cattle_id: Optional[str] = None
    farm_id: Optional[str] = None
    farm_name: Optional[str] = None
    animal_identifier: Optional[str] = None
    breed: Optional[str] = None
    disease_name: str
    confidence: float
    severity: Optional[str] = "Moderate"
    stage: Optional[str] = "Acute"
    prognosis: Optional[str] = "Good"
    rationale: Optional[str] = None
    spatial_correlation: Optional[str] = None
    symptoms_image: Optional[str] = None
    cropped_image: Optional[str] = None
    clinical_notes: Optional[str] = None
    llm_reasoning: Optional[str] = None
    verified: bool = False
    reported_by: Optional[str] = None
    reporter_email: Optional[str] = None
    assigned_vet_id: Optional[str] = None


class DiagnosticCaseVerifyRequest(BaseModel):
    clinical_notes: Optional[str] = None
    prescription: Optional[str] = None
    health_status: Optional[str] = None


class DiagnosticCaseResponse(BaseModel):
    id: str
    case_number: str
    cattle_id: Optional[str] = None
    farm_id: Optional[str] = None
    farm_name: Optional[str] = None
    animal_identifier: Optional[str] = None
    breed: Optional[str] = None
    disease_name: str
    confidence: float
    severity: Optional[str] = None
    stage: Optional[str] = None
    prognosis: Optional[str] = None
    rationale: Optional[str] = None
    spatial_correlation: Optional[str] = None
    symptoms_image: Optional[str] = None
    cropped_image: Optional[str] = None
    clinical_notes: Optional[str] = None
    llm_reasoning: Optional[str] = None
    status: str = "Pending Verification"
    verified: bool = False
    created_at: Union[str, datetime]
    verified_at: Optional[Union[str, datetime]] = None
    vet_id: Optional[str] = None
    vet_name: Optional[str] = None
    vet_license: Optional[str] = None
    reported_by: Optional[str] = "vet"
    reporter_email: Optional[str] = None
    assigned_vet_id: Optional[str] = None


class VetNotificationResponse(BaseModel):
    id: str
    vet_id: Optional[str] = None
    vet_email: Optional[str] = None
    type: str
    case_id: Optional[str] = None
    case_number: Optional[str] = None
    farm_name: Optional[str] = None
    animal_identifier: Optional[str] = None
    disease_name: Optional[str] = None
    severity: Optional[str] = None
    message: str
    read: bool = False
    created_at: Union[str, datetime]


class CattleDeathLog(BaseModel):
    cattle_id: str = Field(..., min_length=1)
    farm_id: str = Field(..., min_length=1)
    district: str = Field(..., min_length=1)
    cause: Literal["FMD", "LSD", "Other"]
    date_of_death: Union[str, datetime]
    reported_by_vet_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[Union[str, datetime]] = None


class CattleDeathLogResponse(BaseModel):
    id: str
    cattle_id: str
    farm_id: str
    district: str
    cause: Literal["FMD", "LSD", "Other"]
    date_of_death: Union[str, datetime]
    reported_by_vet_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[Union[str, datetime]] = None


class DeclareDeceasedRequest(BaseModel):
    cause: Literal["FMD", "LSD", "Other"]
    date_of_death: str
    notes: Optional[str] = None


class OutbreakStatusResponse(BaseModel):
    district: str
    disease: str
    year: int
    month: int
    outbreak_status: float
    cases_count: int
    deaths_count: int



