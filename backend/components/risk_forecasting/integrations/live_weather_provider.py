import calendar
import datetime
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx
import pandas as pd

from components.risk_forecasting.config import (
    SRI_LANKA_DISTRICT_CENTROIDS,
    SRI_LANKA_DISTRICTS,
)
from components.risk_forecasting.integrations.forecast_data_provider import (
    ForecastDataProvider,
)

logger = logging.getLogger(__name__)


class LiveWeatherForecastDataProvider(ForecastDataProvider):

    def __init__(
        self,
        fallback_provider: ForecastDataProvider,
        cache_ttl_seconds: int = 21600,
    ):
        self.fallback_provider = fallback_provider
        self.cache_ttl_seconds = cache_ttl_seconds
        self.cache: Dict[Tuple[str, int, int], Dict[str, Any]] = {}

    def _get_metrics(self, district: str, month: int, year: int) -> Dict[str, Any]:
        formatted_district = district.strip().title()
        if formatted_district in ["Moneragala", "Monaragala"]:
            formatted_district = "Monaragala"
        elif formatted_district in ["Nuwaraeliya", "Nuwara Eliya"]:
            formatted_district = "Nuwara Eliya"

        if formatted_district not in SRI_LANKA_DISTRICTS:
            raise ValueError(f"Unsupported Sri Lankan district: '{district}'")

        centroid = SRI_LANKA_DISTRICT_CENTROIDS.get(formatted_district)
        if not centroid:
            raise ValueError(f"No coordinates found for district: '{formatted_district}'")

        if not (1 <= month <= 12):
            raise ValueError(f"Month {month} is out of range 1-12")

        key = (formatted_district, month, year)
        now_ts = time.time()
        if key in self.cache:
            cached = self.cache[key]
            if now_ts - cached["timestamp"] < self.cache_ttl_seconds:
                return cached

        start_date = f"{year}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        end_date = f"{year}-{month:02d}-{last_day:02d}"

        today = datetime.date.today()
        is_historical = (year < today.year) or (year == today.year and month < today.month)

        if is_historical:
            url = "https://archive-api.open-meteo.com/v1/archive"
        else:
            url = "https://api.open-meteo.com/v1/forecast"

        params = {
            "latitude": centroid["lat"],
            "longitude": centroid["lon"],
            "start_date": start_date,
            "end_date": end_date,
            "daily": "precipitation_sum,temperature_2m_mean,wind_speed_10m_max",
            "hourly": "precipitation,relative_humidity_2m",
            "timezone": "auto"
        }

        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()

        if "daily" not in data or "hourly" not in data:
            raise ValueError("Invalid Open-Meteo response format")

        daily = data["daily"]
        precip_sum_list = daily.get("precipitation_sum", [])
        temp_mean_list = daily.get("temperature_2m_mean", [])
        wind_max_list = daily.get("wind_speed_10m_max", [])

        clean_precip_sum = [p for p in precip_sum_list if p is not None]
        clean_temp_mean = [t for t in temp_mean_list if t is not None]
        clean_wind_max = [w for w in wind_max_list if w is not None]

        if not clean_precip_sum:
            raise ValueError("No valid precipitation data returned")
        rain_sum = float(sum(clean_precip_sum))
        rfq_count = float(sum(1 for p in clean_precip_sum if p >= 1.0))

        if not clean_temp_mean:
            raise ValueError("No valid temperature data returned")
        temp_mean = float(sum(clean_temp_mean) / len(clean_temp_mean))

        if not clean_wind_max:
            raise ValueError("No valid wind speed data returned")
        wind_mean = float(sum(clean_wind_max) / len(clean_wind_max))

        hourly = data["hourly"]
        hourly_precip = hourly.get("precipitation", [])
        humidity_list = hourly.get("relative_humidity_2m", [])

        clean_hourly_precip = [p for p in hourly_precip if p is not None]
        clean_humidity = [h for h in humidity_list if h is not None]

        if not clean_humidity:
            raise ValueError("No valid humidity data returned")
        humidity_mean = float(sum(clean_humidity) / len(clean_humidity))

        if not clean_hourly_precip:
            raise ValueError("No valid hourly precipitation data returned")
        n_hourly = len(clean_hourly_precip)
        if n_hourly >= 3:
            r3h_max = float(max(sum(clean_hourly_precip[i:i+3]) for i in range(n_hourly - 2)))
        else:
            r3h_max = float(sum(clean_hourly_precip))

        cached_val = {
            "rain_sum": rain_sum,
            "rfq_count": rfq_count,
            "temp_mean": temp_mean,
            "wind_mean": wind_mean,
            "humidity_mean": humidity_mean,
            "r3h_max": r3h_max,
            "timestamp": now_ts
        }
        self.cache[key] = cached_val
        return cached_val

    def get_feature_row(
        self,
        disease: str,
        district: str,
        month_num: int,
        year: int,
        feature_cols: List[str],
        district_enc_val: float = 0.0,
    ) -> Tuple[pd.DataFrame, bool, str, Optional[int], Optional[int], Optional[int], str]:
        base_df, fallback_applied, fallback_message, source_year, source_month, data_age_months, data_quality = (
            self.fallback_provider.get_feature_row(
                disease, district, month_num, year, feature_cols, district_enc_val
            )
        )

        try:
            year_t, month_t = year, month_num
            if month_num == 1:
                year_t1, month_t1 = year - 1, 12
            else:
                year_t1, month_t1 = year, month_num - 1

            if month_t1 == 1:
                year_t2, month_t2 = year_t1 - 1, 12
            else:
                year_t2, month_t2 = year_t1, month_t1 - 1

            metrics_t = self._get_metrics(district, month_t, year_t)
            metrics_t1 = self._get_metrics(district, month_t1, year_t1)
            metrics_t2 = self._get_metrics(district, month_t2, year_t2)

            row_df = base_df.copy()
            if "rainfall_mm" in row_df.columns:
                row_df["rainfall_mm"] = metrics_t["rain_sum"]
            if "rain_lag1" in row_df.columns:
                row_df["rain_lag1"] = metrics_t1["rain_sum"]
            if "rain_lag2" in row_df.columns:
                row_df["rain_lag2"] = metrics_t2["rain_sum"]
            if "temp_lag1" in row_df.columns:
                row_df["temp_lag1"] = metrics_t1["temp_mean"]
            if "humidity" in row_df.columns:
                row_df["humidity"] = metrics_t["humidity_mean"]
            if "humidity_lag1" in row_df.columns:
                row_df["humidity_lag1"] = metrics_t1["humidity_mean"]
            if "wind_speed" in row_df.columns:
                row_df["wind_speed"] = metrics_t["wind_mean"]
            if "wind_lag1" in row_df.columns:
                row_df["wind_lag1"] = metrics_t1["wind_mean"]
            if "rfq" in row_df.columns:
                row_df["rfq"] = metrics_t["rfq_count"]
            if "rfq_lag1" in row_df.columns:
                row_df["rfq_lag1"] = metrics_t1["rfq_count"]
            if "r3h" in row_df.columns:
                row_df["r3h"] = metrics_t["r3h_max"]

            return (
                row_df,
                False,
                "LIVE_WEATHER_API: Meteorological features sourced from Open-Meteo live API.",
                year,
                month_num,
                0,
                "EXACT_REQUESTED_PERIOD"
            )
        except Exception as e:
            logger.error(f"Live weather lookup failed: {e}")
            return (
                base_df,
                True,
                f"Weather API request failed; used historical fallback. Original: {fallback_message}",
                source_year,
                source_month,
                data_age_months,
                data_quality
            )

    def get_valid_lag1(
        self, disease: str, district: str, year: int, month: int
    ) -> Optional[float]:
        return self.fallback_provider.get_valid_lag1(disease, district, year, month)
