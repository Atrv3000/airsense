import os
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class AirQualityClient:
    """
    Dual-source ambient air quality client:
    1. Primary: OpenAQ v3 API using authenticated API key for real ground-level
       monitoring stations in Mumbai (CPCB/MPCB/IITM sensors).
    2. Fallback: Open-Meteo Air Quality API when ground sensor readings are unavailable.
    """
    OPENAQ_API_BASE = os.getenv("OPENAQ_API_BASE", "https://api.openaq.org/v3")
    OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY", "")
    OPEN_METEO_AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

    # 6927: Colaba MPCB, 6945: Kurla MPCB, 6959: Worli IITM, 6965: Borivali East MPCB,
    # 6967: Sion MPCB, 6948: Airport T2 / Vile Parle, 6956: Powai, 6943: Mahape, 11604: Deonar
    STATION_OPENAQ_MAP = {
        "MUM_COLABA": 6927,
        "MUM_WORLI": 6959,
        "MUM_KURLA": 6945,
        "MUM_BORIVALI": 6965,
        "MUM_DEONAR": 11604,
        "MUM_BKC": 11602,      # BKC IITM
        "MUM_VILEPARLE": 6948, # Airport T2 / Vile Parle Terminal
        "MUM_CHEMBUR": 6967,   # Sion / Chembur corridor
        "MUM_MULUND": 5593,    # Thane / Mulund border
        "MUM_SANPADA": 6943,   # Mahape / Navi Mumbai
    }

    @classmethod
    def fetch_openaq_ground_readings(cls, station_id_code: str = None, lat: float = None, lon: float = None):
        """
        Queries OpenAQ v3 API for ground sensor readings.
        Returns a dict of pollutant concentrations, or None if unavailable.
        """
        if not cls.OPENAQ_API_KEY:
            return None

        location_id = cls.STATION_OPENAQ_MAP.get(station_id_code)
        headers = {"X-API-Key": cls.OPENAQ_API_KEY}

        try:
            # 1. If location_id known, query location details & sensors
            if location_id:
                loc_res = requests.get(f"{cls.OPENAQ_API_BASE}/locations/{location_id}", headers=headers, timeout=8)
                if loc_res.status_code == 200:
                    data = loc_res.json().get("results", [])
                    if data:
                        sensors_map = {
                            s["id"]: s.get("parameter", {}).get("name", "").lower()
                            for s in data[0].get("sensors", [])
                        }

                        # Get latest readings
                        latest_res = requests.get(f"{cls.OPENAQ_API_BASE}/locations/{location_id}/latest", headers=headers, timeout=8)
                        if latest_res.status_code == 200:
                            items = latest_res.json().get("results", [])
                            readings = {}
                            for item in items:
                                p_name = sensors_map.get(item.get("sensorsId"))
                                val = item.get("value")
                                # Skip old abandoned readings (e.g. from 2022 or older)
                                dt_local = item.get("datetime", {}).get("local", "")
                                if dt_local and dt_local < "2026-01-01":
                                    continue

                                if p_name and val is not None and p_name not in readings:
                                    readings[p_name] = float(val)

                            if readings:
                                # Standardize values for CPCB calculation
                                co_val = readings.get("co")
                                # If CO is reported in ug/m3 (> 10), convert to mg/m3
                                if co_val is not None and co_val > 10.0:
                                    co_val = round(co_val / 1000.0, 2)

                                return {
                                    "pm25": readings.get("pm25"),
                                    "pm10": readings.get("pm10"),
                                    "no2": readings.get("no2"),
                                    "so2": readings.get("so2"),
                                    "co": co_val,
                                    "o3": readings.get("o3"),
                                }
        except Exception as e:
            logger.warning(f"OpenAQ ground query error for {station_id_code}: {e}")

        return None

    @classmethod
    def fetch_station_air_quality(cls, latitude: float, longitude: float, past_days: int = 2, forecast_days: int = 1, station_id_code: str = None):
        """
        Retrieves hourly air pollutant readings.
        Prioritizes OpenAQ ground sensor for the latest reading when available,
        and uses Open-Meteo for full historical time series.
        """
        params = {
            "latitude": round(latitude, 4),
            "longitude": round(longitude, 4),
            "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
            "timezone": "Asia/Kolkata",
            "past_days": past_days,
            "forecast_days": forecast_days
        }

        results = {}

        # 1. Fetch time series baseline from Open-Meteo
        try:
            response = requests.get(cls.OPEN_METEO_AQ_URL, params=params, timeout=12)
            if response.status_code == 200:
                data = response.json()
                hourly = data.get("hourly", {})
                times = hourly.get("time", [])
                pm25_list = hourly.get("pm2_5", [])
                pm10_list = hourly.get("pm10", [])
                no2_list = hourly.get("nitrogen_dioxide", [])
                so2_list = hourly.get("sulphur_dioxide", [])
                co_list = hourly.get("carbon_monoxide", [])
                o3_list = hourly.get("ozone", [])

                for i in range(len(times)):
                    t_str = times[i]
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
        except requests.RequestException as e:
            logger.error(f"Open-Meteo query error for ({latitude}, {longitude}): {e}")

        # 2. Layer real ground-level sensor data from OpenAQ onto the latest timestamp
        ground_data = cls.fetch_openaq_ground_readings(station_id_code=station_id_code, lat=latitude, lon=longitude)
        if ground_data and results:
            latest_time = sorted(results.keys())[-1]
            # Replace/supplement the latest reading with actual ground sensor reading
            latest_rec = results[latest_time]
            for param in ["pm25", "pm10", "no2", "so2", "co", "o3"]:
                if ground_data.get(param) is not None:
                    latest_rec[param] = ground_data[param]

        return results
