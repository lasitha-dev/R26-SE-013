"""National case-surveillance records: disease gate, verification state,
GPS handling and privacy reduction (no identifying fields ever returned)."""

from datetime import datetime

from components.geospatial_tracking.services.operational.national_cases import build_national_case_records, record_key

FARMS = {
    "farm-gps": {"_id": "farm-gps", "latitude": 5.95, "longitude": 80.55, "location_district": "Matara"},
    "farm-nogps": {"_id": "farm-nogps", "latitude": None, "longitude": None, "location_district": "Kandy"},
    "farm-strgps": {"_id": "farm-strgps", "latitude": "6.9", "longitude": "79.8", "location_district": "Colombo"},
}


def _case(_id, disease, verified, farm, **extra):
    return {
        "_id": _id, "disease_name": disease, "verified": verified, "farm_id": farm,
        "status": "Verified" if verified else "Pending Verification",
        "created_at": "2026-08-29T10:00:00", "verified_at": datetime(2026, 8, 30, 6, 0, 0) if verified else None,
        "farm_name": "Private Farm", "vet_name": "Dr X", "reporter_email": "x@example.com", "clinical_notes": "free text",
        "severity": "Moderate", "stage": "Early", "confidence": 0.91, **extra,
    }


def test_disease_gate_status_gps_and_privacy():
    result = build_national_case_records(
        [
            _case("c1", "Lumpy Skin Disease", True, "farm-gps"),
            _case("c2", "FMD", False, "farm-gps"),
            _case("c3", "Mastitis", True, "farm-gps"),
            _case("c4", "Foot and Mouth Disease", True, "farm-nogps"),
            _case("c5", "LSD", True, "farm-strgps"),
        ],
        FARMS,
    )
    records = {r["record_key"]: r for r in result["records"]}
    assert len(records) == 4  # Mastitis excluded, never shown
    lsd = records[record_key("c1")]
    assert lsd["disease"] == "LSD" and lsd["verification_status"] == "VERIFIED"
    assert lsd["verified_at"].startswith("2026-08-30T06:00:00")
    assert (lsd["latitude"], lsd["longitude"], lsd["location_status"]) == (5.95, 80.55, "VALID")
    assert lsd["district"] == "Matara"
    pending = records[record_key("c2")]
    assert pending["verification_status"] == "PENDING_VERIFICATION" and pending["verified_at"] is None
    assert records[record_key("c4")]["location_status"] == "LOCATION_REQUIRED"
    # string coordinates are not silently accepted (existing farm GPS rule)
    assert records[record_key("c5")]["latitude"] is None
    assert result["summary"]["excluded"] == {"disease_not_lsd_or_fmd": 1, "no_usable_farm_gps": 2}
    assert result["summary"]["by_verification_status"] == {"VERIFIED": 3, "PENDING_VERIFICATION": 1}
    flat = repr(result)
    for leaked in ("Private Farm", "Dr X", "x@example.com", "free text", "farm-gps", "'c1'"):
        assert leaked not in flat
    assert lsd["clinical_summary"] == {"severity": "Moderate", "stage": "Early", "model_confidence": 0.91}
