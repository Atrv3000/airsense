import requests
import logging
from datetime import datetime, timezone
import dateutil.parser

logger = logging.getLogger(__name__)

class WeatherClient:
    """
    Fetches real-time and historical hourly meteorological observations
    from Open-Meteo API for specified coordinates.
    """
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    @classmethod
    def fetch_weather_for_coords(cls, latitude: float, longitude: float, past_days: int = 1):
        """
        Retrieves hourly weather parameters for the given coordinates.
        Returns a dictionary mapping ISO timestamp strings to weather parameters:
        { '2026-10-13T03:00': {'temperature': 28.5, 'humidity': 75.0, 'wind_speed': 12.4, 'wind_direction': 240.0} }
        """
        params = {
            "latitude": round(latitude, 4),
            "longitude": round(longitude, 4),
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m",
            "timezone": "Asia/Kolkata",
            "past_days": past_days,
            "forecast_days": 1
        }

        try:
            response = requests.get(cls.BASE_URL, params=params, timeout=10)
            if response.status_code != 200:
                logger.error(f"Open-Meteo API error: HTTP {response.status_code} - {response.text}")
                return {}

            data = response.json()
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            humids = hourly.get("relative_humidity_2m", [])
            winds = hourly.get("wind_speed_10m", [])
            wdirs = hourly.get("wind_direction_10m", [])

            weather_map = {}
            for i in range(len(times)):
                t_str = times[i]
                # Normalize time string
                weather_map[t_str] = {
                    "temperature": temps[i] if i < len(temps) else None,
                    "humidity": humids[i] if i < len(humids) else None,
                    "wind_speed": winds[i] if i < len(winds) else None,
                    "wind_direction": wdirs[i] if i < len(wdirs) else None,
                }

            return weather_map

        except requests.RequestException as e:
            logger.error(f"Failed to query Open-Meteo for ({latitude}, {longitude}): {e}")
            return {}
