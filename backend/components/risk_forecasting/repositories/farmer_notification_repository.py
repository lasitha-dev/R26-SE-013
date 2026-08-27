import logging
from typing import List, Dict, Any
from datetime import datetime, timezone
from pymongo import UpdateOne
from core.database import db

logger = logging.getLogger(__name__)

async def forward_to_assigned_farms(advisory, assigned_farms: List[Dict[str, Any]], vet: Dict[str, Any]) -> Dict[str, int]:
    if not assigned_farms:
        return {"notified_count": 0, "already_notified_count": 0}

    now_iso = datetime.now(timezone.utc).isoformat()
    operations = []
    
    # Safely extract advisory ID which might be a model field or a dict key depending on how it's returned
    advisory_id = getattr(advisory, 'advisory_id', None) or (advisory.get("advisory_id") if isinstance(advisory, dict) else None)
    title = getattr(advisory, 'title', None) or (advisory.get("title") if isinstance(advisory, dict) else "Disease Advisory")
    message = getattr(advisory, 'standard_message', None) or (advisory.get("standard_message") if isinstance(advisory, dict) else "A new advisory has been issued.")
    severity = getattr(advisory, 'risk_level', None) or (advisory.get("risk_level") if isinstance(advisory, dict) else "High")
    
    for farm in assigned_farms:
        farm_id = str(farm["_id"])
        deterministic_id = f"risk_forecasting:{advisory_id}:{farm_id}"
        
        doc = {
            "_id": deterministic_id,
            "advisory_id": advisory_id,
            "farm_id": farm_id,
            "farmer_email": farm.get("email"),
            "vet_id": str(vet["_id"]),
            "vet_email": vet.get("email"),
            "title": title,
            "message": message,
            "type": "risk_forecasting",
            "severity": severity,
            "source": "risk_forecasting",
            "created_at": now_iso,
            "read": False
        }
        
        operations.append(
            UpdateOne(
                {"_id": deterministic_id},
                {"$setOnInsert": doc},
                upsert=True
            )
        )
        
    if not operations:
        return {"notified_count": 0, "already_notified_count": 0}
        
    result = await db.forecast_notifications.bulk_write(operations, ordered=False)
    
    return {
        "notified_count": result.upserted_count,
        "already_notified_count": len(operations) - result.upserted_count
    }

async def list_for_farm(farm_id: str) -> List[Dict[str, Any]]:
    cursor = db.forecast_notifications.find({"farm_id": farm_id}).sort("created_at", -1)
    notifications = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        notifications.append(doc)
    return notifications
