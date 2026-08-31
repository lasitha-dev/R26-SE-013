"""Registry sanity checks (supports PROV-01..03)."""

from components.geospatial_tracking.services.geospatial.source_registry import REGISTRY

_ALLOWED_TEMPORAL_ROLES = {
    "STATIC_REFERENCE_PROXY",
    "HISTORICAL_REANALYSIS",
    "TIME_MATCHED",
    "LIVE_OPERATIONAL",
    "UNKNOWN",
}
_ALLOWED_STATUSES = {"REAL", "MISSING", "BLOCKED", "DEMO", "AVAILABLE_NOT_YET_SELECTED"}


def test_registry_is_not_empty():
    assert len(REGISTRY) >= 6


def test_registry_every_entry_has_a_valid_temporal_role():
    for entry in REGISTRY:
        assert entry.temporal_role in _ALLOWED_TEMPORAL_ROLES, entry.dataset_name


def test_registry_every_entry_has_a_valid_status():
    for entry in REGISTRY:
        assert entry.status in _ALLOWED_STATUSES, entry.dataset_name


def test_registry_no_status_is_demo():
    # DEMO must never enter this real-data registry
    assert all(entry.status != "DEMO" for entry in REGISTRY)


def test_registry_blocked_entries_document_a_reason():
    for entry in REGISTRY:
        if entry.status == "BLOCKED":
            assert len(entry.known_limitations) > 10, entry.dataset_name


def test_registry_entries_serialize_to_dict():
    for entry in REGISTRY:
        d = entry.as_dict()
        assert d["dataset_name"] == entry.dataset_name
        assert isinstance(d["variables_used"], list)
