from fastapi import APIRouter, HTTPException, status, Header, File, UploadFile, Form
from typing import Optional
import jwt
import os
import numpy as np
import base64
from datetime import datetime
from bson import ObjectId

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import tensorflow as tf
    from ultralytics import YOLO
except ImportError:
    tf = None
    YOLO = None

from core.security import JWT_SECRET, JWT_ALGORITHM, get_password_hash, verify_password, create_access_token
from components.health_anomaly.database import farms_collection, cattles_collection, daily_logs_collection, breed_settings_collection, bcs_logs_collection, vets_collection, diagnostic_cases_collection
from components.health_anomaly.schemas import (
    FarmRegister, FarmLogin, TokenResponse,
    VetRegister, VetLogin, VetTokenResponse, VetProfileUpdate,
    VetSearchResponse, AssignVetRequest, UnassignVetRequest, FarmSummaryResponse,
    CattleCreate, CattleResponse, DailyLogCreate, DailyLogResponse, TriagePredictPayload,
    DiagnosticCaseCreate, DiagnosticCaseResponse, DiagnosticCaseVerifyRequest
)

router = APIRouter()

# Global models loading for vision BCS pipeline
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YOLO_MODEL_PATH = os.path.join(BASE_DIR, "best.pt")
BCS_MODEL_PATH = os.path.join(BASE_DIR, "Cow_BCS_Final_Master.h5")
LATE_FUSION_MODEL_PATH = os.path.join(BASE_DIR, "adrs_late_fusion_model.h5")

yolo_model = None
bcs_model = None
late_fusion_model = None

def load_ai_models():
    global yolo_model, bcs_model, late_fusion_model
    if YOLO is not None:
        try:
            if os.path.exists(YOLO_MODEL_PATH):
                yolo_model = YOLO(YOLO_MODEL_PATH)
                print(f"YOLOv8 Model loaded successfully from {YOLO_MODEL_PATH}")
            else:
                print(f"YOLO model not found at {YOLO_MODEL_PATH}")
        except Exception as e:
            print(f"Error loading YOLO model: {e}")
    if tf is not None:
        try:
            if os.path.exists(BCS_MODEL_PATH):
                bcs_model = tf.keras.models.load_model(BCS_MODEL_PATH, compile=False)
                print(f"Keras BCS Model loaded successfully from {BCS_MODEL_PATH}")
            else:
                print(f"Keras BCS model not found at {BCS_MODEL_PATH}")
        except Exception as e:
            print(f"Error loading Keras BCS model: {e}")
        try:
            if os.path.exists(LATE_FUSION_MODEL_PATH):
                late_fusion_model = tf.keras.models.load_model(LATE_FUSION_MODEL_PATH, compile=False)
                print(f"Late Fusion Model loaded successfully from {LATE_FUSION_MODEL_PATH}")
            else:
                print(f"Late Fusion Model not found at {LATE_FUSION_MODEL_PATH}")
        except Exception as e:
            print(f"Error loading Late Fusion model: {e}")

# Load models once
load_ai_models()

def get_last_conv_layer(model):
    """Forcefully extract the last convolution layer by string matching, bypassing output_shape."""
    for layer in reversed(model.layers):
        if isinstance(layer, tf.keras.models.Model):
            nested_layer, nested_model = get_last_conv_layer(layer)
            if nested_layer is not None:
                return nested_layer, nested_model

        # String match works across all Keras versions and wrapper types
        layer_name = layer.name.lower()
        class_name = layer.__class__.__name__.lower()
        if 'conv' in layer_name or 'conv2d' in class_name:
            return layer, model

    return None, None


def make_gradcam_heatmap(img_array, target_model, target_layer_name, pred_index=None):
    try:
        # Keras 3 restricts .output/.inputs access on Sequential models that haven't been called yet.
        # We manually trace through layers to build a Functional extraction model instead.
        if isinstance(target_model, tf.keras.Sequential):
            inputs = tf.keras.Input(shape=target_model.input_shape[1:])
            x = inputs
            last_conv_output = None

            for layer in target_model.layers:
                x = layer(x)
                if layer.name == target_layer_name:
                    last_conv_output = x

            if last_conv_output is None:
                raise ValueError(f"Layer '{target_layer_name}' not found in Sequential model.")

            grad_model = tf.keras.Model(inputs, [last_conv_output, x])
        else:
            # Standard Functional API approach
            grad_model = tf.keras.Model(
                target_model.inputs,
                [target_model.get_layer(target_layer_name).output, target_model.output]
            )

        img_tensor = tf.cast(img_array, tf.float32)
        with tf.GradientTape() as tape:
            tape.watch(img_tensor)
            last_conv_layer_output, preds = grad_model(img_tensor)
            if pred_index is None:
                class_channel = preds[:, 0]
            else:
                class_channel = preds[:, pred_index]

        grads = tape.gradient(class_channel, last_conv_layer_output)
        if grads is None:
            print("[GRAD-CAM] Gradients evaluated to None.")
            return np.zeros((img_array.shape[1], img_array.shape[2]))

        pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
        last_conv_layer_output = last_conv_layer_output[0]
        heatmap = last_conv_layer_output @ pooled_grads[..., tf.newaxis]
        heatmap = tf.squeeze(heatmap)

        # Linear Regression heatmap magnitude extraction — tf.abs preserves negative gradient signal
        heatmap = tf.abs(heatmap)

        max_heat = tf.math.reduce_max(heatmap)
        if max_heat == 0:
            return np.zeros((img_array.shape[1], img_array.shape[2]))

        heatmap = heatmap / max_heat
        return heatmap.numpy()

    except Exception as e:
        import traceback
        print(f"[GRAD-CAM INTERNAL ERROR]: {e}")
        traceback.print_exc()
        return np.zeros((img_array.shape[1], img_array.shape[2]))


def overlay_gradcam(img, heatmap, alpha=0.4):
    heatmap = np.uint8(255 * heatmap)
    jet = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
    jet = cv2.resize(jet, (img.shape[1], img.shape[0]))
    superimposed_img = jet * alpha + img * (1 - alpha)
    superimposed_img = np.clip(superimposed_img, 0, 255).astype(np.uint8)
    return superimposed_img


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

@router.post("/vet/register", status_code=status.HTTP_201_CREATED)
async def register_vet(vet_data: VetRegister):
    # Check if the email already exists in vets collection
    existing_vet_email = await vets_collection.find_one({"email": vet_data.email})
    if existing_vet_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A veterinarian registration with this email address already exists."
        )

    # Check if license_number already exists in vets collection
    existing_vet_license = await vets_collection.find_one({"license_number": vet_data.license_number})
    if existing_vet_license:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A veterinarian with this license registration number already exists."
        )

    # Hash password and serialize schema
    hashed_password = get_password_hash(vet_data.password)
    vet_doc = vet_data.model_dump()
    vet_doc["password"] = hashed_password
    vet_doc["role"] = "vet"
    vet_doc["created_at"] = datetime.utcnow().isoformat()

    try:
        await vets_collection.insert_one(vet_doc)
        return {"message": "Veterinarian registered successfully."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error during vet registration: {str(e)}"
        )

@router.post("/vet/login", response_model=VetTokenResponse)
async def login_vet(credentials: VetLogin):
    vet = await vets_collection.find_one({"email": credentials.email})
    if not vet:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    if not verify_password(credentials.password, vet["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    token_data = {
        "sub": vet["email"],
        "full_name": vet["full_name"],
        "role": "vet",
        "license_number": vet.get("license_number", "")
    }
    access_token = create_access_token(data=token_data)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "full_name": vet["full_name"],
        "email": vet["email"],
        "role": "vet",
        "license_number": vet.get("license_number", ""),
        "phone": vet.get("phone", ""),
        "district": vet.get("district") or vet.get("location_district") or "Sri Lanka Central Jurisdiction"
    }

@router.get("/vet/profile")
async def get_vet_profile(authorization: Optional[str] = Header(None)):
    email = await get_current_user_email(authorization)
    vet = await vets_collection.find_one({"email": email})
    if not vet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Veterinarian profile not found."
        )
    return {
        "full_name": vet.get("full_name"),
        "email": vet.get("email"),
        "license_number": vet.get("license_number"),
        "phone": vet.get("phone"),
        "role": vet.get("role", "vet"),
        "district": vet.get("district") or vet.get("location_district") or "Sri Lanka Central Jurisdiction",
        "assigned_farms": vet.get("assigned_farms", []),
        "assigned_farm_ids": vet.get("assigned_farm_ids", [])
    }

@router.put("/vet/profile")
async def update_vet_profile(
    payload: VetProfileUpdate,
    authorization: Optional[str] = Header(None)
):
    email = await get_current_user_email(authorization)
    vet = await vets_collection.find_one({"email": email})
    if not vet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Veterinarian profile not found."
        )

    update_fields = {}
    if payload.full_name is not None and payload.full_name.strip():
        update_fields["full_name"] = payload.full_name.strip()
    if payload.license_number is not None and payload.license_number.strip():
        # Check if license_number is changing and if new license is taken by another vet
        new_lic = payload.license_number.strip()
        if new_lic != vet.get("license_number"):
            existing = await vets_collection.find_one({"license_number": new_lic, "email": {"$ne": email}})
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A veterinarian with this license registration number already exists."
                )
            update_fields["license_number"] = new_lic
    if payload.phone is not None:
        update_fields["phone"] = payload.phone.strip()
    if payload.district is not None:
        update_fields["district"] = payload.district.strip()
        update_fields["location_district"] = payload.district.strip()

    if update_fields:
        update_fields["updated_at"] = datetime.utcnow().isoformat()
        await vets_collection.update_one({"email": email}, {"$set": update_fields})

    updated_vet = await vets_collection.find_one({"email": email})
    return {
        "message": "Veterinarian profile updated successfully.",
        "full_name": updated_vet.get("full_name"),
        "email": updated_vet.get("email"),
        "license_number": updated_vet.get("license_number"),
        "phone": updated_vet.get("phone"),
        "district": updated_vet.get("district") or updated_vet.get("location_district") or "Sri Lanka Central Jurisdiction",
        "role": updated_vet.get("role", "vet")
    }

# ─── Farm-to-Vet Linking & Jurisdictional Management Endpoints ────────────────

@router.get("/vet/search", response_model=list[VetSearchResponse])
async def search_veterinarians(
    q: Optional[str] = None,
    district: Optional[str] = None,
    authorization: Optional[str] = Header(None)
):
    email = await get_current_user_email(authorization)
    farm = await farms_collection.find_one({"email": email})
    assigned_vet_ids = set(farm.get("assigned_vet_ids", [])) if farm else set()
    assigned_vet_emails = set(farm.get("assigned_vet_emails", [])) if farm else set()

    and_conditions = []

    if district and district.strip() and district.strip().lower() not in ["all", "all districts", ""]:
        dist_regex = {"$regex": district.strip(), "$options": "i"}
        and_conditions.append({
            "$or": [
                {"district": dist_regex},
                {"location_district": dist_regex}
            ]
        })

    if q and q.strip():
        q_clean = q.strip()
        q_regex = {"$regex": q_clean, "$options": "i"}
        and_conditions.append({
            "$or": [
                {"full_name": q_regex},
                {"email": q_regex},
                {"license_number": q_regex},
                {"phone": q_regex}
            ]
        })

    filter_query = {}
    if and_conditions:
        if len(and_conditions) == 1:
            filter_query = and_conditions[0]
        else:
            filter_query = {"$and": and_conditions}

    cursor = vets_collection.find(filter_query).limit(50)
    vets = []
    async for doc in cursor:
        vid_str = str(doc["_id"])
        is_assigned = (vid_str in assigned_vet_ids) or (doc.get("email") in assigned_vet_emails)
        vets.append(VetSearchResponse(
            id=vid_str,
            full_name=doc.get("full_name", ""),
            email=doc.get("email", ""),
            license_number=doc.get("license_number", ""),
            phone=doc.get("phone"),
            district=doc.get("district") or doc.get("location_district") or "Sri Lanka Central Jurisdiction",
            assigned=is_assigned
        ))
    return vets

@router.post("/farms/assign-vet")
async def assign_veterinarian(
    payload: AssignVetRequest,
    authorization: Optional[str] = Header(None)
):
    farm_email = await get_current_user_email(authorization)
    farm = await farms_collection.find_one({"email": farm_email})
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm profile not found."
        )

    # Find target veterinarian
    vet_query = {}
    if payload.vet_id and ObjectId.is_valid(payload.vet_id):
        vet_query["_id"] = ObjectId(payload.vet_id)
    elif payload.vet_email:
        vet_query["email"] = payload.vet_email
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid vet_id or vet_email."
        )

    vet = await vets_collection.find_one(vet_query)
    if not vet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Veterinarian profile not found."
        )

    vet_id_str = str(vet["_id"])
    farm_id_str = str(farm["_id"])

    # Link vet to farm (idempotent via $addToSet)
    await farms_collection.update_one(
        {"_id": farm["_id"]},
        {
            "$addToSet": {
                "assigned_vet_ids": vet_id_str,
                "assigned_vet_emails": vet["email"]
            },
            "$set": {
                "veterinarian_name": vet.get("full_name", farm.get("veterinarian_name", ""))
            }
        }
    )

    # Link farm to vet (idempotent via $addToSet)
    await vets_collection.update_one(
        {"_id": vet["_id"]},
        {
            "$addToSet": {
                "assigned_farm_ids": farm_id_str,
                "assigned_farms": farm["email"]
            }
        }
    )

    return {
        "message": f"Dr. {vet.get('full_name')} assigned to your farm successfully.",
        "vet_id": vet_id_str,
        "vet_name": vet.get("full_name"),
        "vet_email": vet.get("email")
    }

@router.post("/farms/unassign-vet")
async def unassign_veterinarian(
    payload: UnassignVetRequest,
    authorization: Optional[str] = Header(None)
):
    farm_email = await get_current_user_email(authorization)
    farm = await farms_collection.find_one({"email": farm_email})
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm profile not found."
        )

    vet_query = {}
    if payload.vet_id and ObjectId.is_valid(payload.vet_id):
        vet_query["_id"] = ObjectId(payload.vet_id)
    elif payload.vet_email:
        vet_query["email"] = payload.vet_email
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid vet_id or vet_email."
        )

    vet = await vets_collection.find_one(vet_query)
    if not vet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Veterinarian profile not found."
        )

    vet_id_str = str(vet["_id"])
    farm_id_str = str(farm["_id"])

    # Unlink vet from farm
    await farms_collection.update_one(
        {"_id": farm["_id"]},
        {
            "$pull": {
                "assigned_vet_ids": vet_id_str,
                "assigned_vet_emails": vet["email"]
            }
        }
    )

    # Unlink farm from vet
    await vets_collection.update_one(
        {"_id": vet["_id"]},
        {
            "$pull": {
                "assigned_farm_ids": farm_id_str,
                "assigned_farms": farm["email"]
            }
        }
    )

    return {
        "message": f"Dr. {vet.get('full_name')} unassigned from your farm.",
        "vet_id": vet_id_str
    }

@router.get("/farms/assigned-vets", response_model=list[VetSearchResponse])
async def list_assigned_veterinarians(authorization: Optional[str] = Header(None)):
    farm_email = await get_current_user_email(authorization)
    farm = await farms_collection.find_one({"email": farm_email})
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm profile not found."
        )

    assigned_vet_ids = [ObjectId(v) for v in farm.get("assigned_vet_ids", []) if ObjectId.is_valid(v)]
    assigned_vet_emails = farm.get("assigned_vet_emails", [])

    if not assigned_vet_ids and not assigned_vet_emails:
        return []

    cursor = vets_collection.find({
        "$or": [
            {"_id": {"$in": assigned_vet_ids}},
            {"email": {"$in": assigned_vet_emails}}
        ]
    })

    vets = []
    async for doc in cursor:
        vets.append(VetSearchResponse(
            id=str(doc["_id"]),
            full_name=doc.get("full_name", ""),
            email=doc.get("email", ""),
            license_number=doc.get("license_number", ""),
            phone=doc.get("phone"),
            district=doc.get("district") or doc.get("location_district") or "Sri Lanka Central Jurisdiction",
            assigned=True
        ))
    return vets

@router.get("/vet/my-farms", response_model=list[FarmSummaryResponse])
async def list_vet_assigned_farms(authorization: Optional[str] = Header(None)):
    email = await get_current_user_email(authorization)
    vet = await vets_collection.find_one({"email": email})
    if not vet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Veterinarian profile not found."
        )

    vet_id_str = str(vet["_id"])
    assigned_farm_ids = [ObjectId(f) for f in vet.get("assigned_farm_ids", []) if ObjectId.is_valid(f)]
    assigned_farm_emails = vet.get("assigned_farms", [])

    query = {
        "$or": [
            {"_id": {"$in": assigned_farm_ids}},
            {"email": {"$in": assigned_farm_emails}},
            {"assigned_vet_ids": vet_id_str},
            {"assigned_vet_emails": vet["email"]}
        ]
    }

    cursor = farms_collection.find(query)
    farms_list = []
    async for farm_doc in cursor:
        f_email = farm_doc.get("email", "")
        # Aggregate cattle count and alert count for this farm
        total_cattle = await cattles_collection.count_documents({"owner_email": f_email})
        alert_cattle = await cattles_collection.count_documents({
            "owner_email": f_email,
            "$or": [{"health_status": "Alert"}, {"status": "Alert"}]
        })

        # Parse coordinates if present
        lat = farm_doc.get("latitude")
        lon = farm_doc.get("longitude")
        loc_district = farm_doc.get("location_district", "")
        if (lat is None or lon is None) and loc_district and "(" in loc_district:
            try:
                coords_part = loc_district.split("(")[0].strip()
                p_lat, p_lon = coords_part.split(",")
                lat = float(p_lat.strip())
                lon = float(p_lon.strip())
            except Exception:
                pass

        farms_list.append(FarmSummaryResponse(
            id=str(farm_doc["_id"]),
            owner_name=farm_doc.get("owner_name", "Estate Principal"),
            email=f_email,
            location_district=loc_district or "Central Agro District",
            latitude=lat,
            longitude=lon,
            registration_number=farm_doc.get("registration_number") or f"REG-SL-{str(farm_doc['_id'])[-4:].upper()}",
            total_animals=total_cattle or farm_doc.get("total_animals", 0),
            alert_count=alert_cattle,
            status="Active Synchronization" if total_cattle > 0 else "Pending Intake"
        ))

    return farms_list

@router.get("/vet/farms/{farm_id}/cattle")
async def get_assigned_farm_cattle(
    farm_id: str,
    authorization: Optional[str] = Header(None)
):
    email = await get_current_user_email(authorization)
    vet = await vets_collection.find_one({"email": email})
    if not vet:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized. Only veterinarians can access this endpoint."
        )

    # Find farm
    farm = None
    if ObjectId.is_valid(farm_id):
        farm = await farms_collection.find_one({"_id": ObjectId(farm_id)})
    if not farm:
        farm = await farms_collection.find_one({"email": farm_id})

    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target farm not found."
        )

    # Enforce RBAC: verify vet is assigned to this farm
    vet_id_str = str(vet["_id"])
    farm_id_str = str(farm["_id"])
    vet_assigned_farms = set(vet.get("assigned_farm_ids", [])) | set(vet.get("assigned_farms", []))
    farm_assigned_vets = set(farm.get("assigned_vet_ids", [])) | set(farm.get("assigned_vet_emails", []))

    is_authorized = (
        farm_id_str in vet_assigned_farms or
        farm.get("email") in vet_assigned_farms or
        vet_id_str in farm_assigned_vets or
        vet.get("email") in farm_assigned_vets
    )

    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You are not an authorized veterinarian for this agricultural estate."
        )

    # Retrieve cattle for this farm
    cursor = cattles_collection.find({"owner_email": farm["email"]})
    cattle_records = []
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        doc.pop("_id", None)
        doc["farm_id"] = farm_id_str
        doc["farm_name"] = farm.get("owner_name", "Assigned Farm")
        doc["farm_location"] = farm.get("location_district", "")
        cattle_records.append(doc)

    return {
        "farm": {
            "id": farm_id_str,
            "owner_name": farm.get("owner_name"),
            "email": farm.get("email"),
            "location_district": farm.get("location_district"),
            "registration_number": farm.get("registration_number"),
            "latitude": farm.get("latitude"),
            "longitude": farm.get("longitude")
        },
        "cattle": cattle_records,
        "total_animals": len(cattle_records),
    }


# ─── Diagnostic Case Reporting & Verification Endpoints ──────────────────────

@router.post("/vet/cases", response_model=DiagnosticCaseResponse, status_code=status.HTTP_201_CREATED)
async def report_diagnostic_case(
    payload: DiagnosticCaseCreate,
    authorization: Optional[str] = Header(None)
):
    """Report a new AI diagnostic case by veterinarian for a selected animal."""
    vet_email = None
    vet = None
    if authorization and authorization.startswith("Bearer "):
        try:
            vet_email = await get_current_user_email(authorization)
            vet = await vets_collection.find_one({"email": vet_email})
        except Exception:
            pass

    # If cattle_id provided, look up cattle details to ensure complete record
    cattle = None
    farm = None
    if payload.cattle_id and ObjectId.is_valid(payload.cattle_id):
        cattle = await cattles_collection.find_one({"_id": ObjectId(payload.cattle_id)})
        if cattle:
            owner_email = cattle.get("owner_email")
            if owner_email:
                farm = await farms_collection.find_one({"email": owner_email})

    animal_id_str = payload.animal_identifier or (cattle.get("identifier") if cattle else "COW-UNASSIGNED")
    farm_name_str = payload.farm_name or ((farm.get("owner_name") + "'s Farm") if farm else "Regional Agro Estate")
    farm_id_str = payload.farm_id or (str(farm["_id"]) if farm else None)
    breed_str = payload.breed or (cattle.get("breed") if cattle else "Dairy Breed")

    now = datetime.utcnow()
    case_number = f"REC-{now.year}-{now.strftime('%m%d%H%M%S')[-4:]}"

    is_verified = payload.verified
    status_label = "Verified" if is_verified else "Pending Verification"

    case_doc = {
        "case_number": case_number,
        "cattle_id": payload.cattle_id,
        "farm_id": farm_id_str,
        "farm_name": farm_name_str,
        "animal_identifier": animal_id_str,
        "breed": breed_str,
        "disease_name": payload.disease_name,
        "confidence": round(payload.confidence, 2),
        "severity": payload.severity or "Moderate",
        "stage": payload.stage or "Acute",
        "prognosis": payload.prognosis or "Good",
        "rationale": payload.rationale,
        "spatial_correlation": payload.spatial_correlation,
        "symptoms_image": payload.symptoms_image,
        "cropped_image": payload.cropped_image,
        "clinical_notes": payload.clinical_notes,
        "llm_reasoning": payload.llm_reasoning,
        "status": status_label,
        "verified": is_verified,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "verified_at": now.strftime("%Y-%m-%d %H:%M:%S") if is_verified else None,
        "vet_id": str(vet["_id"]) if vet else None,
        "vet_name": vet.get("full_name") if vet else (payload.clinical_notes or "Clinical Practitioner"),
        "vet_license": vet.get("license_number") if vet else "VET-AUTH-2026",
    }

    result = await diagnostic_cases_collection.insert_one(case_doc)
    case_id_str = str(result.inserted_id)

    # If verified and cattle exists, update cattle health status
    if is_verified and cattle:
        disease_lower = payload.disease_name.lower()
        is_healthy = disease_lower in ["cattle", "cattle (healthy)", "healthy"]
        new_health_status = "Healthy" if is_healthy else "Alert"
        await cattles_collection.update_one(
            {"_id": cattle["_id"]},
            {
                "$set": {
                    "health_status": new_health_status,
                    "status": new_health_status,
                    "last_diagnosis": payload.disease_name,
                    "last_diagnosed_date": now.strftime("%Y-%m-%d")
                }
            }
        )

    return DiagnosticCaseResponse(
        id=case_id_str,
        case_number=case_number,
        cattle_id=payload.cattle_id,
        farm_id=farm_id_str,
        farm_name=farm_name_str,
        animal_identifier=animal_id_str,
        breed=breed_str,
        disease_name=payload.disease_name,
        confidence=round(payload.confidence, 2),
        severity=case_doc["severity"],
        stage=case_doc["stage"],
        prognosis=case_doc["prognosis"],
        rationale=case_doc["rationale"],
        spatial_correlation=case_doc["spatial_correlation"],
        symptoms_image=case_doc["symptoms_image"],
        cropped_image=case_doc["cropped_image"],
        clinical_notes=case_doc["clinical_notes"],
        llm_reasoning=case_doc["llm_reasoning"],
        status=status_label,
        verified=is_verified,
        created_at=case_doc["created_at"],
        verified_at=case_doc["verified_at"],
        vet_id=case_doc["vet_id"],
        vet_name=case_doc["vet_name"],
        vet_license=case_doc["vet_license"],
    )


@router.get("/vet/cases", response_model=list[DiagnosticCaseResponse])
async def list_diagnostic_cases(
    cattle_id: Optional[str] = None,
    farm_id: Optional[str] = None,
    authorization: Optional[str] = Header(None)
):
    """List diagnostic cases. Allows filtering by cattle or farm."""
    query = {}
    if cattle_id:
        query["cattle_id"] = cattle_id
    if farm_id:
        query["farm_id"] = farm_id

    cursor = diagnostic_cases_collection.find(query).sort("_id", -1).limit(100)
    cases = []
    async for doc in cursor:
        cases.append(DiagnosticCaseResponse(
            id=str(doc["_id"]),
            case_number=doc.get("case_number", f"REC-2026-{str(doc['_id'])[-4:]}"),
            cattle_id=doc.get("cattle_id"),
            farm_id=doc.get("farm_id"),
            farm_name=doc.get("farm_name"),
            animal_identifier=doc.get("animal_identifier"),
            breed=doc.get("breed"),
            disease_name=doc.get("disease_name", "Undetermined"),
            confidence=float(doc.get("confidence", 0.0)),
            severity=doc.get("severity"),
            stage=doc.get("stage"),
            prognosis=doc.get("prognosis"),
            rationale=doc.get("rationale"),
            spatial_correlation=doc.get("spatial_correlation"),
            symptoms_image=doc.get("symptoms_image"),
            cropped_image=doc.get("cropped_image"),
            clinical_notes=doc.get("clinical_notes"),
            llm_reasoning=doc.get("llm_reasoning"),
            status=doc.get("status", "Verified" if doc.get("verified") else "Pending Verification"),
            verified=bool(doc.get("verified", False)),
            created_at=doc.get("created_at", datetime.utcnow().strftime("%Y-%m-%d")),
            verified_at=doc.get("verified_at"),
            vet_id=doc.get("vet_id"),
            vet_name=doc.get("vet_name"),
            vet_license=doc.get("vet_license"),
        ))
    return cases


@router.put("/vet/cases/{case_id}/verify", response_model=DiagnosticCaseResponse)
@router.post("/vet/cases/{case_id}/verify", response_model=DiagnosticCaseResponse)
async def verify_diagnostic_case(
    case_id: str,
    payload: Optional[DiagnosticCaseVerifyRequest] = None,
    authorization: Optional[str] = Header(None)
):
    """Verify and approve an AI diagnostic report."""
    vet = None
    if authorization and authorization.startswith("Bearer "):
        try:
            vet_email = await get_current_user_email(authorization)
            vet = await vets_collection.find_one({"email": vet_email})
        except Exception:
            pass

    if not ObjectId.is_valid(case_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Case ID format.")

    case_doc = await diagnostic_cases_collection.find_one({"_id": ObjectId(case_id)})
    if not case_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnostic case not found.")

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    update_data = {
        "verified": True,
        "status": "Verified",
        "verified_at": now_str,
    }
    if vet:
        update_data["vet_id"] = str(vet["_id"])
        update_data["vet_name"] = vet.get("full_name")
        update_data["vet_license"] = vet.get("license_number")

    if payload:
        if payload.clinical_notes:
            update_data["clinical_notes"] = payload.clinical_notes
        if payload.prescription:
            update_data["prescription"] = payload.prescription

    await diagnostic_cases_collection.update_one({"_id": ObjectId(case_id)}, {"$set": update_data})
    updated_case = await diagnostic_cases_collection.find_one({"_id": ObjectId(case_id)})

    # Also update cattle status if linked
    if updated_case.get("cattle_id") and ObjectId.is_valid(updated_case["cattle_id"]):
        cattle = await cattles_collection.find_one({"_id": ObjectId(updated_case["cattle_id"])})
        if cattle:
            disease_lower = updated_case.get("disease_name", "").lower()
            is_healthy = disease_lower in ["cattle", "cattle (healthy)", "healthy"]
            target_status = payload.health_status if (payload and payload.health_status) else ("Healthy" if is_healthy else "Alert")
            await cattles_collection.update_one(
                {"_id": cattle["_id"]},
                {
                    "$set": {
                        "health_status": target_status,
                        "status": target_status,
                        "last_diagnosis": updated_case.get("disease_name"),
                        "last_diagnosed_date": datetime.utcnow().strftime("%Y-%m-%d")
                    }
                }
            )

    return DiagnosticCaseResponse(
        id=str(updated_case["_id"]),
        case_number=updated_case.get("case_number", f"REC-2026-{case_id[-4:]}"),
        cattle_id=updated_case.get("cattle_id"),
        farm_id=updated_case.get("farm_id"),
        farm_name=updated_case.get("farm_name"),
        animal_identifier=updated_case.get("animal_identifier"),
        breed=updated_case.get("breed"),
        disease_name=updated_case.get("disease_name", "Undetermined"),
        confidence=float(updated_case.get("confidence", 0.0)),
        severity=updated_case.get("severity"),
        stage=updated_case.get("stage"),
        prognosis=updated_case.get("prognosis"),
        rationale=updated_case.get("rationale"),
        spatial_correlation=updated_case.get("spatial_correlation"),
        symptoms_image=updated_case.get("symptoms_image"),
        cropped_image=updated_case.get("cropped_image"),
        clinical_notes=updated_case.get("clinical_notes"),
        llm_reasoning=updated_case.get("llm_reasoning"),
        status="Verified",
        verified=True,
        created_at=updated_case.get("created_at", now_str),
        verified_at=updated_case.get("verified_at", now_str),
        vet_id=updated_case.get("vet_id"),
        vet_name=updated_case.get("vet_name"),
        vet_license=updated_case.get("vet_license"),
    )


@router.post("/cattle", status_code=status.HTTP_201_CREATED)
async def create_cattle(cattle_data: CattleCreate, authorization: Optional[str] = Header(None)):
    try:
        owner_email = await get_current_user_email(authorization)
        doc = cattle_data.model_dump()
        doc["owner_email"] = owner_email
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
async def list_cattle(authorization: Optional[str] = Header(None)):
    try:
        owner_email = await get_current_user_email(authorization)
        cursor = cattles_collection.find({"owner_email": owner_email})
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
        "latitude": farm.get("latitude"),
        "longitude": farm.get("longitude"),
        "registration_number": farm.get("registration_number"),
        "veterinarian_name": farm.get("veterinarian_name"),
        "profile_photo": farm.get("profile_photo"),
        "assigned_vet_ids": farm.get("assigned_vet_ids", [])
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
    if "location_district" in profile_data:
        update_fields["location_district"] = profile_data["location_district"]
    if "latitude" in profile_data and profile_data["latitude"] is not None:
        update_fields["latitude"] = float(profile_data["latitude"])
    if "longitude" in profile_data and profile_data["longitude"] is not None:
        update_fields["longitude"] = float(profile_data["longitude"])
        
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
            'Holstein-Friesian': {'milk': 25.0, 'weight': 600.0},
            'Jersey': {'milk': 16.0, 'weight': 410.0},
            'Ayrshire': {'milk': 19.0, 'weight': 480.0},
            'Brown_Swiss': {'milk': 21.0, 'weight': 550.0},
            'Guernsey': {'milk': 17.0, 'weight': 450.0},
            'Fleckvieh': {'milk': 22.0, 'weight': 650.0},
            'Montbeliarde': {'milk': 20.0, 'weight': 600.0},
            'Simmental': {'milk': 20.0, 'weight': 650.0},
            'Milking_Shorthorn': {'milk': 18.0, 'weight': 550.0},
            'Normande': {'milk': 18.0, 'weight': 600.0},
            'Danish_Red': {'milk': 19.0, 'weight': 550.0},
            'Norwegian_Red': {'milk': 19.0, 'weight': 550.0},
            'Illawarra_Shorthorn': {'milk': 18.0, 'weight': 550.0},
            'Sahiwal': {'milk': 10.0, 'weight': 380.0},
            'Gir': {'milk': 12.0, 'weight': 400.0},
            'Tharparkar': {'milk': 9.0, 'weight': 380.0},
            'Red_Sindhi': {'milk': 10.0, 'weight': 350.0},
            'Kankrej': {'milk': 8.0, 'weight': 450.0},
            'Hariana': {'milk': 7.0, 'weight': 400.0},
            'Ongole': {'milk': 6.0, 'weight': 450.0},
            'Deoni': {'milk': 7.0, 'weight': 400.0},
            'Gangatiri': {'milk': 6.0, 'weight': 350.0},
            'Krishna_Valley': {'milk': 6.0, 'weight': 400.0},
            'Rathi': {'milk': 8.0, 'weight': 380.0},
            'Ankole': {'milk': 5.0, 'weight': 450.0},
            'Boran': {'milk': 6.0, 'weight': 400.0},
            'Africander': {'milk': 5.0, 'weight': 450.0},
            'NDama': {'milk': 3.0, 'weight': 250.0},
            'White_Fulani': {'milk': 5.0, 'weight': 350.0},
            'Butana': {'milk': 7.0, 'weight': 350.0},
            'Kenana': {'milk': 7.0, 'weight': 350.0},
            'Red_Poll_Africa': {'milk': 8.0, 'weight': 450.0},
            'Exotic_Local_Cross': {'milk': 12.0, 'weight': 400.0},
            'Girolando': {'milk': 15.0, 'weight': 450.0},
            'Holstein_Zebu_Cross': {'milk': 18.0, 'weight': 480.0},
            'Jersey_Zebu_Cross': {'milk': 14.0, 'weight': 400.0},
            'Australian_Friesian_Sahiwal': {'milk': 15.0, 'weight': 450.0},
            'Australian_Milking_Zebu': {'milk': 12.0, 'weight': 420.0},
            'Zebu_Cross_Brazil': {'milk': 14.0, 'weight': 450.0},
            'Tipo_Carora': {'milk': 14.0, 'weight': 450.0}
        }
        
        breed_info = breed_defaults.get(payload.Breed, {"milk": 15.0, "weight": 450.0})
        breed_avg_milk = custom_milk if custom_milk is not None else breed_info["milk"]
        breed_avg_weight = custom_weight if custom_weight is not None else breed_info["weight"]
        
        # 2. Compute drop percentages (FIXED: Using Day_Minus_3_Milk)
        prev_milk_3d = payload.Day_Minus_3_Milk if payload.Day_Minus_3_Milk > 0 else payload.Milk_Yield_L
        milk_drop = ((prev_milk_3d - payload.Milk_Yield_L) / prev_milk_3d) * 100.0 if prev_milk_3d > 0 else 0.0
        
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

@router.post("/monitor/predict-bcs")
async def predict_bcs(
    file: UploadFile = File(...),
    confidence: float = Form(0.5),
    cattle_id: Optional[str] = Form(None),
    photo_date: Optional[str] = Form(None)
):
    global yolo_model, bcs_model, cv2
    # Lazy reload check in case modules were imported as None originally
    if cv2 is None:
        try:
            import cv2 as cv2_imported
            cv2 = cv2_imported
        except ImportError:
            pass

    if yolo_model is None or bcs_model is None:
        load_ai_models()
        
    if cv2 is None or yolo_model is None or bcs_model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI models or OpenCV libraries are not loaded. Please ensure cv2, best.pt, and Cow_BCS_Final_Master.h5 are present."
        )

    # 1. Read uploaded image bytes
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image format."
        )

    h, w, _ = img_bgr.shape

    # 2. Run YOLO prediction
    results = yolo_model.predict(img_bgr, conf=confidence, verbose=False)
    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No cow detected in the image. Try decreasing the confidence threshold."
        )

    # 3. Extract highest confidence bounding box
    max_idx = int(np.argmax(boxes.conf.cpu().numpy()))
    box = boxes[max_idx]
    
    # Coordinates: xyxy format
    xyxy = box.xyxy[0].cpu().numpy()
    x1, y1, x2, y2 = map(int, xyxy)
    det_conf = float(box.conf[0].cpu().item())

    # 4. Apply a dynamic 30-pixel padding clamped to image bounds
    px1 = max(0, x1 - 30)
    py1 = max(0, y1 - 30)
    px2 = min(w, x2 + 30)
    py2 = min(h, y2 + 30)

    # 5. Crop the region
    crop_bgr = img_bgr[py1:py2, px1:px2]
    if crop_bgr.size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cropped bounding box is empty."
        )

    # 6. Resize BGR crop directly (matching training/notebook flow), normalize, expand dimensions
    crop_resized = cv2.resize(crop_bgr, (224, 224))
    crop_normalized = crop_resized.astype(np.float32) / 255.0
    crop_input = np.expand_dims(crop_normalized, axis=0) # shape: (1, 224, 224, 3)

    # 7. Run Keras prediction to get float score
    pred = bcs_model.predict(crop_input, verbose=False)
    bcs_score = float(pred[0][0])

    gradcam_image = None
    try:
        last_conv_layer, target_model_for_cam = get_last_conv_layer(bcs_model)

        if last_conv_layer is not None and target_model_for_cam is not None:
            cam_input = crop_input
            if target_model_for_cam is not bcs_model:
                for layer in bcs_model.layers:
                    if layer is target_model_for_cam:
                        break
                    cam_input = layer(cam_input)

            heatmap = make_gradcam_heatmap(cam_input, target_model_for_cam, last_conv_layer.name)

            if np.max(heatmap) > 0:
                # --- FIXED VISIBILITY XAI OVERLAY ---
                xai_bgr = img_bgr.copy()
                crop_h, crop_w = py2 - py1, px2 - px1
                
                # 1. Resize heatmap to bounding box
                heatmap_resized = cv2.resize(heatmap, (crop_w, crop_h))
                
                # 2. Convert to INFERNO colormap
                heatmap_color = cv2.applyColorMap(np.uint8(255 * heatmap_resized), cv2.COLORMAP_INFERNO)
                
                # 3. Extract the ROI from the original image
                roi = xai_bgr[py1:py2, px1:px2]
                
                # 4. Create a dynamic alpha mask (max 50% opacity) so the cow is ALWAYS visible
                alpha_mask = np.stack([heatmap_resized]*3, axis=-1) * 0.5 
                
                # 5. Blend the heatmap over the original cow ROI
                blended_roi = (heatmap_color * alpha_mask + roi * (1.0 - alpha_mask)).astype(np.uint8)
                xai_bgr[py1:py2, px1:px2] = blended_roi
                
                # 6. Find the ABSOLUTE Hottest spot
                _, _, _, maxLoc = cv2.minMaxLoc(heatmap_resized)
                center_x = int(maxLoc[0]) + px1
                center_y = int(maxLoc[1]) + py1
                
                # 7. Draw sleek Crosshair UI
                cv2.circle(xai_bgr, (center_x, center_y), 35, (0, 255, 255), 2)
                cv2.circle(xai_bgr, (center_x, center_y), 3, (0, 255, 255), -1)
                cv2.line(xai_bgr, (center_x - 50, center_y), (center_x - 20, center_y), (0, 255, 255), 2)
                cv2.line(xai_bgr, (center_x + 20, center_y), (center_x + 50, center_y), (0, 255, 255), 2)
                cv2.line(xai_bgr, (center_x, center_y - 50), (center_x, center_y - 20), (0, 255, 255), 2)
                cv2.line(xai_bgr, (center_x, center_y + 20), (center_x, center_y + 50), (0, 255, 255), 2)
                
                # 8. Draw text label
                text = "AI PRECISION FOCUS"
                text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, 0.5, 1)[0]
                text_x = center_x - text_size[0] // 2
                text_y = center_y - 65
                
                # Clamp text within bounds
                if text_y - text_size[1] - 10 < 0:
                    text_y = center_y + 65 + text_size[1]
                    
                cv2.rectangle(xai_bgr, (text_x - 10, text_y - text_size[1] - 10), (text_x + text_size[0] + 10, text_y + 10), (0, 0, 0), -1)
                cv2.putText(xai_bgr, text, (text_x, text_y), cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 255, 255), 1)
                
                _, gc_buf = cv2.imencode(".jpg", xai_bgr)
                gradcam_image = "data:image/jpeg;base64," + base64.b64encode(gc_buf).decode("utf-8")
            else:
                print("[DEBUG] Heatmap is entirely zero.")
        else:
            print("[DEBUG] No convolution layer found for Grad-CAM.")
    except Exception as e:
        import traceback
        print(f"\n--- GRAD-CAM CRITICAL FAILURE ---")
        traceback.print_exc()
        gradcam_image = None

    # 8. Draw bounding box on original image for visualization
    annotated_bgr = img_bgr.copy()
    label = f"Cow: {det_conf:.2f} | BCS: {bcs_score:.2f}"
    cv2.rectangle(annotated_bgr, (x1, y1), (x2, y2), (46, 222, 163), 3) # emerald primary color
    cv2.putText(annotated_bgr, label, (x1, max(y1 - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (46, 222, 163), 2)

    # 9. Encode original annotated and cropped images to base64
    _, annot_buf = cv2.imencode(".jpg", annotated_bgr)
    annot_b64 = "data:image/jpeg;base64," + base64.b64encode(annot_buf).decode("utf-8")

    _, crop_buf = cv2.imencode(".jpg", crop_bgr)
    crop_b64 = "data:image/jpeg;base64," + base64.b64encode(crop_buf).decode("utf-8")

    # 10. Database Update if cattle_id provided and is valid ObjectId
    if cattle_id:
        try:
            if ObjectId.is_valid(cattle_id):
                target_date = photo_date if photo_date else datetime.utcnow().strftime("%Y-%m-%d")
                
                # Insert log document
                log_doc = {
                    "cattle_id": cattle_id,
                    "date": target_date,
                    "bcs_score": bcs_score,
                    "detection_conf": det_conf
                }
                await bcs_logs_collection.insert_one(log_doc)
                
                # Fetch cattle doc to verify last_scored_date
                cattle_doc = await cattles_collection.find_one({"_id": ObjectId(cattle_id)})
                if cattle_doc:
                    existing_date = cattle_doc.get("last_scored_date")
                    
                    should_update = False
                    if not existing_date:
                        should_update = True
                    else:
                        try:
                            # Use >= so multiple uploads on the same day update to the latest score
                            if target_date >= existing_date:
                                should_update = True
                        except Exception:
                            should_update = True
                            
                    if should_update:
                        await cattles_collection.update_one(
                            {"_id": ObjectId(cattle_id)},
                            {"$set": {
                                "bcs_score": bcs_score,
                                "last_scored_date": target_date
                            }}
                        )
        except Exception as e:
            print(f"Error updating cattle database record: {e}")

    return {
        "bcs_score": round(bcs_score, 2),
        "detection_conf": round(det_conf, 2),
        "annotated_image": annot_b64,
        "crop_image": crop_b64,
        "gradcam_image": gradcam_image
    }

@router.get("/cattle/{id}/bcs-logs")
async def get_bcs_logs(id: str):
    try:
        cursor = bcs_logs_collection.find({"cattle_id": id}).sort("date", -1)
        logs = []
        async for doc in cursor:
            logs.append({
                "id": str(doc["_id"]),
                "cattle_id": doc["cattle_id"],
                "date": doc["date"],
                "bcs_score": float(doc["bcs_score"]),
                "detection_conf": float(doc["detection_conf"])
            })
        return logs
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while loading BCS history logs: {str(e)}"
        )

@router.post("/monitor/predict-7day")
async def predict_7day(payload: TriagePredictPayload):
    global late_fusion_model
    if late_fusion_model is None:
        load_ai_models()
    if late_fusion_model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Late Fusion model is not loaded. Please ensure adrs_late_fusion_model.h5 is present."
        )

    try:
        # Validate time series lengths
        if (len(payload.ambient_temp) != 7 or len(payload.humidity) != 7 or len(payload.thi) != 7 or
            len(payload.body_temp) != 7 or len(payload.milk_yield) != 7 or len(payload.water_intake) != 7 or
            len(payload.feed_intake) != 7 or len(payload.weight) != 7):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All time series arrays must have exactly 7 elements."
            )

        # 1. Construct X_ts: shape (1, 7, 8)
        ts_data = []
        for i in range(7):
            ts_data.append([
                float(payload.ambient_temp[i]) / 50.0,
                float(payload.humidity[i]) / 100.0,
                float(payload.thi[i]) / 100.0,
                float(payload.body_temp[i]) / 50.0,
                float(payload.milk_yield[i]) / 50.0,
                float(payload.water_intake[i]) / 150.0,
                float(payload.feed_intake[i]) / 50.0,
                float(payload.weight[i]) / 1000.0
            ])
        X_ts = np.array([ts_data], dtype=np.float32)

        import pandas as pd
        # 2. Construct X_static: exact 45 columns matching drop_first=True training schema
        dummy_columns = [
            'Age_Months', 'Days_in_Milk', 'Breed_Ankole', 'Breed_Australian_Friesian_Sahiwal',
            'Breed_Australian_Milking_Zebu', 'Breed_Ayrshire', 'Breed_Boran', 'Breed_Brown_Swiss',
            'Breed_Butana', 'Breed_Danish_Red', 'Breed_Deoni', 'Breed_Exotic_Local_Cross',
            'Breed_Fleckvieh', 'Breed_Gangatiri', 'Breed_Gir', 'Breed_Girolando', 'Breed_Guernsey',
            'Breed_Hariana', 'Breed_Holstein-Friesian', 'Breed_Holstein_Zebu_Cross',
            'Breed_Illawarra_Shorthorn', 'Breed_Jersey', 'Breed_Jersey_Zebu_Cross', 'Breed_Kankrej',
            'Breed_Kenana', 'Breed_Krishna_Valley', 'Breed_Milking_Shorthorn', 'Breed_Montbeliarde',
            'Breed_NDama', 'Breed_Normande', 'Breed_Norwegian_Red', 'Breed_Ongole', 'Breed_Rathi',
            'Breed_Red_Poll_Africa', 'Breed_Red_Sindhi', 'Breed_Sahiwal', 'Breed_Simmental',
            'Breed_Tharparkar', 'Breed_Tipo_Carora', 'Breed_White_Fulani', 'Breed_Zebu_Cross_Brazil',
            'Genetic_Group_B', 'Genetic_Group_C', 'Lactation_Stage_Late', 'Lactation_Stage_Mid'
        ]

        cow_static_df = pd.DataFrame([{
            'Age_Months': float(payload.age_months),
            'Days_in_Milk': float(payload.days_in_milk),
            'Breed': payload.breed,
            'Genetic_Group': payload.genetic_group,  # Must be 'A', 'B', or 'C'
            'Lactation_Stage': payload.lactation_stage.split(' ')[0].title()  # 'Early', 'Mid', or 'Late'
        }])

        cow_dummy = pd.get_dummies(cow_static_df)
        cow_dummy = cow_dummy.reindex(columns=dummy_columns, fill_value=0)

        X_static = cow_dummy.values.astype(np.float32)
        X_static[0, 0] = X_static[0, 0] / 100.0   # Scale Age_Months
        X_static[0, 1] = X_static[0, 1] / 305.0   # Scale Days_in_Milk

        # 3. Construct X_vis: shape (1, 1)
        X_vis = np.array([[float(payload.bcs_score) / 5.0]], dtype=np.float32)

        # 4. Predict
        preds = late_fusion_model.predict([X_ts, X_static, X_vis], verbose=False)
        pred_class = int(np.argmax(preds[0]))

        return {"class": pred_class}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Late Fusion prediction failure: {str(e)}"
        )
