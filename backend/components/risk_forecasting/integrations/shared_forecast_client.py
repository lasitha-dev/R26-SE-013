"""
Typed Shared-Data Client Contract for Disease Forecasting.

Defines the normalized DTO records and client interface protocol expected
from the future shared data integration layer. Converts typed external inputs
into validated structures for consumption by model service data adapters.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Protocol, runtime_checkable


@dataclass
class SharedForecastRecord:
    """
    Normalized DTO representing a single district-month surveillance record
    supplied by the shared data infrastructure.
    """
    # 1. Primary Identifiers (Required for lookup & alignment)
    disease: str          # "FMD" or "LSD"
    district: str         # Standard Sri Lankan administrative district name
    year: int             # Calendar year (e.g. 2024)
    month: int            # Calendar month (1-12)

    # 2. Model Feature Payload (Required for current model inference)
    # Dictionary mapping feature names (e.g. 'sin_month', 'rainfall_mm') to numeric float values
    feature_values: Dict[str, float] = field(default_factory=dict)

    # 3. Lag Verification Fields (Required only for lag verification)
    outbreak_status_lag1: Optional[float] = None
    lag1_verified: bool = False

    # 4. Metadata / Data Freshness Provenance (Not a model feature)
    source_timestamp: Optional[str] = None
    provenance_id: Optional[str] = None
    data_quality_status: str = "EXACT_REQUESTED_PERIOD"
    is_proxy: bool = False
    source_year: Optional[int] = None
    source_month: Optional[int] = None
    data_age_months: Optional[int] = 0


@runtime_checkable
class SharedForecastDataClient(Protocol):
    """
    Protocol defining the contract for retrieving normalized forecasting input records
    and ground-truth outbreak status from the shared data system.
    """

    def fetch_feature_record(
        self, disease: str, district: str, month: int, year: int
    ) -> Optional[SharedForecastRecord]:
        """
        Retrieves normalized feature record for specified disease, district, and time period.
        Returns None if record is unavailable.
        """
        ...

    def fetch_valid_lag1(
        self, disease: str, district: str, month: int, year: int
    ) -> Optional[Tuple[float, bool]]:
        """
        Retrieves ground-truth outbreak status for preceding month (t-1).
        Returns (outbreak_status, is_verified) or None if unavailable.
        """
        ...
