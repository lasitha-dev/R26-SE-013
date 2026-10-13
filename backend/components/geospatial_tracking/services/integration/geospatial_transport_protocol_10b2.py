"""FMD-02: additive active inbound-contract identity correction.

The historical `geospatial_transport_protocol_hash_10b1()`
(`geospatial_transport_protocol_10b1.py`, UNCHANGED by this module, `=
476a7593aafd4011eec840a7ca60cb339302c037f4e00dd7ba11a239ff153a25`,
classified `HISTORICAL_10B1_TRANSPORT_PROTOCOL_HASH` below) bound the
exact inbound message field contract as it stood at Checkpoint 10B.1 --
`snapshot_request`/`snapshot_refresh` did not yet carry an optional
`disease` field, because disease was not yet a runtime-selectable
dimension. `geospatial_transport_protocol_hash_10b2()` is the ACTIVE
contract identity: it binds the historical 10B.1 hash (read-only, never
recomputed differently) plus the one additive fact FMD-02 introduces --
`disease: str | null, max_length=256, optional` now exists on both
`snapshot_request` and `snapshot_refresh`. This mirrors exactly how
Checkpoint 10A.1 additively corrected 10A's incomplete identity and how
10B.1a additively corrected 10B.1's -- the historical dict/hash is a
real, unchanged fact, just incomplete for a runtime dimension that did
not exist yet when it was frozen (never "invalid").

No other field, message type, outbound frame, or transport rule changes
-- `OUTBOUND_CONTRACT_10B1` is reused verbatim (FMD-02 adds no new
outbound field; disease already reaches the client via each frame's
existing `analysis_metadata.disease`/`data.analysis_metadata.disease`
field, unchanged in shape).
"""

from __future__ import annotations

import copy
import hashlib
import json

from .geospatial_transport_protocol_10b1 import (
    HISTORICAL_10B_TRANSPORT_PROTOCOL_HASH,
    INBOUND_CONTRACT_10B1,
    OUTBOUND_CONTRACT_10B1,
    geospatial_transport_protocol_hash_10b1,
)

# The exact frozen historical value -- verified never to change.
HISTORICAL_10B1_TRANSPORT_PROTOCOL_HASH = "476a7593aafd4011eec840a7ca60cb339302c037f4e00dd7ba11a239ff153a25"

HISTORICAL_10B1_HASH_CLASSIFICATION_10B2 = "HISTORICAL_10B1_TRANSPORT_CONTRACT_HASH_PRE_DISEASE_PARAMETERIZATION"
ACTIVE_10B2_HASH_CLASSIFICATION = "ACTIVE_TRANSPORT_PROTOCOL_HASH_FOR_FRONTEND"

DISEASE_FIELD_CONTRACT_10B2 = "str|null, max_length=256, optional -- omitted resolves to DEFAULT_DISEASE (Lumpy skin disease) at the router"

INBOUND_CONTRACT_10B2 = copy.deepcopy(INBOUND_CONTRACT_10B1)
INBOUND_CONTRACT_10B2["snapshot_request"]["disease"] = DISEASE_FIELD_CONTRACT_10B2
INBOUND_CONTRACT_10B2["snapshot_refresh"]["disease"] = DISEASE_FIELD_CONTRACT_10B2


def geospatial_transport_protocol_dict_10b2() -> dict:
    return {
        "historical_10b1_transport_protocol_hash": geospatial_transport_protocol_hash_10b1(),
        "historical_10b1_hash_classification": HISTORICAL_10B1_HASH_CLASSIFICATION_10B2,
        "inbound_contract": INBOUND_CONTRACT_10B2,
        "outbound_contract": OUTBOUND_CONTRACT_10B1,
        "disease_field_contract": DISEASE_FIELD_CONTRACT_10B2,
    }


def geospatial_transport_protocol_hash_10b2() -> str:
    canonical = json.dumps(geospatial_transport_protocol_dict_10b2(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
