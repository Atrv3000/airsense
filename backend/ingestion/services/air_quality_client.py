import os
import logging
import requests
from datetime import datetime, timezone
import dateutil.parser
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class AirQualityClient:
    """
    Dual-source ambient air quality client:
    1. Primary: OpenAQ v3 API using authenticated API key for real ground-level
       monitoring stations in Mumbai.
    2. Fallback: Open-Meteo Air Quality API when ground sensor readings are unavailable.
    """
    OPENAQ_API_BASE = os.getenv("OPENAQ_API_BASE", "https://api.openaq.org/v3")
    OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY", "")
    OPEN_METEO_AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

    @classmethod
    def _extract_location_id(cls, station_id_code: str) -> int | None:
        """
        Extracts integer location ID from station ID (e.g. 'OPENAQ_6927' -> 6927, or '6927' -> 6927).
        """
        if not station_id_code:
            return None
        parts = station_id_code.split("_")
        num_str = parts[-1]
        try:
            return int(num_str)
        except ValueError:
            return None

    @classmethod
    def fetch_openaq_ground_readings(cls, station_id_code: str = None, max_age_hours: int = 72) -> tuple[dict | None, str | None]:
        """
        Queries OpenAQ v3 API for ground sensor readings of a specific location.
        Returns:
            (pollutants_dict, timestamp_iso_local) or (None, None)
        Units are read directly from sensor parameter definitions:
          - co: if units == 'µg/m³' or 'ug/m3', converted to mg/m3 by dividing by 1000.
          - ppb units: converted to µg/m³ using standard conversion factors if mass is unavailable.
        """
        if not cls.OPENAQ_API_KEY:
            return None, None

        location_id = cls._extract_location_id(station_id_code)
        if not location_id:
            return None, None

        headers = {"X-API-Key": cls.OPENAQ_API_KEY}
        now_utc = datetime.now(timezone.utc)

        try:
            # 1. Fetch sensor catalog for location to map sensor ID to pollutant parameter & units
            loc_res = requests.get(f"{cls.OPENAQ_API_BASE}/locations/{location_id}", headers=headers, timeout=8)
            if loc_res.status_code != 200:
                return None, None

            data = loc_res.json().get("results", [])
            if not data:
                return None, None

            sensors_meta = {}
            for s in data[0].get("sensors", []):
                s_id = s.get("id")
                param = s.get("parameter", {})
                sensors_meta[s_id] = {
                    "name": param.get("name", "").lower(),
                    "units": param.get("units", "").lower()
                }

            # 2. Fetch latest readings for this location
            latest_res = requests.get(f"{cls.OPENAQ_API_BASE}/locations/{location_id}/latest", headers=headers, timeout=8)
            if latest_res.status_code != 200:
                return None, None

            items = latest_res.json().get("results", [])
            if not items:
                return None, None

            readings = {}
            latest_reading_time = None
            latest_local_dt_str = None

            for item in items:
                s_id = item.get("sensorsId")
                meta = sensors_meta.get(s_id)
                if not meta:
                    continue

                p_name = meta["name"]
                p_units = meta["units"]
                val = item.get("value")
                dt_info = item.get("datetime", {})
                utc_str = dt_info.get("utc")
                local_str = dt_info.get("local")

                if val is None or val < 0:
                    continue

                # Age check against current time
                if utc_str:
                    try:
                        reading_dt = dateutil.parser.isoparse(utc_str)
                        if reading_dt.tzinfo is None:
                            reading_dt = reading_dt.replace(tzinfo=timezone.utc)

                        # Ignore reading if in the future
                        if reading_dt > now_utc:
                            continue

                        age_hours = (now_utc - reading_dt).total_seconds() / 3600.0
                        if age_hours > max_age_hours:
                            continue

                        if latest_reading_time is None or reading_dt > latest_reading_time:
                            latest_reading_time = reading_dt
                            latest_local_dt_str = local_str
                    except Exception:
                        pass

                val_converted = cls.convert_openaq_value(p_name, p_units, val)
                if val_converted is not None and p_name in ["pm25", "pm10", "no2", "so2", "co", "o3"]:
                    if p_name not in readings:
                        readings[p_name] = val_converted

            if readings and latest_local_dt_str:
                return readings, latest_local_dt_str

        except Exception as e:
            logger.warning(f"OpenAQ ground query error for {station_id_code}: {e}")

        return None, None

    @staticmethod
    def convert_openaq_value(p_name: str, p_units: str, val: float) -> float | None:
        """
        Converts OpenAQ sensor reading to CPCB standard units:
        - CO in mg/m3 (converts from ug/m3 or ppb)
        - NO2, SO2, PM2.5, PM10, O3 in ug/m3 (converts from ppb if needed)
        """
        if val is None or val < 0:
            return None
        val_converted = float(val)
        p_units_clean = (p_units or "").lower()
        if p_name == "co":
            if p_units_clean in ["µg/m³", "ug/m3"]:
                val_converted = round(val_converted / 1000.0, 3)
            elif p_units_clean == "ppb":
                # 1 ppb CO ≈ 1.145 ug/m3 = 0.001145 mg/m3
                val_converted = round((val_converted * 1.145) / 1000.0, 3)
            else:
                val_converted = round(val_converted, 3)
        elif p_name in ["no2", "so2"]:
            if p_units_clean == "ppb":
                factor = 1.88 if p_name == "no2" else 2.62
                val_converted = round(val_converted * factor, 2)
            else:
                val_converted = round(val_converted, 2)
        else:
            val_converted = round(val_converted, 2)
        return val_converted

    @classmethod
    def fetch_openaq_historical_data(
        cls,
        station_id_code: str,
        start_dt: datetime,
        end_dt: datetime
    ) -> dict[str, dict[str, float]]:
        """
        Queries OpenAQ v3 historical sensor hours endpoint (/v3/sensors/{id}/hours)
        for ground-level criteria pollutants at a specific station.
        Returns:
            dict mapping local hour ISO string ("YYYY-MM-DDTHH:00") to pollutant dict
            e.g. {"2026-10-05T12:00": {"pm25": 28.4, "pm10": 65.2, ...}}
        """
        if not cls.OPENAQ_API_KEY:
            return {}

        location_id = cls._extract_location_id(station_id_code)
        if not location_id:
            return {}

        headers = {"X-API-Key": cls.OPENAQ_API_KEY}
        try:
            # 1. Fetch sensor catalog for location
            loc_res = requests.get(
                f"{cls.OPENAQ_API_BASE}/locations/{location_id}/sensors",
                headers=headers,
                timeout=10
            )
            if loc_res.status_code != 200:
                return {}

            sensors_list = loc_res.json().get("results", [])
            if not sensors_list:
                return {}

            # Map criteria pollutants to the most relevant/recent sensor
            target_params = {"pm25", "pm10", "no2", "so2", "co", "o3"}
            param_sensors: dict[str, dict] = {}

            for s in sensors_list:
                p_name = (s.get("parameter", {}).get("name") or "").lower()
                if p_name in ["pm2.5", "pm25"]:
                    p_name = "pm25"
                elif p_name in ["ozone"]:
                    p_name = "o3"

                if p_name in target_params:
                    # Prefer sensors with more recent datetimeLast
                    s_last = (s.get("datetimeLast") or {}).get("utc", "")
                    if p_name not in param_sensors:
                        param_sensors[p_name] = s
                    else:
                        existing_last = (param_sensors[p_name].get("datetimeLast") or {}).get("utc", "")
                        if s_last > existing_last:
                            param_sensors[p_name] = s

            # 2. Fetch hourly readings for each matched sensor
            dt_from_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            dt_to_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            history_by_hour: dict[str, dict[str, float]] = {}

            for p_name, s_meta in param_sensors.items():
                sensor_id = s_meta.get("id")
                units = (s_meta.get("parameter", {}).get("units") or "").lower()
                if not sensor_id:
                    continue

                page = 1
                max_pages = 5  # limit=1000 * 5 = 5000 hours (~208 days coverage)
                while page <= max_pages:
                    params = {
                        "datetime_from": dt_from_str,
                        "datetime_to": dt_to_str,
                        "limit": 1000,
                        "page": page
                    }
                    try:
                        h_res = requests.get(
                            f"{cls.OPENAQ_API_BASE}/sensors/{sensor_id}/hours",
                            headers=headers,
                            params=params,
                            timeout=12
                        )
                        if h_res.status_code != 200:
                            break
                        items = h_res.json().get("results", [])
                        if not items:
                            break

                        for item in items:
                            val = item.get("value")
                            converted = cls.convert_openaq_value(p_name, units, val)
                            if converted is None:
                                continue

                            dt_info = item.get("period", {}).get("datetimeTo", {})
                            local_iso = dt_info.get("local") or dt_info.get("utc")
                            if not local_iso:
                                continue

                            # Normalize to YYYY-MM-DDTHH:00
                            hour_key = local_iso[:13] + ":00"
                            if hour_key not in history_by_hour:
                                history_by_hour[hour_key] = {}
                            history_by_hour[hour_key][p_name] = converted

                        if len(items) < 1000:
                            break
                        page += 1
                    except requests.RequestException:
                        break

            return history_by_hour

        except Exception as e:
            logger.warning(f"Error fetching historical OpenAQ sensor hours for {station_id_code}: {e}")
            return {}

    @classmethod
    def fetch_station_air_quality(
        cls,
        latitude: float,
        longitude: float,
        past_days: int = 2,
        forecast_days: int = 0,
        station_id_code: str = None
    ) -> dict:
        """
        Retrieves hourly air pollutant readings.
        Sets forecast_days=0 by default so future hours are never stored as observations.
        Attaches OpenAQ ground readings to its actual measured timestamp hour.
        Returns a dict mapping timestamp -> {pollutants, 'source': 'OPENAQ_MEASURED' | 'OPEN_METEO_MODELLED'}.
        """
        # forecast_days=1 retrieves current-day hours (pipeline strictly filters out future timestamps > now)
        forecast_days = 1

        params = {
            "latitude": round(latitude, 4),
            "longitude": round(longitude, 4),
            "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
            "timezone": "Asia/Kolkata",
            "past_days": past_days,
            "forecast_days": forecast_days
        }

        now_utc = datetime.now(timezone.utc)
        results = {}

        # 1. Fetch modelled time series baseline from Open-Meteo
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
                    co_mg = round(co_raw / 1000.0, 3) if co_raw is not None else None

                    results[t_str] = {
                        "pm25": pm25_list[i] if i < len(pm25_list) else None,
                        "pm10": pm10_list[i] if i < len(pm10_list) else None,
                        "no2": no2_list[i] if i < len(no2_list) else None,
                        "so2": so2_list[i] if i < len(so2_list) else None,
                        # Open-Meteo CAMS tropospheric model lacks ground-level urban NOx titration,
                        # causing uncalibrated ozone predictions (>300 ug/m3). Only ground sensors provide verified O3.
                        "o3": None,
                        "source": "OPEN_METEO_MODELLED"
                    }
        except requests.RequestException as e:
            logger.error(f"Open-Meteo query error for ({latitude}, {longitude}): {e}")

        # 2. Fetch real ground-level sensor data from OpenAQ and attach to the EXACT matching hour
        ground_data, ground_time_str = cls.fetch_openaq_ground_readings(station_id_code=station_id_code)
        if ground_data and ground_time_str:
            try:
                g_dt = dateutil.parser.isoparse(ground_time_str)
                matching_hour_key = g_dt.strftime("%Y-%m-%dT%H:00")

                if matching_hour_key not in results:
                    results[matching_hour_key] = {}

                for param in ["pm25", "pm10", "no2", "so2", "co", "o3"]:
                    if ground_data.get(param) is not None:
                        results[matching_hour_key][param] = ground_data[param]

                results[matching_hour_key]["source"] = "OPENAQ_MEASURED"
            except Exception as e:
                logger.warning(f"Could not map ground reading time {ground_time_str}: {e}")

        # 3. Fetch optional real-time WAQI telemetry if configured
        try:
            from .cpcb_client import CPCBClient
            cpcb_data, cpcb_time_str = CPCBClient.fetch_station_cpcb_reading(station_id_code=station_id_code)
            if cpcb_data and cpcb_time_str:
                c_dt = dateutil.parser.isoparse(cpcb_time_str)
                matching_hour_key = c_dt.strftime("%Y-%m-%dT%H:00")

                if matching_hour_key not in results:
                    results[matching_hour_key] = {}

                # Supplement meteorological parameters if missing, never overwrite physical concentrations
                for param in ["temperature", "humidity", "wind_speed"]:
                    if cpcb_data.get(param) is not None and results[matching_hour_key].get(param) is None:
                        results[matching_hour_key][param] = cpcb_data[param]

                if "sub_indices" in cpcb_data:
                    results[matching_hour_key]["waqi_sub_indices"] = cpcb_data["sub_indices"]
        except Exception as e:
            logger.warning(f"Could not attach WAQI live observation: {e}")

        return results
