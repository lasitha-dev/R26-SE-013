"""
Forecast Data Provider Abstraction Boundary.
Defines the abstract interface ForecastDataProvider and the concrete CsvForecastDataProvider
implementation to decouple model inference services from data retrieval sources.
"""

from abc import ABC, abstractmethod
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd

from backend.components.risk_forecasting.config import (
    FMD_DATASET_FILE,
    LSD_DATASET_FILE,
    MONTH_NAMES,
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
