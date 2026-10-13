"""Checkpoint 10B Part 11: deterministic cell chunking for WebSocket
backpressure.

`WS_CELL_CHUNK_SIZE_10B` is an
`ENGINEERING_TRANSPORT_PARAMETER_NOT_SCIENTIFIC_PARAMETER` -- never
tuned against outbreak outcomes. Cells arrive already deterministically
sorted by `scientific_cell_id` (Checkpoint 10A) -- this module only
slices that sequence into fixed-size, non-overlapping, order-preserving
windows. No cell is duplicated, omitted, or reordered, and no
scientific field on any cell is touched.
"""

from __future__ import annotations

import math

WS_CELL_CHUNK_SIZE_10B = 500
CHUNK_PARAMETER_CLASSIFICATION_10B = "ENGINEERING_TRANSPORT_PARAMETER_NOT_SCIENTIFIC_PARAMETER"


def chunk_cells_10b(cells: list[dict], chunk_size: int = WS_CELL_CHUNK_SIZE_10B) -> list[list[dict]]:
    """`n_chunks = ceil(len(cells) / chunk_size)`. Every non-final chunk
    has exactly `chunk_size` cells; the final chunk has 1..chunk_size.
    Zero cells produces zero chunks."""
    if chunk_size < 1:
        raise ValueError(f"chunk_size must be >= 1, got {chunk_size!r}")
    return [cells[i : i + chunk_size] for i in range(0, len(cells), chunk_size)]


def n_chunks_10b(n_cells: int, chunk_size: int = WS_CELL_CHUNK_SIZE_10B) -> int:
    if chunk_size < 1:
        raise ValueError(f"chunk_size must be >= 1, got {chunk_size!r}")
    return math.ceil(n_cells / chunk_size) if n_cells > 0 else 0
