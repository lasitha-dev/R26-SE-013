"""Checkpoint 6B/6B.5: fixed, non-data-derived ST-DBSCAN parameter
CANDIDATES. Shared by `development_source_universe.py` and
`parameter_candidates.py` (single definition avoids either module
importing the other, which would create a cycle).

Neither tuple is a scientific claim about a correct value — both are
finite candidate sets for later development-only sensitivity analysis
(Checkpoint 6B Part 17 / 6B.5 Part 10).
"""

from __future__ import annotations

ACTIVE_WINDOW_DAY_CANDIDATES: tuple[int, ...] = (7, 14, 21, 28)

MIN_CORE_SUPPORT_CANDIDATES: tuple[int, ...] = (2, 3, 4)

MAX_ACTIVE_WINDOW_DAYS: int = max(ACTIVE_WINDOW_DAY_CANDIDATES)
