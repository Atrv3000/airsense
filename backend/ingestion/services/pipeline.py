import logging
from datetime import datetime
import dateutil.parser
from zoneinfo import ZoneInfo
from django.utils import timezone
from core.models import MonitoringStation
from ingestion.models import RawMeasurement
from .air_quality_client import AirQualityClient
from .weather_client import WeatherClient
from .preprocessor import DataPreprocessor
from .station_seeder import seed_mumbai_stations
from aqi_engine.services.aqi_service import AQIService

logger = logging.getLogger(__name__)

class DataPipeline:
    """
    Orchestrates end-to-end data ingestion:
    API Fetch -> Merging -> Preprocessing & Cleaning -> PostgreSQL Storage.
    """

    @classmethod
    def run_ingestion_for_station(cls, station: MonitoringStation, past_days: int = 2, forecast_days: int = 1) -> dict:
        """
        Executes an ingestion cycle for a single monitoring station.
        """
        logger.info(f"Starting ingestion for {station.name} ({station.station_id})...")

        # 1. Fetch Pollutants & Weather in parallel
        aq_data = AirQualityClient.fetch_station_air_quality(
            station.latitude, station.longitude, past_days=past_days, forecast_days=forecast_days, station_id_code=station.station_id
        )
        weather_data = WeatherClient.fetch_weather_for_coords(
            station.latitude, station.longitude, past_days=past_days
        )

        all_timestamps = set(aq_data.keys()).union(set(weather_data.keys()))
        if not all_timestamps:
            logger.warning(f"No data returned for station {station.name}.")
            return {"created": 0, "updated": 0, "total": 0}

        created_count = 0
        updated_count = 0
        tz = ZoneInfo('Asia/Kolkata')

        for t_str in sorted(all_timestamps):
            try:
                # Parse ISO timestamp to timezone-aware datetime
                dt_naive = datetime.fromisoformat(t_str)
                if dt_naive.tzinfo is None:
                    dt_aware = dt_naive.replace(tzinfo=tz)
                else:
                    dt_aware = dt_naive.astimezone(tz)

                # Merge sensor and meteorological dictionaries
                pollutants = aq_data.get(t_str, {})
                weather = weather_data.get(t_str, {})

                raw_record = {
                    "station": station,
                    "recorded_at": dt_aware,
                    "pm25": pollutants.get("pm25"),
                    "pm10": pollutants.get("pm10"),
                    "no2": pollutants.get("no2"),
                    "so2": pollutants.get("so2"),
                    "co": pollutants.get("co"),
                    "o3": pollutants.get("o3"),
                    "temperature": weather.get("temperature"),
                    "humidity": weather.get("humidity"),
                    "wind_speed": weather.get("wind_speed"),
                    "wind_direction": weather.get("wind_direction"),
                    "source": "OPEN_METEO_CAMS_HYBRID"
                }

                # 2. Clean & Sanitize through Preprocessor
                cleaned = DataPreprocessor.clean_record(raw_record)

                # 3. Store idempotently in PostgreSQL
                defaults_payload = {
                    "pm25": cleaned["pm25"],
                    "pm10": cleaned["pm10"],
                    "no2": cleaned["no2"],
                    "so2": cleaned["so2"],
                    "co": cleaned["co"],
                    "o3": cleaned["o3"],
                    "temperature": cleaned["temperature"],
                    "humidity": cleaned["humidity"],
                    "wind_speed": cleaned["wind_speed"],
                    "wind_direction": cleaned["wind_direction"],
                    "is_validated": cleaned["is_validated"],
                    "source": cleaned["source"],
                }

                obj, created = RawMeasurement.objects.update_or_create(
                    station=station,
                    recorded_at=dt_aware,
                    defaults=defaults_payload
                )

                # Calculate CPCB NAQI immediately
                AQIService.calculate_for_measurement(obj)

                if created:
                    created_count += 1
                else:
                    updated_count += 1

            except Exception as e:
                logger.error(f"Error saving measurement at {t_str} for {station.name}: {e}")
                continue

        logger.info(f"Finished {station.name}: {created_count} created, {updated_count} updated.")
        return {
            "created": created_count,
            "updated": updated_count,
            "total": created_count + updated_count
        }

    @classmethod
    def run_full_mumbai_pipeline(cls, past_days: int = 3, forecast_days: int = 1) -> dict:
        """
        Runs ingestion for all registered Mumbai monitoring stations.
        """
        # Ensure stations are seeded
        seed_mumbai_stations()

        active_stations = MonitoringStation.objects.filter(is_active=True)
        summary = {
            "stations_processed": 0,
            "total_records_created": 0,
            "total_records_updated": 0,
            "details": {}
        }

        for station in active_stations:
            res = cls.run_ingestion_for_station(station, past_days=past_days, forecast_days=forecast_days)
            summary["stations_processed"] += 1
            summary["total_records_created"] += res["created"]
            summary["total_records_updated"] += res["updated"]
            summary["details"][station.station_id] = res

        return summary
