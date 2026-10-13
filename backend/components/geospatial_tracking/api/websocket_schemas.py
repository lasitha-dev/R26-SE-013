"""Checkpoint 10B Part 16: strict inbound WebSocket message validation.

No arbitrary Python expression, SQL, file path, or serialized object is
ever accepted -- every inbound message is validated against one of
these closed (`extra="forbid"`) Pydantic models before any lookup
happens. `forecast_origin_id` is a bounded plain string
(`max_length=256`), never interpreted as a filesystem path.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FORECAST_ORIGIN_ID_MAX_LENGTH_10B = 256


class _StrictInboundMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str | None = Field(default=None, max_length=256)


DISEASE_MAX_LENGTH_10B = 256
"""FMD-02: bounds the optional inbound `disease` field the same way
`forecast_origin_id` is already bounded (10B Part 16's rule -- no
unbounded string is ever accepted before validation)."""


class SnapshotRequestMessage(_StrictInboundMessage):
    type: Literal["snapshot_request"]
    forecast_origin_id: str = Field(min_length=1, max_length=FORECAST_ORIGIN_ID_MAX_LENGTH_10B)
    # FMD-02: optional -- omitted (the pre-FMD-02 shape every existing
    # frontend/test message already sends) resolves to DEFAULT_DISEASE at
    # the router, reproducing LSD-only behavior unchanged.
    disease: str | None = Field(default=None, max_length=DISEASE_MAX_LENGTH_10B)


class SnapshotRefreshMessage(_StrictInboundMessage):
    type: Literal["snapshot_refresh"]
    forecast_origin_id: str = Field(min_length=1, max_length=FORECAST_ORIGIN_ID_MAX_LENGTH_10B)
    disease: str | None = Field(default=None, max_length=DISEASE_MAX_LENGTH_10B)


class PingMessage(_StrictInboundMessage):
    type: Literal["ping"]


INBOUND_MESSAGE_MODELS_10B = {
    "snapshot_request": SnapshotRequestMessage,
    "snapshot_refresh": SnapshotRefreshMessage,
    "ping": PingMessage,
}
