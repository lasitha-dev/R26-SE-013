from fastapi import APIRouter, HTTPException, status
from components.health_anomaly.database import farms_collection, cattles_collection
from core.security import get_password_hash, verify_password, create_access_token
from components.health_anomaly.schemas import FarmRegister, FarmLogin, TokenResponse, CattleCreate, CattleResponse

router = APIRouter()

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
