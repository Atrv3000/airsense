import os
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AirQualityClient:
    """
    Fetches real-time and historical ambient pollutant concentrations
    (PM2.5, PM10, NO2, SO2, CO, O3) for Mumbai stations using public CAMS/Open-Meteo
    and OpenAQ APIs.
    """
    OPEN_METEO_AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

    @classmethod
    def fetch_station_air_quality(cls, latitude: float, longitude: float, past_days: int = 2, forecast_days: int = 1):
        """
        Retrieves hourly air pollutant readings for specific station coordinates.
        Returns a dictionary mapping ISO timestamp strings to pollutant concentrations:
        {
            '2026-10-13T03:00': {
                'pm25': 43.1,
                'pm10': 46.6,
                'no2': 15.9,
                'so2': 25.9,
                'co': 0.48,   # Converted from ug/m3 to mg/m3
                'o3': 170.0
            }
        }
        """
        params = {
            "latitude": round(latitude, 4),
            "longitude": round(longitude, 4),
            "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
            "timezone": "Asia/Kolkata",
            "past_days": past_days,
            "forecast_days": forecast_days
        }

        try:
            response = requests.get(cls.OPEN_METEO_AQ_URL, params=params, timeout=12)
            if response.status_code != 200:
                logger.error(f"Air Quality API error for ({latitude}, {longitude}): HTTP {response.status_code} - {response.text}")
                return {}

            data = response.json()
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            pm25_list = hourly.get("pm2_5", [])
            pm10_list = hourly.get("pm10", [])
            no2_list = hourly.get("nitrogen_dioxide", [])
            so2_list = hourly.get("sulphur_dioxide", [])
            co_list = hourly.get("carbon_monoxide", [])
            o3_list = hourly.get("ozone", [])

            results = {}
            for i in range(len(times)):
                t_str = times[i]
                
                # Convert CO from ug/m3 to mg/m3 (CPCB NAQI expects CO in mg/m3)
                co_raw = co_list[i] if i < len(co_list) else None
                co_mg = round(co_raw / 1000.0, 2) if co_raw is not None else None

                results[t_str] = {
                    "pm25": pm25_list[i] if i < len(pm25_list) else None,
                    "pm10": pm10_list[i] if i < len(pm10_list) else None,
                    "no2": no2_list[i] if i < len(no2_list) else None,
                    "so2": so2_list[i] if i < len(so2_list) else None,
                    "co": co_mg,
                    "o3": o3_list[i] if i < len(o3_list) else None,
                }

            return results

        except requests.RequestException as e:
            logger.error(f"Network error while querying air quality for ({latitude}, {longitude}): {e}")
            return {}
