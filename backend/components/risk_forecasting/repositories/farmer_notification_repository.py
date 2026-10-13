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
    base_message = getattr(advisory, 'standard_message', None) or (advisory.get("standard_message") if isinstance(advisory, dict) else "A new advisory has been issued.")
    severity = getattr(advisory, 'risk_level', None) or (advisory.get("risk_level") if isinstance(advisory, dict) else "High")
    vet_note = getattr(advisory, 'vet_custom_note', None) or (advisory.get("vet_custom_note") if isinstance(advisory, dict) else None)
    
    # Extract personalized overrides as a dictionary {recipient_id: custom_note}
    overrides_list = getattr(advisory, 'personalized_overrides', []) or (advisory.get("personalized_overrides", []) if isinstance(advisory, dict) else [])
    overrides_map = {}
    for override in overrides_list:
        rec_id = getattr(override, 'recipient_id', None) or (override.get("recipient_id") if isinstance(override, dict) else None)
        note = getattr(override, 'custom_note', None) or (override.get("custom_note") if isinstance(override, dict) else None)
        if rec_id and note:
            overrides_map[str(rec_id)] = str(note)
    
    for farm in assigned_farms:
        farm_id = str(farm["_id"])
        deterministic_id = f"risk_forecasting:{advisory_id}:{farm_id}"
        
        # Build the final message for this specific farm
        final_message = base_message
        if vet_note:
            final_message += f"\n\nVet Note: {vet_note}"
            
        if farm_id in overrides_map:
            final_message += f"\n\nPersonalized Note: {overrides_map[farm_id]}"
        
        doc = {
            "advisory_id": advisory_id,
            "farm_id": farm_id,
            "farmer_email": farm.get("email"),
            "vet_id": str(vet["_id"]),
            "vet_email": vet.get("email"),
            "title": title,
            "message": final_message,
            "type": "risk_forecasting",
            "severity": severity,
            "source": "risk_forecasting",
            "read": False
        }
        
        operations.append(
            UpdateOne(
                {"_id": deterministic_id},
                {"$set": doc, "$setOnInsert": {"created_at": now_iso}},
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
