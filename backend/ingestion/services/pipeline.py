import logging
from datetime import datetime, timezone as py_timezone
import dateutil.parser
from zoneinfo import ZoneInfo
from django.utils import timezone
from core.models import MonitoringStation
from ingestion.models import RawMeasurement, CleanMeasurement
from .air_quality_client import AirQualityClient
from .weather_client import WeatherClient
from .preprocessor import DataPreprocessor
from .station_seeder import seed_mumbai_stations
from aqi_engine.services.aqi_service import AQIService

logger = logging.getLogger(__name__)

class DataPipeline:
    """
    Orchestrates end-to-end data ingestion:
    API Fetch -> Raw Ingest Storage -> Preprocessing & 3h Interpolation -> Clean Measurement Storage -> AQI Calculation.
    Strictly ignores any future timestamp (recorded_at > now).
    """

    @classmethod
    def run_ingestion_for_station(cls, station: MonitoringStation, past_days: int = 2, forecast_days: int = 0) -> dict:
        """
        Executes an ingestion cycle for a single monitoring station.
        forecast_days is forced to 0 so future predictions are never stored as measurements.
        """
        forecast_days = 0
        logger.info(f"Starting ingestion for {station.name} ({station.station_id})...")

        # 1. Fetch Pollutants & Weather
        aq_data = AirQualityClient.fetch_station_air_quality(
            station.latitude, station.longitude, past_days=past_days, forecast_days=0, station_id_code=station.station_id
        )
        weather_data = WeatherClient.fetch_weather_for_coords(
            station.latitude, station.longitude, past_days=past_days, forecast_days=0
        )

        all_timestamps = set(aq_data.keys()).union(set(weather_data.keys()))
        if not all_timestamps:
            logger.warning(f"No data returned for station {station.name}.")
            return {"raw_created": 0, "raw_updated": 0, "clean_saved": 0}

        tz = ZoneInfo('Asia/Kolkata')
        now_dt = timezone.now()

        raw_records_to_process = []

        for t_str in sorted(all_timestamps):
            try:
                dt_naive = datetime.fromisoformat(t_str)
                if dt_naive.tzinfo is None:
                    dt_aware = dt_naive.replace(tzinfo=tz)
                else:
                    dt_aware = dt_naive.astimezone(tz)

                # RULE: Ignore any timestamp in the future!
                if dt_aware > now_dt:
                    continue

                pollutants = aq_data.get(t_str, {})
                weather = weather_data.get(t_str, {})

                source = pollutants.get("source", "OPEN_METEO_MODELLED")

                raw_record = {
                    "station": station,
                    "recorded_at": dt_aware,
                    "pm25": pollutants.get("pm25"),
                    "pm10": pollutants.get("pm10"),
                    "no2": pollutants.get("no2"),
                    "so2": pollutants.get("so2"),
                    "co": pollutants.get("co"),
                    "o3": pollutants.get("o3"),
                    "temperature": weather.get("temperature") if weather.get("temperature") is not None else pollutants.get("temperature"),
                    "humidity": weather.get("humidity") if weather.get("humidity") is not None else pollutants.get("humidity"),
                    "wind_speed": weather.get("wind_speed") if weather.get("wind_speed") is not None else pollutants.get("wind_speed"),
                    "wind_direction": weather.get("wind_direction") if weather.get("wind_direction") is not None else pollutants.get("wind_direction"),
                    "source": source
                }
                raw_records_to_process.append(raw_record)
            except Exception as e:
                logger.error(f"Error parsing timestamp {t_str} for {station.name}: {e}")

        raw_created_count = 0
        raw_updated_count = 0
        saved_raw_objs = []

        # Store in RawMeasurement
        for r_data in raw_records_to_process:
            defaults = {
                "pm25": r_data["pm25"],
                "pm10": r_data["pm10"],
                "no2": r_data["no2"],
                "so2": r_data["so2"],
                "co": r_data["co"],
                "o3": r_data["o3"],
                "temperature": r_data["temperature"],
                "humidity": r_data["humidity"],
                "wind_speed": r_data["wind_speed"],
                "wind_direction": r_data["wind_direction"],
                "source": r_data["source"],
                "is_validated": False,
            }
            raw_obj, created = RawMeasurement.objects.update_or_create(
                station=station,
                recorded_at=r_data["recorded_at"],
                defaults=defaults
            )
            if created:
                raw_created_count += 1
            else:
                raw_updated_count += 1
            saved_raw_objs.append(raw_obj)

        # 2. Preprocess & Clean: range check, spike detection
        clean_dicts = []
        prev_clean = None
        for r_obj in saved_raw_objs:
            r_dict = {
                "station": station,
                "recorded_at": r_obj.recorded_at,
                "pm25": r_obj.pm25,
                "pm10": r_obj.pm10,
                "no2": r_obj.no2,
                "so2": r_obj.so2,
                "co": r_obj.co,
                "o3": r_obj.o3,
                "temperature": r_obj.temperature,
                "humidity": r_obj.humidity,
                "wind_speed": r_obj.wind_speed,
                "wind_direction": r_obj.wind_direction,
                "source": r_obj.source,
                "raw_obj": r_obj
            }
            cleaned = DataPreprocessor.clean_record(r_dict, prev_record=prev_clean)
            cleaned["raw_obj"] = r_obj
            clean_dicts.append(cleaned)
            prev_clean = cleaned

        # 3. Short Gap Time-Based Interpolation (up to 3 hours)
        interpolated_clean_records = DataPreprocessor.interpolate_short_gaps(clean_dicts, max_gap_hours=3)

        # 4. Save CleanMeasurement & trigger AQI calculation
        clean_saved_count = 0
        for c_dict in interpolated_clean_records:
            clean_defaults = {
                "pm25": c_dict["pm25"],
                "pm10": c_dict["pm10"],
                "no2": c_dict["no2"],
                "so2": c_dict["so2"],
                "co": c_dict["co"],
                "o3": c_dict["o3"],
                "temperature": c_dict["temperature"],
                "humidity": c_dict["humidity"],
                "wind_speed": c_dict["wind_speed"],
                "wind_direction": c_dict["wind_direction"],
                "source": c_dict["source"],
                "is_imputed": c_dict.get("is_imputed", False),
                "imputed_fields": c_dict.get("imputed_fields", []),
                "raw_measurement": c_dict["raw_obj"]
            }
            clean_obj, _ = CleanMeasurement.objects.update_or_create(
                station=station,
                recorded_at=c_dict["recorded_at"],
                defaults=clean_defaults
            )
            clean_saved_count += 1

            # Recalculate AQI based on CleanMeasurement / linked RawMeasurement
            try:
                AQIService.calculate_for_measurement(c_dict["raw_obj"])
            except Exception as e:
                logger.error(f"Error calculating AQI at {c_dict['recorded_at']}: {e}")

        logger.info(f"Finished {station.name}: {raw_created_count} raw created, {raw_updated_count} raw updated, {clean_saved_count} clean saved.")
        return {
            "raw_created": raw_created_count,
            "raw_updated": raw_updated_count,
            "clean_saved": clean_saved_count,
            "total": raw_created_count + raw_updated_count
        }

    @classmethod
    def run_full_mumbai_pipeline(cls, past_days: int = 3, forecast_days: int = 0) -> dict:
        """
        Runs ingestion for all registered Mumbai monitoring stations.
        """
        # Ensure stations are seeded with real OpenAQ verified stations
        seed_mumbai_stations()

        active_stations = MonitoringStation.objects.filter(is_active=True)
        summary = {
            "stations_processed": 0,
            "total_raw_created": 0,
            "total_raw_updated": 0,
            "total_records_created": 0,
            "total_records_updated": 0,
            "total_clean_saved": 0,
            "details": {}
        }

        for station in active_stations:
            res = cls.run_ingestion_for_station(station, past_days=past_days, forecast_days=0)
            summary["stations_processed"] += 1
            summary["total_raw_created"] += res["raw_created"]
            summary["total_raw_updated"] += res["raw_updated"]
            summary["total_records_created"] += res["raw_created"]
            summary["total_records_updated"] += res["raw_updated"]
            summary["total_clean_saved"] += res["clean_saved"]
            summary["details"][station.station_id] = res

        return summary
