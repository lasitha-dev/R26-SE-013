"""Validation and farm-scoped persistence for wellness monitoring."""
from datetime import datetime
import re

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReplaceOne


def normalize_date_str(raw_date):
    """Accept year-first dates or month/day/year CSV dates, without rollovers."""
    if isinstance(raw_date, datetime):
        return raw_date.strftime("%Y-%m-%d")
    value = str(raw_date or "").strip()
    match = re.fullmatch(r"(\d{1,4})[-/.](\d{1,2})[-/.](\d{1,4})", value)
    try:
        if not match:
            raise ValueError
        first, second, third = match.groups()
        if len(first) == 4:
            year, month, day = int(first), int(second), int(third)
        elif len(third) in (2, 4):
            month, day, year = int(first), int(second), int(third)
            if len(third) == 2:
                year += 2000
        else:
            raise ValueError
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Invalid date. Use YYYY-MM-DD or MM/DD/YYYY (month first).")


def farm_cattle_filter(email):
    return {"$or": [{"owner_email": email}, {"farm_email": email}]}


def is_deceased(cow):
    return any(str(cow.get(field, "")).lower() == "deceased" for field in ("status", "health_status"))


async def owned_cattle(collection, email, cattle_id):
    query = farm_cattle_filter(email)
    query["_id" if ObjectId.is_valid(cattle_id) else "identifier"] = (
        ObjectId(cattle_id) if ObjectId.is_valid(cattle_id) else cattle_id
    )
    cow = await collection.find_one(query)
    if cow is None:
        raise HTTPException(404, "Cattle not found in your farm.")
    if is_deceased(cow):
        raise HTTPException(400, "Monitoring cannot change a deceased animal's status.")
    return cow


def living_cattle_filter(cow):
    return {"_id": cow["_id"], "status": {"$ne": "Deceased"}, "health_status": {"$ne": "Deceased"}}


async def import_daily_logs(logs_data, email, cattle, daily_logs, breed_settings, evaluate):
    """Validate and infer the entire batch before replacing any stored logs.

    Matching records are replaced automatically. Repeated input keys use the
    last CSV row. Writes are idempotent so a database failure can be retried;
    inference or validation failures leave the stored data untouched.
    """
    all_cows = await cattle.find(farm_cattle_filter(email)).to_list(None)
    by_id = {str(cow["_id"]): cow for cow in all_cows}
    by_tag = {}
    for cow in all_cows:
        tag = str(cow.get("identifier", "")).strip().casefold()
        if tag:
            by_tag.setdefault(tag, []).append(cow)

    incoming = {}
    skipped = 0
    for row in logs_data:
        cow = by_id.get(row.cattle_id)
        if cow is None:
            # An explicit object ID must never fall back to another animal's tag.
            if row.cattle_id and ObjectId.is_valid(row.cattle_id):
                raise HTTPException(404, "Cattle not found in your farm.")
            matches = by_tag.get(str(row.identifier or row.cattle_id or "").strip().casefold(), [])
            if len(matches) != 1:
                raise HTTPException(400, "Unknown or ambiguous cattle identifier in CSV. Use the cattle ID.")
            cow = matches[0]
        if is_deceased(cow) or str(cow.get("gender", "")).lower() == "male":
            skipped += 1
            continue
        doc = row.model_dump(exclude_none=True, exclude={"identifier", "cattle_id"})
        doc.update(cattle_id=str(cow["_id"]), date=normalize_date_str(row.date))
        incoming[(doc["cattle_id"], doc["date"])] = doc

    ids = list(dict.fromkeys(cid for cid, _ in incoming))
    history = await daily_logs.find({"cattle_id": {"$in": ids}}).to_list(None) if ids else []
    settings = await breed_settings.find({"farm_email": email}).to_list(None) if ids else []
    settings_by_breed = {setting.get("breed"): setting for setting in settings}
    by_cow = {cid: {} for cid in ids}
    existing = {}
    for log in history:
        date = normalize_date_str(log.get("date"))
        cid = log["cattle_id"]
        by_cow[cid][date] = dict(log, date=date)
        existing[(cid, date)] = log
    for (cid, date), doc in incoming.items():
        by_cow[cid][date] = doc

    results, updates = [], []
    for cid, dated_logs in by_cow.items():
        cow = by_id[cid]
        ordered = [dated_logs[date] for date in sorted(dated_logs)]
        latest = ordered[-1]
        custom = settings_by_breed.get(cow.get("breed"), {})
        outcome = evaluate(cow, latest, ordered, custom.get("avg_milk"), custom.get("avg_weight"))
        results.append(dict(cattle_id=cid, identifier=cow.get("identifier", "Unknown"),
                            breed=cow.get("breed", "Unknown"), **outcome))
        fields = {"status": outcome["new_status"], "health_status": outcome["new_status"],
                  "weight": outcome["weight"], "last_monitored_date": latest["date"]}
        query = living_cattle_filter(cow)
        query["$or"] = [{"last_monitored_date": {"$exists": False}},
                        {"last_monitored_date": None}, {"last_monitored_date": {"$lte": latest["date"]}}]
        updates.append((query, fields))

    # Replace in place rather than deleting first; preserve record IDs and retry safely.
    operations = []
    for key, doc in incoming.items():
        previous = existing.get(key)
        query = {"_id": previous["_id"]} if previous else {"cattle_id": key[0], "date": key[1]}
        operations.append(ReplaceOne(query, doc, upsert=True))
    if operations:
        await daily_logs.bulk_write(operations, ordered=True)
    for query, fields in updates:
        await cattle.update_one(query, {"$set": fields})

    return {"status": "success", "message": f"Successfully imported {len(incoming)} logs and evaluated {len(results)} cattle.",
            "count": len(incoming), "inserted_count": len(incoming), "evaluated_count": len(results),
            "skipped_count": skipped, "alerts_triggered": sum(bool(r["is_anomaly"]) for r in results), "results": results}
