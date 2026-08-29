"""GEO-ANALYSIS-01 enums for the Page-3 "Analysis & Trends" backend
contract.

Deliberately separate from `my_area_enums.py` (a different page, a
different composition of the same underlying scientific read path), but
several constants below are imported VERBATIM from it rather than
redeclared -- `NOMINAL_REACH_DISCLAIMER`, `RELATIVE_SPATIAL_SCORE_LABEL`,
`RELATIVE_SPATIAL_SCORE_TEMPORAL_BASIS`, and
`SCORE_STATUS_CELL_GEOMETRY_NOT_EXPOSED` are the SAME scientific facts
Page 2 already established; Page 3 must never risk a second, subtly
different copy of any of them.
"""

from __future__ import annotations

from enum import Enum

from .my_area_enums import (
    GEOSPATIAL_STUDY_COUNTRY,
    NOMINAL_REACH_DISCLAIMER,
    RELATIVE_SPATIAL_SCORE_LABEL,
    RELATIVE_SPATIAL_SCORE_TEMPORAL_BASIS,
    SCORE_STATUS_CELL_GEOMETRY_NOT_EXPOSED,
)

__all__ = [
    "AnalysisTrendsStatus",
    "HistoricalDataStatus",
    "SelectedOriginAnalyticsStatus",
    "ApparentRateStatus",
    "DirectionContextStatus",
    "RelativeSpatialScoreDistributionStatus",
    "EvaluationStatus",
    "ModelRunComparisonStatus",
    "ConfidenceStatus",
    "DriversStatus",
    "NOMINAL_REACH_DISCLAIMER",
    "RELATIVE_SPATIAL_SCORE_LABEL",
    "RELATIVE_SPATIAL_SCORE_TEMPORAL_BASIS",
    "AREA_SCORE_AVAILABILITY_STATUS",
    "CROSS_SNAPSHOT_SCORE_COMPARISON_STATUS",
    "HISTORICAL_TREND_PERIOD_BASIS_WEEK",
    "HISTORICAL_TREND_PERIOD_BASIS_MONTH",
    "HISTORICAL_TREND_PERIOD_BASIS_YEAR",
    "HISTORICAL_TREND_WEEK_SPAN_THRESHOLD_DAYS",
    "HISTORICAL_TREND_MONTH_SPAN_THRESHOLD_DAYS",
    "HISTORICAL_COUNT_BASIS",
    "ANALYSIS_TRENDS_COUNTRY",
]


class AnalysisTrendsStatus(str, Enum):
    """Top-level result state of one `AnalysisTrendsContext` request.
    Several values are reused VERBATIM from the existing scientific 10A
    contract / `MyAreaStatus` rather than declared as new,
    differently-spelled synonyms -- `UNSUPPORTED_DISEASE`,
    `ORIGIN_NOT_FOUND`, and `ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY`
    are byte-identical to their `_10A` counterparts."""

    OK = "OK"
    PARTIAL = "PARTIAL"
    """Real evidence exists for at least one block, but at least one
    other requested block is honestly unavailable (Section 9's FMD
    example: historical data real and available, model evaluation not
    ready) -- never a silent downgrade to `OK`."""
    UNSUPPORTED_DISEASE = "UNSUPPORTED_DISEASE"
    NO_HISTORICAL_DATA = "NO_HISTORICAL_DATA"
    ORIGIN_NOT_FOUND = "ORIGIN_NOT_FOUND"
    ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY = "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"
    ANALYSIS_INTERNAL_ERROR = "ANALYSIS_INTERNAL_ERROR"
    """Reused verbatim from `ANALYSIS_INTERNAL_ERROR_10A` -- never raised
    deliberately by any gate in this module; reserved for a genuinely
    unexpected read failure."""


class HistoricalDataStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    NO_HISTORICAL_DATA = "NO_HISTORICAL_DATA"


class SelectedOriginAnalyticsStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY = "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"


class ApparentRateStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE_RUNTIME_METRIC = "UNAVAILABLE_RUNTIME_METRIC"


class DirectionContextStatus(str, Enum):
    UNAVAILABLE_RUNTIME_METRIC = "UNAVAILABLE_RUNTIME_METRIC"
    """Always this value, every response, this checkpoint -- see
    `services/analysis_trends/context_service.py`'s module docstring:
    `bearing_deg`/`directional_clarity` are per-GRID-CELL values
    (`RuntimeCellDirection10A`), never a single origin-level scalar, and
    naively arithmetic-averaging bearings (circular data) across cells
    would be a mathematically invalid aggregation this checkpoint does
    not invent."""


class RelativeSpatialScoreDistributionStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE_RUNTIME_METRIC = "UNAVAILABLE_RUNTIME_METRIC"


class EvaluationStatus(str, Enum):
    EVALUATION_METRICS_NOT_AVAILABLE = "EVALUATION_METRICS_NOT_AVAILABLE"
    ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY = "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"


class ModelRunComparisonStatus(str, Enum):
    MODEL_RUN_COMPARISON_UNAVAILABLE = "MODEL_RUN_COMPARISON_UNAVAILABLE"


class ConfidenceStatus(str, Enum):
    CONFIDENCE_NOT_AVAILABLE = "CONFIDENCE_NOT_AVAILABLE"


class DriversStatus(str, Enum):
    DRIVER_DECOMPOSITION_NOT_AVAILABLE = "DRIVER_DECOMPOSITION_NOT_AVAILABLE"


AREA_SCORE_AVAILABILITY_STATUS = SCORE_STATUS_CELL_GEOMETRY_NOT_EXPOSED
"""Section 16: Page 3 must preserve the exact GEO-AREA limitation, not
reopen it -- reused verbatim, never redeclared."""

CROSS_SNAPSHOT_SCORE_COMPARISON_STATUS = "CROSS_SNAPSHOT_SCORE_COMPARISON_NOT_SUPPORTED"

HISTORICAL_TREND_PERIOD_BASIS_WEEK = "WEEK"
HISTORICAL_TREND_PERIOD_BASIS_MONTH = "MONTH"
HISTORICAL_TREND_PERIOD_BASIS_YEAR = "YEAR"

HISTORICAL_TREND_WEEK_SPAN_THRESHOLD_DAYS = 180
"""GEO-ANALYSIS-01H Section 11: real Sri Lanka LSD data spans only 51
days (2020-09-07 to 2020-10-28, 6 unique historical source records
across 5 forecast origins) -- MONTH would collapse this into ~2 bars,
losing almost the entire real temporal signal. A span under ~6 months
uses WEEK instead."""

HISTORICAL_TREND_MONTH_SPAN_THRESHOLD_DAYS = 1095
"""Real Sri Lanka FMD data spans ~3752 days (2009-09-09 to 2019-12-17,
16 records) -- WEEK over that span would be ~536 buckets, 97% empty.
A span of 3+ years uses YEAR instead (~11 points, ~1.5 records/year on
average) -- everything in between uses MONTH. These two thresholds were
chosen from the two real Sri-Lanka-scoped disease corpora actually
observed, not for chart appearance; see `services/analysis_trends/
historical_trend.py::choose_trend_period_basis` for the exact rule and
`GEO-ANALYSIS-01H` real-data smoke evidence in that checkpoint's final
report."""

HISTORICAL_COUNT_BASIS = "HISTORICAL_SOURCE_RECORDS"

ANALYSIS_TRENDS_COUNTRY = GEOSPATIAL_STUDY_COUNTRY
"""GEO-ANALYSIS-01H Section 3/4, re-sourced by GEO-AREA-01S Section 3:
Page 3's own name for the application's real operational study scope.

GEO-AREA-01S discovered My Area (Page 2) still called `list_origins`
with `country=None`, and moved the underlying string constant to the
neutral, already-shared `domain.my_area_enums.GEOSPATIAL_STUDY_COUNTRY`
(that module already supplied several other cross-page constants to
this one, e.g. `NOMINAL_REACH_DISCLAIMER`) so Page 2 and Page 3 consume
the exact same value rather than two independently-declared "Sri Lanka"
literals that could silently drift apart. `ANALYSIS_TRENDS_COUNTRY` is
kept as a same-value re-export, not renamed, so every existing Page-3
file/test that already imports it by this name needed no further
change. Not reused from `services/model_development/sri_lanka_
protocol_7e.py` -- that module's "Sri Lanka" is a held-out MODEL
EVALUATION case-study label (a research-scientific concept), a
different meaning from this live APPLICATION operational scope
constant, and conflating the two would blur a real semantic
distinction."""
