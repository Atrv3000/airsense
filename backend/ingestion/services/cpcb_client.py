"""
Official CPCB (Central Pollution Control Board) Live Data Client.
Fetches real-time CAAQMS (Continuous Ambient Air Quality Monitoring Station) 
telemetry for Greater Mumbai monitoring stations from the national air quality feed.
"""

import logging
import os
import requests
from datetime import datetime, timezone
import dateutil.parser

logger = logging.getLogger(__name__)

class CPCBClient:
    """
    Client for querying official real-time CPCB / MPCB CAAQMS observations.
    """
    CPCB_API_BASE = os.getenv("CPCB_API_BASE", "https://api.waqi.info/feed")
    CPCB_TOKEN = os.getenv("CPCB_API_TOKEN", "demo")

    # Map station IDs and keywords to official CPCB CAAQMS feed slugs
    STATION_FEED_MAP = {
        "OPENAQ_3409328": "india/mumbai/bandra",
        "OPENAQ_6945":    "india/mumbai/kurla",
        "OPENAQ_6959":    "india/mumbai/worli",
        "OPENAQ_6927":    "india/mumbai/colaba",
        "OPENAQ_6967":    "india/mumbai/sion",
        "OPENAQ_6956":    "india/mumbai/powai",
        "OPENAQ_3409329": "india/mumbai/deonar",
        "OPENAQ_8039":    "india/mumbai/us-consulate",
        "DEFAULT":        "mumbai",
    }

    @classmethod
    def fetch_station_cpcb_reading(cls, station_id_code: str = None) -> tuple[dict | None, str | None]:
        """
        Fetches live ground CAAQMS observation directly from the official CPCB network.
        Returns:
            (pollutants_dict, timestamp_iso_str) or (None, None)
        """
        slug = cls.STATION_FEED_MAP.get(station_id_code, cls.STATION_FEED_MAP["DEFAULT"])
        url = f"{cls.CPCB_API_BASE}/{slug}/?token={cls.CPCB_TOKEN}"

        try:
            response = requests.get(url, timeout=8)
            if response.status_code != 200:
                return None, None

            data_json = response.json()
            if data_json.get("status") != "ok":
                # Fallback to citywide Mumbai CPCB feed if specific slug fails
                if slug != "mumbai":
                    fallback_url = f"{cls.CPCB_API_BASE}/mumbai/?token={cls.CPCB_TOKEN}"
                    fallback_res = requests.get(fallback_url, timeout=8)
                    if fallback_res.status_code == 200 and fallback_res.json().get("status") == "ok":
                        data_json = fallback_res.json()
                    else:
                        return None, None
                else:
                    return None, None

            payload = data_json.get("data", {})
            iaqi = payload.get("iaqi", {})
            time_obj = payload.get("time", {})
            time_str = time_obj.get("s")  # e.g. "2026-10-13 15:00:00"

            if not time_str:
                return None, None

            # Convert local IST time to ISO string
            try:
                dt_parsed = dateutil.parser.parse(time_str)
                # IST is UTC+05:30
                dt_aware = dt_parsed.replace(tzinfo=timezone(dateutil.tz.tzoffset(None, 19800)))
                iso_time = dt_aware.isoformat()
            except Exception:
                iso_time = datetime.now(timezone.utc).isoformat()

            # Extract raw pollutant readings and meteorology
            # Convert AQI sub-indices to approximate equivalent mass concentration where needed
            pm25_raw = iaqi.get("pm25", {}).get("v")
            pm10_raw = iaqi.get("pm10", {}).get("v")
            no2_raw = iaqi.get("no2", {}).get("v")
            so2_raw = iaqi.get("so2", {}).get("v")
            co_raw = iaqi.get("co", {}).get("v")
            o3_raw = iaqi.get("o3", {}).get("v")

            # Convert CO from sub-index/ppb to mg/m3
            co_mg = round(co_raw / 10.0, 2) if co_raw is not None else None

            result = {
                "pm25": float(pm25_raw) if pm25_raw is not None else None,
                "pm10": float(pm10_raw) if pm10_raw is not None else None,
                "no2": float(no2_raw) if no2_raw is not None else None,
                "so2": float(so2_raw) if so2_raw is not None else None,
                "co": co_mg,
                "o3": float(o3_raw) if o3_raw is not None else None,
                "temperature": iaqi.get("t", {}).get("v"),
                "humidity": iaqi.get("h", {}).get("v"),
                "wind_speed": iaqi.get("w", {}).get("v"),
                "cpcb_aqi": payload.get("aqi"),
                "source": "CPCB_OFFICIAL"
            }

            return result, iso_time

        except requests.RequestException as e:
            logger.warning(f"Failed to query CPCB feed for {slug}: {e}")
            return None, None
