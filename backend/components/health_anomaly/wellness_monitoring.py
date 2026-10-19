"""Validation and farm-scoped persistence for wellness monitoring."""
from datetime import datetime
import re

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReplaceOne


# ==============================================================================
# FUNCTION 1: normalize_date_str
# ------------------------------------------------------------------------------
# What this function does:
#   Converts any incoming date string (like "2026-10-19" or "10/19/2026") into
#   a standard YYYY-MM-DD format.
#
# Why we need it:
#   Farmers upload CSV files with different date formats (e.g., month/day/year or
#   year-month-day). Standardizing them prevents database sorting errors and keeps
#   all records uniform.
# ==============================================================================
def normalize_date_str(raw_date):
    """Accept year-first dates or month/day/year CSV dates, without rollovers."""
    # Step 1: If input is already a Python datetime object, format it directly to YYYY-MM-DD.
    if isinstance(raw_date, datetime):
        return raw_date.strftime("%Y-%m-%d")

    # Step 2: Strip surrounding spaces and check against a regex pattern for 3 date components.
    value = str(raw_date or "").strip()
    match = re.fullmatch(r"(\d{1,4})[-/.](\d{1,2})[-/.](\d{1,4})", value)
    try:
        if not match:
            raise ValueError
        first, second, third = match.groups()

        # Step 3: Determine if the year is placed first (YYYY-MM-DD) or last (MM/DD/YYYY).
        if len(first) == 4:
            year, month, day = int(first), int(second), int(third)
        elif len(third) in (2, 4):
            month, day, year = int(first), int(second), int(third)
            if len(third) == 2:
                year += 2000
        else:
            raise ValueError

        # Step 4: Validate that it forms a real calendar date and return as standard YYYY-MM-DD string.
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Invalid date. Use YYYY-MM-DD or MM/DD/YYYY (month first).")


# ==============================================================================
# FUNCTION 2: farm_cattle_filter
# ------------------------------------------------------------------------------
# What this function does:
#   Creates a MongoDB query filter ensuring only cows belonging to the logged-in farm
#   are retrieved.
#
# Why we need it:
#   Data privacy and security: A farmer must never see or modify cattle belonging
#   to another farm.
# ==============================================================================
def farm_cattle_filter(email):
    # Step 1: Match cattle by owner_email or farm_email matching the user's account.
    return {"$or": [{"owner_email": email}, {"farm_email": email}]}


# ==============================================================================
# FUNCTION 3: is_deceased
# ------------------------------------------------------------------------------
# What this function does:
#   Checks if a given cow is already marked as deceased in the database.
#
# Why we need it:
#   Dead cows cannot produce milk or have daily wellness logs added to them.
# ==============================================================================
def is_deceased(cow):
    # Step 1: Look at the 'status' and 'health_status' fields to check for 'deceased'.
    return any(str(cow.get(field, "")).lower() == "deceased" for field in ("status", "health_status"))


# ==============================================================================
# FUNCTION 4: owned_cattle
# ------------------------------------------------------------------------------
# What this function does:
#   Finds a single live cow by its MongoDB ID or Tag ID and confirms farm ownership.
#
# Why we need it:
#   Validates user permissions before any monitoring log is saved or evaluated.
# ==============================================================================
async def owned_cattle(collection, email, cattle_id):
    # Step 1: Build a secure query scoped to the farmer's registered email.
    query = farm_cattle_filter(email)

    # Step 2: Search by ObjectId if valid, otherwise search by the animal's ear tag identifier.
    query["_id" if ObjectId.is_valid(cattle_id) else "identifier"] = (
        ObjectId(cattle_id) if ObjectId.is_valid(cattle_id) else cattle_id
    )
    cow = await collection.find_one(query)

    # Step 3: Reject if cow does not exist on this farm.
    if cow is None:
        raise HTTPException(404, "Cattle not found in your farm.")

    # Step 4: Block updates if the animal is deceased.
    if is_deceased(cow):
        raise HTTPException(400, "Monitoring cannot change a deceased animal's status.")
    return cow


# ==============================================================================
# FUNCTION 5: living_cattle_filter
# ------------------------------------------------------------------------------
# What this function does:
#   Builds a query targeting a specific cow that is confirmed to be living.
#
# Why we need it:
#   Prevents background updates from mistakenly reviving deceased cattle records.
# ==============================================================================
def living_cattle_filter(cow):
    return {"_id": cow["_id"], "status": {"$ne": "Deceased"}, "health_status": {"$ne": "Deceased"}}


# ==============================================================================
# FUNCTION 6: import_daily_logs
# ------------------------------------------------------------------------------
# What this function does:
#   Processes bulk daily logs (from CSV upload), runs AI/rule evaluation, and
#   updates both daily logs and cattle health statuses in the database.
#
# Why we need it:
#   Allows farmers to upload multiple days or multiple cows in a single CSV file,
#   automatically evaluating wellness and raising alerts where necessary.
# ==============================================================================
async def import_daily_logs(logs_data, email, cattle, daily_logs, breed_settings, evaluate):
    """Validate and infer the entire batch before replacing any stored logs.

    Matching records are replaced automatically. Repeated input keys use the
    last CSV row. Writes are idempotent so a database failure can be retried;
    inference or validation failures leave the stored data untouched.
    """
    # Step 1: Fetch all cows owned by this farm to resolve IDs and Ear Tag numbers in memory.
    all_cows = await cattle.find(farm_cattle_filter(email)).to_list(None)
    by_id = {str(cow["_id"]): cow for cow in all_cows}
    by_tag = {}
    for cow in all_cows:
        tag = str(cow.get("identifier", "")).strip().casefold()
        if tag:
            by_tag.setdefault(tag, []).append(cow)

    incoming = {}
    skipped = 0

    # Step 2: Loop through each row in the uploaded CSV data and match it to a valid cow.
    for row in logs_data:
        cow = by_id.get(row.cattle_id)
        if cow is None:
            # If an explicit object ID was provided but not found, reject.
            if row.cattle_id and ObjectId.is_valid(row.cattle_id):
                raise HTTPException(404, "Cattle not found in your farm.")
            matches = by_tag.get(str(row.identifier or row.cattle_id or "").strip().casefold(), [])
            if len(matches) != 1:
                raise HTTPException(400, "Unknown or ambiguous cattle identifier in CSV. Use the cattle ID.")
            cow = matches[0]

        # Step 3: Skip deceased animals and male cattle (since milk monitoring is female-only).
        if is_deceased(cow) or str(cow.get("gender", "")).lower() == "male":
            skipped += 1
            continue

        # Step 4: Clean the document and standardize the date string.
        doc = row.model_dump(exclude_none=True, exclude={"identifier", "cattle_id"})
        doc.update(cattle_id=str(cow["_id"]), date=normalize_date_str(row.date))
        incoming[(doc["cattle_id"], doc["date"])] = doc

    # Step 5: Load existing history for these cows so we can calculate 7-day rolling drops.
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

    # Step 6: For each cow, run the evaluation logic using past history plus newly uploaded logs.
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

    # Step 7: Bulk upsert all daily log records into the database.
    operations = []
    for key, doc in incoming.items():
        previous = existing.get(key)
        query = {"_id": previous["_id"]} if previous else {"cattle_id": key[0], "date": key[1]}
        operations.append(ReplaceOne(query, doc, upsert=True))
    if operations:
        await daily_logs.bulk_write(operations, ordered=True)

    # Step 8: Update each living cow's status, health_status, and current weight in the cattle collection.
    for query, fields in updates:
        await cattle.update_one(query, {"$set": fields})

    # Step 9: Return a structured summary to the frontend.
    return {"status": "success", "message": f"Successfully imported {len(incoming)} logs and evaluated {len(results)} cattle.",
            "count": len(incoming), "inserted_count": len(incoming), "evaluated_count": len(results),
            "skipped_count": skipped, "alerts_triggered": sum(bool(r["is_anomaly"]) for r in results), "results": results}
