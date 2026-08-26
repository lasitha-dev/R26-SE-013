"""
Isolated backend ViewerContext adapter.
Provides role verification and authenticated context without importing heavy AI dependencies.
"""
from typing import Any, Dict, List, Optional
from fastapi import Request, HTTPException, status
from pydantic import BaseModel
import jwt
import logging

from core.security import JWT_SECRET, JWT_ALGORITHM
from core.database import vets_collection

logger = logging.getLogger(__name__)

class ViewerContextAuthorization(BaseModel):
    scopeLevel: str
    registeredFarmDistrict: Optional[str] = None
    authorizedDistricts: List[str]
    assignedFarmIds: List[str]

    class Config:
        extra = "forbid"

class ViewerContextPermissions(BaseModel):
    viewDataQuality: bool
    viewModelTransparency: bool
    manageAlerts: bool
    recordResponse: bool
    viewReports: bool

    class Config:
        extra = "forbid"

class ViewerContextResponse(BaseModel):
    userId: str
    role: str
    authorization: ViewerContextAuthorization
    permissions: ViewerContextPermissions

    class Config:
        extra = "forbid"

async def get_viewer_context(request: Request) -> ViewerContextResponse:
    """
    Isolated backend ViewerContext adapter.
    Resolves the authenticated user from the request's Bearer token.
    Queries the main database vets_collection to verify the user is a Veterinary Officer.
    Provides the exact ViewerContext contract required by the Forecasting frontend.
    Fails closed with 401 or 403.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header."
        )
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format."
        )
        
    token = parts[1].strip()
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("sub")
        if not email or not isinstance(email, str) or not email.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token credentials."
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials."
        )
        
    vet = await vets_collection.find_one({"email": email.strip()})
    if not vet:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Veterinary profile not found."
        )
        
    if vet.get("role") != "vet":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Veterinary Officers are permitted to access this resource."
        )
        
    district = vet.get("district")
    if not district or not isinstance(district, str) or not district.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Veterinary profile missing valid district."
        )
    authorized_districts = [district.strip()]
    
    assigned_farm_ids_raw = vet.get("assigned_farm_ids")
    if assigned_farm_ids_raw is None:
        assigned_farm_ids = []
    elif isinstance(assigned_farm_ids_raw, list):
        assigned_farm_ids = []
        for fid in assigned_farm_ids_raw:
            if fid is None:
                continue
            if not isinstance(fid, (str, int)):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Malformed assigned-farm identifiers."
                )
            fid_str = str(fid).strip()
            if fid_str:
                assigned_farm_ids.append(fid_str)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Malformed assigned-farm array."
        )
        
    return ViewerContextResponse(
        userId=str(vet.get("_id", email)),
        role="VETERINARY_OFFICER",
        authorization=ViewerContextAuthorization(
            scopeLevel="DISTRICT",
            registeredFarmDistrict=None,
            authorizedDistricts=authorized_districts,
            assignedFarmIds=assigned_farm_ids
        ),
        permissions=ViewerContextPermissions(
            viewDataQuality=False,
            viewModelTransparency=True,
            manageAlerts=True,
            recordResponse=True,
            viewReports=True
        )
    )
