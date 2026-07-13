from fastapi import APIRouter, HTTPException, status, Header
from typing import Optional
import jwt
from core.security import JWT_SECRET, JWT_ALGORITHM, get_password_hash, verify_password, create_access_token
from components.health_anomaly.database import farms_collection, cattles_collection, daily_logs_collection, breed_settings_collection
from components.health_anomaly.schemas import FarmRegister, FarmLogin, TokenResponse, CattleCreate, CattleResponse, DailyLogCreate, DailyLogResponse

router = APIRouter()

# Helper function to decode JWT token and retrieve logged-in farm email
async def get_current_user_email(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token."
        )
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token credentials."
            )
        return email
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is expired or invalid."
        )

# Helper function to propagate the most recent weight log to cattle details
async def propagate_latest_weight(cattle_id: str):
    from bson import ObjectId
    if not ObjectId.is_valid(cattle_id):
        return
    
    # Sort by date descending, then ID descending to find the latest recorded entry
    recent_log = await daily_logs_collection.find_one(
        {"cattle_id": cattle_id},
        sort=[("date", -1), ("_id", -1)]
    )
    if recent_log:
        await cattles_collection.update_one(
            {"_id": ObjectId(cattle_id)},
            {"$set": {"weight": recent_log["weight"]}}
        )

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_farm(farm_data: FarmRegister):
    # Check if the email already exists
    existing_farm = await farms_collection.find_one({"email": farm_data.email})
    if existing_farm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A farm registration with this email address already exists."
        )
    
    # Hash password and serialize schema
    hashed_password = get_password_hash(farm_data.password)
    farm_doc = farm_data.model_dump()
    farm_doc["password"] = hashed_password
    
    # Insert document
    try:
        await farms_collection.insert_one(farm_doc)
        return {"message": "Farm registered successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during registration: {str(e)}"
        )

@router.post("/login", response_model=TokenResponse)
async def login_farm(credentials: FarmLogin):
    # Find farm by email
    farm = await farms_collection.find_one({"email": credentials.email})
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )
    
    # Verify password
    if not verify_password(credentials.password, farm["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )
    
    # Generate access token
    token_data = {
        "sub": farm["email"],
        "owner_name": farm["owner_name"]
    }
    access_token = create_access_token(data=token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "owner_name": farm["owner_name"],
        "email": farm["email"],
        "veterinarian_name": farm["veterinarian_name"]
    }

@router.post("/cattle", status_code=status.HTTP_201_CREATED)
async def create_cattle(cattle_data: CattleCreate):
    try:
        doc = cattle_data.model_dump()
        result = await cattles_collection.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        # remove mongo internal _id field
        doc.pop("_id", None)
        return doc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving cattle: {str(e)}"
        )

@router.get("/cattle", response_model=list[CattleResponse])
async def list_cattle():
    try:
        cursor = cattles_collection.find({})
        cattles = []
        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            doc.pop("_id", None)
            cattles.append(doc)
        return cattles


    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while retrieving cattle list: {str(e)}"
        )

from bson import ObjectId

@router.get("/cattle/{id}", response_model=CattleResponse)
async def get_cattle(id: str):
    try:
        if not ObjectId.is_valid(id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cattle ID format."
            )
        doc = await cattles_collection.find_one({"_id": ObjectId(id)})
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cattle not found."
            )
        doc["id"] = str(doc["_id"])
        doc.pop("_id", None)
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while retrieving cattle details: {str(e)}"
        )

@router.post("/daily-logs", response_model=DailyLogResponse, status_code=status.HTTP_201_CREATED)
async def create_daily_log(log_data: DailyLogCreate):
    # Check for duplicate daily log entry
    existing_log = await daily_logs_collection.find_one({
        "cattle_id": log_data.cattle_id,
        "date": log_data.date
    })
    if existing_log:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A daily log entry already exists for this animal on this date."
        )

    try:
        from bson import ObjectId
        doc = log_data.model_dump()
        result = await daily_logs_collection.insert_one(doc)
        
        # Propagate latest weight
        await propagate_latest_weight(log_data.cattle_id)
        
        doc["id"] = str(result.inserted_id)
        doc.pop("_id", None)
        return doc
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving daily log: {str(e)}"
        )

@router.post("/daily-logs/bulk", status_code=status.HTTP_201_CREATED)
async def create_daily_logs_bulk(logs_data: list[DailyLogCreate]):
    try:
        from bson import ObjectId
        if not logs_data:
            return {"message": "No logs provided.", "count": 0}
        
        docs = [log.model_dump() for log in logs_data]
        result = await daily_logs_collection.insert_many(docs)
        
        # Update weights for all affected cattle
        affected_cattle = set(log.cattle_id for log in logs_data)
        for cattle_id in affected_cattle:
            await propagate_latest_weight(cattle_id)
                
        return {
            "message": f"Successfully imported {len(result.inserted_ids)} logs and updated cattle weights.",
            "count": len(result.inserted_ids)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during bulk import: {str(e)}"
        )

@router.get("/cattle/{id}/daily-logs", response_model=list[DailyLogResponse])
async def get_cattle_daily_logs(id: str):
    try:
        cursor = daily_logs_collection.find({"cattle_id": id}).sort("date", 1)
        logs = []
        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            doc.pop("_id", None)
            logs.append(doc)
        return logs
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while retrieving daily logs: {str(e)}"
        )

@router.get("/daily-logs", response_model=list[DailyLogResponse])
async def list_daily_logs():
    try:
        cursor = daily_logs_collection.find({}).sort("date", -1)
        logs = []
        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            doc.pop("_id", None)
            logs.append(doc)
        return logs
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while listing daily logs: {str(e)}"
        )

@router.put("/daily-logs/{id}", response_model=DailyLogResponse)
async def update_daily_log(id: str, log_data: DailyLogCreate):
    try:
        from bson import ObjectId
        if not ObjectId.is_valid(id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid daily log ID format."
            )
        update_doc = log_data.model_dump()
        result = await daily_logs_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            {"$set": update_doc},
            return_document=True
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Daily log entry not found."
            )
            
        # Propagate latest weight
        await propagate_latest_weight(log_data.cattle_id)
            
        result["id"] = str(result["_id"])
        result.pop("_id", None)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while updating daily log: {str(e)}"
        )

@router.put("/cattle/{id}", response_model=CattleResponse)
async def update_cattle(id: str, cattle_data: CattleCreate):
    try:
        from bson import ObjectId
        if not ObjectId.is_valid(id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cattle ID format."
            )
        update_doc = cattle_data.model_dump()
        result = await cattles_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            {"$set": update_doc},
            return_document=True
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cattle not found."
            )
        result["id"] = str(result["_id"])
        result.pop("_id", None)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while updating cattle details: {str(e)}"
        )

@router.delete("/daily-logs/{id}", status_code=status.HTTP_200_OK)
async def delete_daily_log(id: str):
    try:
        from bson import ObjectId
        if not ObjectId.is_valid(id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid daily log ID format."
            )
        
        # 1. Fetch log entry to find cattle_id before deleting
        log_entry = await daily_logs_collection.find_one({"_id": ObjectId(id)})
        if not log_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Daily log entry not found."
            )
        
        cattle_id = log_entry["cattle_id"]

        # 2. Delete the log entry
        result = await daily_logs_collection.delete_one({"_id": ObjectId(id)})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Daily log entry not found."
            )
        
        # 3. Propagate latest weight to cattle
        await propagate_latest_weight(cattle_id)
        
        return {"message": "Daily log deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during daily log deletion: {str(e)}"
        )

@router.delete("/cattle/{id}", status_code=status.HTTP_200_OK)
async def delete_cattle(id: str):
    try:
        from bson import ObjectId
        if not ObjectId.is_valid(id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cattle ID format."
            )
        # Delete cattle record
        result = await cattles_collection.delete_one({"_id": ObjectId(id)})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cattle not found."
            )
        
        # Clean up associated daily logs
        await daily_logs_collection.delete_many({"cattle_id": id})
        
        return {"message": "Cattle and all associated logs deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during cattle deletion: {str(e)}"
        )

# ─── User Profile & Settings Endpoints ────────────────────────────────────────

@router.get("/user/profile")
async def get_user_profile(authorization: Optional[str] = Header(None)):
    email = await get_current_user_email(authorization)
    farm = await farms_collection.find_one({"email": email})
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm profile not found."
        )
    return {
        "owner_name": farm.get("owner_name"),
        "email": farm.get("email"),
        "location_district": farm.get("location_district"),
        "registration_number": farm.get("registration_number"),
        "veterinarian_name": farm.get("veterinarian_name"),
        "profile_photo": farm.get("profile_photo")
    }

@router.put("/user/profile")
async def update_user_profile(profile_data: dict, authorization: Optional[str] = Header(None)):
    email = await get_current_user_email(authorization)
    
    update_fields = {}
    if "owner_name" in profile_data:
        update_fields["owner_name"] = profile_data["owner_name"]
    if "veterinarian_name" in profile_data:
        update_fields["veterinarian_name"] = profile_data["veterinarian_name"]
    if "profile_photo" in profile_data:
        update_fields["profile_photo"] = profile_data["profile_photo"]
        
    if not update_fields:
        return {"message": "No changes submitted."}
        
    try:
        await farms_collection.update_one(
            {"email": email},
            {"$set": update_fields}
        )
        return {"message": "Profile updated successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while updating profile: {str(e)}"
        )

@router.put("/user/change-password")
async def change_password(pass_data: dict, authorization: Optional[str] = Header(None)):
    email = await get_current_user_email(authorization)
    
    current_pwd = pass_data.get("current_password")
    new_pwd = pass_data.get("new_password")
    
    if not current_pwd or not new_pwd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current and new password are required."
        )
        
    farm = await farms_collection.find_one({"email": email})
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm profile not found."
        )
        
    # Verify current password
    if not verify_password(current_pwd, farm["password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password."
        )
        
    # Hash new password and save
    hashed = get_password_hash(new_pwd)
    try:
        await farms_collection.update_one(
            {"email": email},
            {"$set": {"password": hashed}}
        )
        return {"message": "Password changed successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while changing password: {str(e)}"
        )

# ─── AI Anomaly Detection Prediction & Breed Settings Endpoints ──────────────

import os
import joblib
import pandas as pd
from bson import ObjectId
from components.health_anomaly.schemas import PredictPayload, PredictResponse

MODEL_PATH = os.path.join(os.path.dirname(__file__), "adrs_persistent_monitoring_model_final1.pkl")
loaded_model = None

def get_predict_model():
    global loaded_model
    if loaded_model is None:
        if not os.path.exists(MODEL_PATH):
            raise RuntimeError(f"Pickle model file not found at {MODEL_PATH}")
        loaded_model = joblib.load(MODEL_PATH)
    return loaded_model

@router.post("/monitor/predict", response_model=PredictResponse)
async def predict_health_anomaly(payload: PredictPayload, authorization: Optional[str] = Header(None)):
    try:
        email = None
        if authorization:
            try:
                email = await get_current_user_email(authorization)
            except Exception:
                pass

        model = get_predict_model()
        
        # 1. Fetch custom overrides if logged in
        custom_milk = None
        custom_weight = None
        if email:
            custom_setting = await breed_settings_collection.find_one({"farm_email": email, "breed": payload.Breed})
            if custom_setting:
                custom_milk = custom_setting.get("avg_milk")
                custom_weight = custom_setting.get("avg_weight")
        
        # Determine Breed defaults if manual values are null
        breed_defaults = {
            "Holstein-Friesian": {"milk": 25.0, "weight": 600.0},
            "Jersey": {"milk": 18.0, "weight": 450.0},
            "Ayrshire": {"milk": 20.0, "weight": 500.0},
            "Brown_Swiss": {"milk": 22.0, "weight": 580.0},
            "Sahiwal": {"milk": 12.0, "weight": 420.0},
            "Gir": {"milk": 14.0, "weight": 400.0},
            "Exotic_Local_Cross": {"milk": 10.0, "weight": 350.0},
            "Boran": {"milk": 8.0, "weight": 380.0},
            "Ankole": {"milk": 6.0, "weight": 450.0}
        }
        
        breed_info = breed_defaults.get(payload.Breed, {"milk": 15.0, "weight": 450.0})
        breed_avg_milk = custom_milk if custom_milk is not None else breed_info["milk"]
        breed_avg_weight = custom_weight if custom_weight is not None else breed_info["weight"]
        
        # 2. Compute drop percentages
        prev_avg = payload.Previous_Week_Avg_Yield if payload.Previous_Week_Avg_Yield > 0 else payload.Milk_Yield_L
        milk_drop = ((prev_avg - payload.Milk_Yield_L) / prev_avg) * 100.0 if prev_avg > 0 else 0.0
        
        prev_wt = payload.Day_Minus_3_Weight if payload.Day_Minus_3_Weight > 0 else payload.Weight_kg
        weight_drop = ((prev_wt - payload.Weight_kg) / prev_wt) * 100.0 if prev_wt > 0 else 0.0
        
        baseline_milk_drop = ((breed_avg_milk - payload.Milk_Yield_L) / breed_avg_milk) * 100.0 if breed_avg_milk > 0 else 0.0
        baseline_weight_drop = ((breed_avg_weight - payload.Weight_kg) / breed_avg_weight) * 100.0 if breed_avg_weight > 0 else 0.0
        
        # 3. Construct input feature row matching exactly model's expectations (54 features)
        feature_names = [
            'Age_Months', 'Weight_kg', 'Milk_Yield_L', 'Days_in_Milk',
            'Previous_Week_Avg_Yield', 'Breed_Avg_Milk', 'Breed_Avg_Weight',
            'Day_Minus_3_Milk', 'Day_Minus_3_Weight', 'Milk_Drop_Percent',
            'Weight_Drop_Percent', 'Baseline_Milk_Drop_Percent',
            'Baseline_Weight_Drop_Percent', 'Breed_Ankole',
            'Breed_Australian_Friesian_Sahiwal', 'Breed_Australian_Milking_Zebu',
            'Breed_Ayrshire', 'Breed_Boran', 'Breed_Brown_Swiss', 'Breed_Butana',
            'Breed_Danish_Red', 'Breed_Deoni', 'Breed_Exotic_Local_Cross',
            'Breed_Fleckvieh', 'Breed_Gangatiri', 'Breed_Gir', 'Breed_Girolando',
            'Breed_Guernsey', 'Breed_Hariana', 'Breed_Holstein-Friesian',
            'Breed_Holstein_Zebu_Cross', 'Breed_Illawarra_Shorthorn', 'Breed_Jersey',
            'Breed_Jersey_Zebu_Cross', 'Breed_Kankrej', 'Breed_Kenana',
            'Breed_Krishna_Valley', 'Breed_Milking_Shorthorn', 'Breed_Montbeliarde',
            'Breed_NDama', 'Breed_Normande', 'Breed_Norwegian_Red', 'Breed_Ongole',
            'Breed_Rathi', 'Breed_Red_Poll_Africa', 'Breed_Red_Sindhi', 'Breed_Sahiwal',
            'Breed_Simmental', 'Breed_Tharparkar', 'Breed_Tipo_Carora',
            'Breed_White_Fulani', 'Breed_Zebu_Cross_Brazil', 'Lactation_Stage_Late',
            'Lactation_Stage_Mid'
        ]
        
        row = {f: 0.0 for f in feature_names}
        row['Age_Months'] = float(payload.Age_Months)
        row['Weight_kg'] = float(payload.Weight_kg)
        row['Milk_Yield_L'] = float(payload.Milk_Yield_L)
        row['Days_in_Milk'] = float(payload.Days_in_Milk)
        row['Previous_Week_Avg_Yield'] = float(payload.Previous_Week_Avg_Yield)
        row['Breed_Avg_Milk'] = float(breed_avg_milk)
        row['Breed_Avg_Weight'] = float(breed_avg_weight)
        row['Day_Minus_3_Milk'] = float(payload.Day_Minus_3_Milk)
        row['Day_Minus_3_Weight'] = float(payload.Day_Minus_3_Weight)
        row['Milk_Drop_Percent'] = float(milk_drop)
        row['Weight_Drop_Percent'] = float(weight_drop)
        row['Baseline_Milk_Drop_Percent'] = float(baseline_milk_drop)
        row['Baseline_Weight_Drop_Percent'] = float(baseline_weight_drop)
        
        # Set breed one-hot column
        breed_col = f"Breed_{payload.Breed}"
        if breed_col in row:
            row[breed_col] = 1.0
            
        # Set lactation stage one-hot column
        stage_col = f"Lactation_Stage_{payload.Lactation_Stage}"
        if stage_col in row:
            row[stage_col] = 1.0
            
        df = pd.DataFrame([row], columns=feature_names)
        prediction = model.predict(df)[0]
        
        is_anomaly = bool(prediction == 1 or prediction == "1")
        
        # Update cattle status inside database
        new_status = "Alert" if is_anomaly else "Healthy"
        if ObjectId.is_valid(payload.cattle_id):
            await cattles_collection.update_one(
                {"_id": ObjectId(payload.cattle_id)},
                {"$set": {"health_status": new_status, "status": new_status}}
            )

        return {"is_anomaly": is_anomaly}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference error: {str(e)}"
        )

@router.post("/cattle/{id}/dismiss-alert")
async def dismiss_alert(id: str, authorization: Optional[str] = Header(None)):
    await get_current_user_email(authorization)
    try:
        if not ObjectId.is_valid(id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cattle ID format."
            )
        result = await cattles_collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"health_status": "Healthy", "status": "Healthy"}}
        )
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cattle not found."
            )
        return {"message": "Alert dismissed. Cattle status set to Healthy."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while dismissing alert: {str(e)}"
        )

@router.get("/user/breed-settings")
async def get_breed_settings(authorization: Optional[str] = Header(None)):
    email = await get_current_user_email(authorization)
    try:
        cursor = breed_settings_collection.find({"farm_email": email})
        settings = []
        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            doc.pop("_id", None)
            settings.append(doc)
        return settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while loading breed defaults: {str(e)}"
        )

@router.post("/user/breed-settings")
async def save_breed_settings(settings_data: dict, authorization: Optional[str] = Header(None)):
    email = await get_current_user_email(authorization)
    breed = settings_data.get("breed")
    avg_milk = settings_data.get("avg_milk")
    avg_weight = settings_data.get("avg_weight")
    
    if not breed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Breed name is required."
        )
        
    try:
        await breed_settings_collection.update_one(
            {"farm_email": email, "breed": breed},
            {"$set": {
                "avg_milk": float(avg_milk) if avg_milk is not None else None,
                "avg_weight": float(avg_weight) if avg_weight is not None else None
            }},
            upsert=True
        )
        return {"message": f"Breed settings for {breed} saved successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving breed settings: {str(e)}"
        )

@router.delete("/user/breed-settings/{breed}")
async def reset_breed_settings(breed: str, authorization: Optional[str] = Header(None)):
    email = await get_current_user_email(authorization)
    try:
        await breed_settings_collection.delete_one({"farm_email": email, "breed": breed})
        return {"message": f"Breed settings for {breed} reset to defaults successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while deleting breed settings: {str(e)}"
        )


