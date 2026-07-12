from fastapi import APIRouter, HTTPException, status
from components.health_anomaly.database import farms_collection, cattles_collection, daily_logs_collection
from core.security import get_password_hash, verify_password, create_access_token
from components.health_anomaly.schemas import FarmRegister, FarmLogin, TokenResponse, CattleCreate, CattleResponse, DailyLogCreate, DailyLogResponse

router = APIRouter()

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

