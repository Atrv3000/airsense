"""
WAQI / CPCB Real-Time Ambient Air Quality Feed Client.
Queries the World Air Quality Index (WAQI / aqicn) API.
Treats reported 'iaqi' values as AQI sub-indices (never converted as raw mass concentrations),
requires an explicit environment API token, avoids attributing city-wide fallback feeds
to specific monitoring stations, and labels all fetched feeds honestly as WAQI_FEED.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
import dateutil.parser
import requests

logger = logging.getLogger(__name__)


class WAQIClient:
    """
    Client for querying real-time ambient air quality observations and sub-indices from WAQI.
    """
    API_BASE = os.getenv("WAQI_API_BASE", "https://api.waqi.info/feed")

    # Known WAQI station slugs for official CAAQMS stations in Mumbai
    STATION_FEED_MAP = {
        "OPENAQ_3409328": "india/mumbai/bandra",
        "OPENAQ_6945":    "india/mumbai/kurla",
        "OPENAQ_6959":    "india/mumbai/worli",
        "OPENAQ_6927":    "india/mumbai/colaba",
        "OPENAQ_6967":    "india/mumbai/sion",
        "OPENAQ_6956":    "india/mumbai/powai",
        "OPENAQ_3409329": "india/mumbai/deonar",
        "OPENAQ_8039":    "india/mumbai/us-consulate",
    }

    @classmethod
    def get_token(cls) -> Optional[str]:
        """
        Retrieves the WAQI API token from environment variables.
        Rejects empty or hardcoded 'demo' tokens to prevent invalid queries.
        """
        token = os.getenv("WAQI_API_TOKEN") or os.getenv("WAQI_TOKEN") or os.getenv("CPCB_API_TOKEN")
        if not token:
            return None
        token = token.strip()
        if token.lower() in ["", "demo"]:
            return None
        return token

    @classmethod
    def parse_waqi_response(cls, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Parses a WAQI API payload.
        Treats 'iaqi' entries strictly as AQI sub-indices, never as physical mass concentrations.
        """
        iaqi = payload.get("iaqi", {})
        time_obj = payload.get("time", {})
        time_str = time_obj.get("s")  # e.g., "2026-10-13 15:00:00"

        iso_time = None
        if time_str:
            try:
                dt_parsed = dateutil.parser.parse(time_str)
                # WAQI Indian stations report IST (UTC+05:30)
                dt_aware = dt_parsed.replace(tzinfo=timezone(dateutil.tz.tzoffset(None, 19800)))
                iso_time = dt_aware.isoformat()
            except Exception:
                iso_time = datetime.now(timezone.utc).isoformat()

        # Extract AQI sub-indices (these are non-dimensional index values, not ug/m3 or mg/m3)
        sub_indices = {}
        for param in ["pm25", "pm10", "no2", "so2", "co", "o3"]:
            val = iaqi.get(param, {}).get("v")
            if val is not None:
                try:
                    sub_indices[param] = float(val)
                except (ValueError, TypeError):
                    pass

        # Meteorological dispersion parameters
        temp = iaqi.get("t", {}).get("v")
        humidity = iaqi.get("h", {}).get("v")
        wind = iaqi.get("w", {}).get("v")

        result = {
            "sub_indices": sub_indices,
            "overall_aqi": payload.get("aqi"),
            "temperature": float(temp) if temp is not None else None,
            "humidity": float(humidity) if humidity is not None else None,
            "wind_speed": float(wind) if wind is not None else None,
            "source": "WAQI_FEED",
            "station_name": payload.get("city", {}).get("name"),
            "attributions": payload.get("attributions", []),
        }
        return result, iso_time

    @classmethod
    def fetch_station_reading(cls, station_id_code: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Fetches live WAQI reading for a specific station.
        Requires a valid token and an established station slug.
        Refuses to fall back to city-wide feeds to prevent false station attribution.
        """
        token = cls.get_token()
        if not token:
            logger.debug("WAQI token is absent or 'demo'. Skipping station WAQI lookup.")
            return None, None

        slug = cls.STATION_FEED_MAP.get(station_id_code)
        if not slug:
            logger.debug(f"No WAQI slug mapping exists for station {station_id_code}.")
            return None, None

        url = f"{cls.API_BASE}/{slug}/?token={token}"
        try:
            response = requests.get(url, timeout=8)
            if response.status_code != 200:
                return None, None

            data_json = response.json()
            if data_json.get("status") != "ok":
                # Do NOT fall back to citywide 'mumbai' feed!
                logger.warning(f"WAQI station lookup failed for {slug}: status={data_json.get('status')}")
                return None, None

            return cls.parse_waqi_response(data_json.get("data", {}))

        except requests.RequestException as e:
            logger.warning(f"Network error querying WAQI for station slug {slug}: {e}")
            return None, None

    @classmethod
    def fetch_city_reading(cls, city_name: str = "mumbai") -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Fetches aggregated city-wide WAQI reading.
        Explicitly flagged as is_city_aggregate=True to avoid attributing it to a single station.
        """
        token = cls.get_token()
        if not token:
            logger.debug("WAQI token is absent or 'demo'. Skipping city WAQI lookup.")
            return None, None

        url = f"{cls.API_BASE}/{city_name}/?token={token}"
        try:
            response = requests.get(url, timeout=8)
            if response.status_code != 200:
                return None, None

            data_json = response.json()
            if data_json.get("status") != "ok":
                return None, None

            result, iso_time = cls.parse_waqi_response(data_json.get("data", {}))
            if result:
                result["is_city_aggregate"] = True
            return result, iso_time

        except requests.RequestException as e:
            logger.warning(f"Network error querying city WAQI feed for {city_name}: {e}")
            return None, None

    # Backward compatibility aliases
    @classmethod
    def fetch_station_cpcb_reading(cls, station_id_code: str = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if not station_id_code:
            return None, None
        return cls.fetch_station_reading(station_id_code)


# Maintain backward-compatible alias
CPCBClient = WAQIClient
