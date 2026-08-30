"""
Forecast Data Provider Abstraction Boundary.
Defines the abstract interface ForecastDataProvider and the concrete CsvForecastDataProvider
implementation to decouple model inference services from data retrieval sources.
"""

from abc import ABC, abstractmethod
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from components.risk_forecasting.config import (
    FMD_DATASET_FILE,
    LSD_DATASET_FILE,
    MONTH_NAMES,
    SRI_LANKA_DISTRICTS,
)

logger = logging.getLogger(__name__)


class ForecastDataProvider(ABC):
    """
    Abstract interface for disease forecasting data retrieval.
    Adapts external data sources (CSV, API, database) to frozen model feature contracts.
    """

    @abstractmethod
    def get_feature_row(
        self,
        disease: str,
        district: str,
        month_num: int,
        year: int,
        feature_cols: List[str],
        district_enc_val: float = 0.0,
    ) -> Tuple[pd.DataFrame, bool, str, Optional[int], Optional[int], Optional[int], str]:
        """
        Extracts or imputes a feature row for a given district, month, and year.

        Returns:
            Tuple containing:
            - row_df (pd.DataFrame): 1-row DataFrame containing requested feature_cols in exact order.
            - fallback_applied (bool): True if data fallback/imputation was required.
            - message (str): Human-readable provenance description.
            - source_year (Optional[int]): Year of source data used.
            - source_month (Optional[int]): Month of source data used.
            - data_age_months (Optional[int]): Age of proxy data in months (0 for exact).
            - data_quality (str): 'EXACT_REQUESTED_PERIOD', 'HISTORICAL_SAME_MONTH_PROXY',
                                 'DISTRICT_HISTORICAL_MEDIAN', or 'NATIONAL_HISTORICAL_MEDIAN'.
        """
        pass

    @abstractmethod
    def get_valid_lag1(
        self, disease: str, district: str, year: int, month: int
    ) -> Optional[float]:
        """
        Retrieves the exact ground-truth Outbreak status (0.0 or 1.0) for the
        immediately preceding calendar month (t-1) for a given district.
        Returns None if no genuine previous-month surveillance record exists.
        """
        pass


class CsvForecastDataProvider(ForecastDataProvider):
    """
    CSV-backed implementation of ForecastDataProvider.
    Uses local historical CSV datasets configured in config.py for offline/standalone execution.
    """

    def __init__(
        self,
        fmd_dataset_path: Optional[Path] = None,
        lsd_dataset_path: Optional[Path] = None,
    ):
        self.fmd_dataset_path = fmd_dataset_path or FMD_DATASET_FILE
        self.lsd_dataset_path = lsd_dataset_path or LSD_DATASET_FILE
        self._datasets: Dict[str, pd.DataFrame] = {}
        self._load_datasets()

    def _load_datasets(self) -> None:
        """Loads FMD and LSD CSV datasets into memory."""
        try:
            if self.fmd_dataset_path.exists():
                self._datasets["FMD"] = pd.read_csv(self.fmd_dataset_path)
            else:
                self._datasets["FMD"] = pd.DataFrame()
        except Exception as e:
            logger.error(f"Failed to load FMD dataset from {self.fmd_dataset_path}: {e}")
            self._datasets["FMD"] = pd.DataFrame()

        try:
            if self.lsd_dataset_path.exists():
                self._datasets["LSD"] = pd.read_csv(self.lsd_dataset_path)
            else:
                self._datasets["LSD"] = pd.DataFrame()
        except Exception as e:
            logger.error(f"Failed to load LSD dataset from {self.lsd_dataset_path}: {e}")
            self._datasets["LSD"] = pd.DataFrame()

    def _get_dataset(self, disease: str) -> pd.DataFrame:
        """Helper to get and validate dataset by disease identifier."""
        if not isinstance(disease, str) or not disease.strip():
            raise ValueError(f"Disease identifier must be a non-empty string. Received: {disease}")
        disease_upper = disease.strip().upper()
        if disease_upper not in ["FMD", "LSD"]:
            raise ValueError(f"Unsupported disease identifier: '{disease}'. Allowed: ['FMD', 'LSD']")
        return self._datasets.get(disease_upper, pd.DataFrame())

    def get_valid_lag1(
        self, disease: str, district: str, year: int, month: int
    ) -> Optional[float]:
        """
        Retrieves the exact ground-truth Outbreak status (0.0 or 1.0) for the
        immediately preceding calendar month (t-1) for a given district.
        """
        df = self._get_dataset(disease)
        if df.empty:
            return None

        if month == 1:
            prev_year = year - 1
            prev_month = 12
        else:
            prev_year = year
            prev_month = month - 1

        prev_match = df[
            (df["district"] == district)
            & (df["year"] == prev_year)
            & (df["month_num"] == prev_month)
        ]

        if not prev_match.empty and pd.notnull(prev_match["Outbreak status"].iloc[0]):
            return float(prev_match["Outbreak status"].iloc[0])

        return None

    def get_feature_row(
        self,
        disease: str,
        district: str,
        month_num: int,
        year: int,
        feature_cols: List[str],
        district_enc_val: float = 0.0,
    ) -> Tuple[pd.DataFrame, bool, str, Optional[int], Optional[int], Optional[int], str]:
        """
        Extracts or imputes feature row from historical dataset with explicit data freshness provenance.
        Guarantees that the returned DataFrame contains strictly requested feature_cols in exact order.
        """
        df = self._get_dataset(disease)
        if df.empty:
            raise RuntimeError(f"Forecasting input dataset for {disease} is empty or unavailable.")

        def _format_row(row_slice: pd.DataFrame) -> pd.DataFrame:
            r = row_slice.copy()
            if "district_enc" in feature_cols:
                r["district_enc"] = district_enc_val
            return r.reindex(columns=feature_cols).fillna(0.0)

        # 1. Exact match
        exact = df[(df["district"] == district) & (df["month_num"] == month_num) & (df["year"] == year)]
        if not exact.empty:
            return (
                _format_row(exact.iloc[[0]]),
                False,
                f"Exact feature row found for {district} ({year}-{month_num:02d}).",
                year,
                month_num,
                0,
                "EXACT_REQUESTED_PERIOD",
            )

        # 2. Historical same-month proxy
        district_month = df[(df["district"] == district) & (df["month_num"] == month_num)]
        if not district_month.empty:
            latest = district_month.sort_values("year", ascending=False).iloc[[0]]
            latest_year = int(latest["year"].iloc[0])
            latest_month = int(latest["month_num"].iloc[0])
            age = ((year - latest_year) * 12) + (month_num - latest_month)
            src_month_name = MONTH_NAMES[latest_month - 1]
            msg = (
                f"No exact year match for {year}. Used latest available surveillance year: "
                f"{latest_year} ({src_month_name} historical same-month proxy)."
            )
            return (
                _format_row(latest),
                True,
                msg,
                latest_year,
                latest_month,
                age,
                "HISTORICAL_SAME_MONTH_PROXY",
            )

        # 3. District historical median
        cols_in_df = [c for c in feature_cols if c in df.columns]
        district_rows = df[df["district"] == district]
        if not district_rows.empty:
            medians = (
                district_rows[cols_in_df]
                .median(numeric_only=True)
                .reindex(feature_cols)
                .fillna(0.0)
            )
            row_df = pd.DataFrame([medians], columns=feature_cols)
            if "district_enc" in feature_cols:
                row_df["district_enc"] = district_enc_val
            return (
                row_df.reindex(columns=feature_cols).fillna(0.0),
                True,
                f"No month-level record found for {district}. Imputed district historical medians.",
                None,
                None,
                None,
                "DISTRICT_HISTORICAL_MEDIAN",
            )

        # 4. National historical median
        global_medians = (
            df[cols_in_df].median(numeric_only=True).reindex(feature_cols).fillna(0.0)
        )
        row_df = pd.DataFrame([global_medians], columns=feature_cols)
        if "district_enc" in feature_cols:
            row_df["district_enc"] = district_enc_val
        return (
            row_df.reindex(columns=feature_cols).fillna(0.0),
            True,
            f"District '{district}' not found in historical data. Imputed national medians.",
            None,
            None,
            None,
            "NATIONAL_HISTORICAL_MEDIAN",
        )


import math
import numpy as np


def _validate_numeric_feature_value(feature_name: str, val: Any) -> float:
    if val is None:
        raise ValueError(f"Required model feature '{feature_name}' is missing (None).")
    if isinstance(val, bool):
        raise ValueError(f"Invalid boolean value for numeric feature '{feature_name}': {val}")
    if not isinstance(val, (int, float, np.number)):
        raise ValueError(f"Invalid non-numeric value for feature '{feature_name}': '{val}' ({type(val).__name__})")
    float_val = float(val)
    if not math.isfinite(float_val):
        raise ValueError(f"Invalid non-finite value (NaN/Infinity) for feature '{feature_name}': {val}")
    return float_val


class SharedApiForecastDataProvider(ForecastDataProvider):
    """
    Adapter implementing ForecastDataProvider by consuming a SharedForecastDataClient instance.
    Transforms normalized DTO records from shared API client into model feature DataFrames
    matching exact feature column orders and data freshness metadata contracts.
    """

    def __init__(self, client: Any):
        if client is None:
            raise RuntimeError("SharedApiForecastDataProvider requires a non-None SharedForecastDataClient instance.")
        self.client = client

    def _validate_disease(self, disease: str) -> str:
        if not isinstance(disease, str) or not disease.strip():
            raise ValueError(f"Disease identifier must be a non-empty string. Received: {disease}")
        disease_upper = disease.strip().upper()
        if disease_upper not in ["FMD", "LSD"]:
            raise ValueError(f"Unsupported disease identifier: '{disease}'. Allowed: ['FMD', 'LSD']")
        return disease_upper

    def get_valid_lag1(
        self, disease: str, district: str, year: int, month: int
    ) -> Optional[float]:
        self._validate_disease(disease)
        if not isinstance(district, str) or not district.strip():
            return None
        formatted_district = district.strip().title()
        if formatted_district in ["Moneragala", "Monaragala"]:
            formatted_district = "Monaragala"
        elif formatted_district in ["Nuwaraeliya", "Nuwara Eliya"]:
            formatted_district = "Nuwara Eliya"

        if formatted_district not in SRI_LANKA_DISTRICTS:
            return None

        if not (2017 <= year <= 2030):
            return None

        if not (1 <= month <= 12):
            return None

        try:
            res = self.client.fetch_valid_lag1(disease, district, month, year)
        except Exception as e:
            logger.error(f"Error fetching lag1 from shared client: {e}")
            return None

        if res is None:
            return None

        status_val, is_verified = res
        if not is_verified or status_val is None:
            return None

        if isinstance(status_val, bool):
            return None

        try:
            float_val = float(status_val)
            if not math.isfinite(float_val):
                return None
            return float_val
        except (ValueError, TypeError):
            return None

    def get_feature_row(
        self,
        disease: str,
        district: str,
        month_num: int,
        year: int,
        feature_cols: List[str],
        district_enc_val: float = 0.0,
    ) -> Tuple[pd.DataFrame, bool, str, Optional[int], Optional[int], Optional[int], str]:
        disease_upper = self._validate_disease(disease)

        if not isinstance(district, str) or not district.strip():
            raise ValueError(f"District must be a non-empty string. Received: {district}")
        formatted_district = district.strip().title()
        if formatted_district in ["Moneragala", "Monaragala"]:
            formatted_district = "Monaragala"
        elif formatted_district in ["Nuwaraeliya", "Nuwara Eliya"]:
            formatted_district = "Nuwara Eliya"

        if formatted_district not in SRI_LANKA_DISTRICTS:
            raise ValueError(f"Unsupported Sri Lankan district: '{district}'")

        if not (2017 <= year <= 2030):
            raise ValueError(f"Year {year} is out of valid schema range (2017-2030).")

        if not (1 <= month_num <= 12):
            raise ValueError(f"Month {month_num} is out of valid range (1-12).")

        record = self.client.fetch_feature_record(disease_upper, district, month_num, year)
        if record is None:
            # Delegate feature queries to CSV fallback as only lag1 is live DB updated
            from components.risk_forecasting.integrations.forecast_data_provider import CsvForecastDataProvider
            csv_provider = CsvForecastDataProvider()
            return csv_provider.get_feature_row(disease, district, month_num, year, feature_cols, district_enc_val)

        if not isinstance(getattr(record, "feature_values", None), dict):
            raise ValueError(f"Invalid feature_values in shared record for '{disease_upper}'")

        if getattr(record, "source_year", None) is not None:
            if not (2017 <= record.source_year <= 2030):
                raise ValueError(f"Invalid source_year in shared record: {record.source_year}")
        if getattr(record, "source_month", None) is not None:
            if not (1 <= record.source_month <= 12):
                raise ValueError(f"Invalid source_month in shared record: {record.source_month}")
        if getattr(record, "data_age_months", None) is not None:
            if record.data_age_months < 0:
                raise ValueError(f"Invalid negative data_age_months in shared record: {record.data_age_months}")

        missing_features = []
        validated_values = {}

        for col in feature_cols:
            if col == "district_enc":
                validated_values["district_enc"] = _validate_numeric_feature_value("district_enc", district_enc_val)
                continue
            if col == "own_outbreak_lag1":
                if "own_outbreak_lag1" in record.feature_values and record.feature_values["own_outbreak_lag1"] is not None:
                    validated_values["own_outbreak_lag1"] = _validate_numeric_feature_value("own_outbreak_lag1", record.feature_values["own_outbreak_lag1"])
                continue

            if col not in record.feature_values:
                missing_features.append(col)
            else:
                val = record.feature_values[col]
                if val is None:
                    missing_features.append(col)
                else:
                    validated_values[col] = _validate_numeric_feature_value(col, val)

        if missing_features:
            if len(missing_features) == 1:
                raise ValueError(f"Required model feature '{missing_features[0]}' is missing in shared API record for {disease_upper}.")
            else:
                raise ValueError(f"Shared API record for {disease_upper} is missing {len(missing_features)} required model features: {missing_features}.")

        row_dict = {col: validated_values.get(col, 0.0) for col in feature_cols}
        row_df = pd.DataFrame([row_dict])
        formatted_df = row_df.reindex(columns=feature_cols)

        fallback_applied = getattr(record, "is_proxy", False)
        data_quality = getattr(record, "data_quality_status", "EXACT_REQUESTED_PERIOD")

        if data_quality in ("DISTRICT_HISTORICAL_MEDIAN", "NATIONAL_HISTORICAL_MEDIAN"):
            source_year = None
            source_month = None
            data_age_months = None
        else:
            source_year = getattr(record, "source_year", year)
            if source_year is None:
                source_year = year
            source_month = getattr(record, "source_month", month_num)
            if source_month is None:
                source_month = month_num
            data_age_months = getattr(record, "data_age_months", 0)
            if data_age_months is None:
                data_age_months = 0

        msg = f"Exact feature row found for {district} ({year}-{month_num:02d})."
        if fallback_applied:
            src_month_name = MONTH_NAMES[source_month - 1] if 1 <= source_month <= 12 else str(source_month)
            msg = (
                f"No exact year match for {year}. Used latest available surveillance year: "
                f"{source_year} ({src_month_name} historical same-month proxy)."
            )
        elif data_quality == "DISTRICT_HISTORICAL_MEDIAN":
            msg = f"No month-level record found for {district}. Imputed district historical medians."
        elif data_quality == "NATIONAL_HISTORICAL_MEDIAN":
            msg = f"District '{district}' not found in historical data. Imputed national medians."

        return (
            formatted_df,
            fallback_applied,
            msg,
            source_year,
            source_month,
            data_age_months,
            data_quality,
        )
