import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from django.utils import timezone
from django.conf import settings
from core.models import MonitoringStation
from ingestion.models import RawMeasurement, CleanMeasurement, IngestionRun
from .air_quality_client import AirQualityClient
from .weather_client import WeatherClient
from .preprocessor import DataPreprocessor
from .station_seeder import seed_mumbai_stations
from .telemetry import IngestionTelemetry
from aqi_engine.services.aqi_service import AQIService
from ..constants import (
    SOURCE_CPCB, SOURCE_OPENAQ, SOURCE_WAQI, SOURCE_OPEN_METEO,
    is_ground_source, should_override_source
)

logger = logging.getLogger(__name__)

class DataPipeline:
    """
    Orchestrates end-to-end data ingestion:
    API Fetch -> Raw Ingest Storage -> Preprocessing & 3h Interpolation -> Clean Measurement Storage -> AQI Calculation.
    Strictly ignores any future timestamp (recorded_at > now).
    Enforces source priority: CPCB_OFFICIAL > OPENAQ_MEASURED > WAQI_FEED > OPEN_METEO_MODELLED.
    """

    @classmethod
    def run_ingestion_for_station(cls, station: MonitoringStation, past_days: int = 2) -> dict:
        """
        Executes an ingestion cycle for a single monitoring station.
        Fetches today's hours and past_days history; pipeline drops future timestamps.
        """
        logger.info(f"Starting ingestion for {station.name} ({station.station_id})...")

        # 1. Fetch Pollutants & Weather
        aq_data = AirQualityClient.fetch_station_air_quality(
            station.latitude, station.longitude, past_days=past_days, station_id_code=station.station_id
        )
        weather_data = WeatherClient.fetch_weather_for_coords(
            station.latitude, station.longitude, past_days=past_days
        )

        all_timestamps = set(aq_data.keys()).union(set(weather_data.keys()))
        if not all_timestamps:
            logger.warning(f"No data returned for station {station.name}.")
            return {"raw_created": 0, "raw_updated": 0, "clean_saved": 0, "error_count": 0}

        tz = ZoneInfo('Asia/Kolkata')
        now_dt = timezone.now()

        raw_records_to_process = []
        error_count = 0

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

                source = pollutants.get("source", SOURCE_OPEN_METEO)

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
                    "source": source,
                    "waqi_sub_indices": pollutants.get("waqi_sub_indices"),
                    "waqi_overall_aqi": pollutants.get("waqi_overall_aqi"),
                }
                raw_records_to_process.append(raw_record)
            except Exception as e:
                error_count += 1
                logger.error(f"Error parsing timestamp {t_str} for {station.name}: {e}")

        raw_created_count = 0
        raw_updated_count = 0
        saved_raw_objs = []
        waqi_info_by_raw = {}

        # Store in RawMeasurement with strict source-priority preservation
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

            existing_raw = RawMeasurement.objects.filter(
                station=station,
                recorded_at=r_data["recorded_at"]
            ).first()

            if existing_raw:
                # Evaluate source priority: CPCB_OFFICIAL > OPENAQ_MEASURED > WAQI_FEED > OPEN_METEO_MODELLED
                can_override = should_override_source(existing_raw.source, r_data["source"])

                if not can_override:
                    # Existing record has higher or equal priority.
                    # Do not overwrite pollutants; only fill missing weather parameters
                    updated = False
                    for w_field in ["temperature", "humidity", "wind_speed", "wind_direction"]:
                        if getattr(existing_raw, w_field) is None and r_data.get(w_field) is not None:
                            setattr(existing_raw, w_field, r_data[w_field])
                            updated = True
                    if updated:
                        existing_raw.save()
                    raw_updated_count += 1
                    saved_raw_objs.append(existing_raw)
                    continue

                # Incoming record has strictly higher priority -> update values and source
                for k, v in defaults.items():
                    setattr(existing_raw, k, v)
                existing_raw.save()
                raw_updated_count += 1
                saved_raw_objs.append(existing_raw)
                if r_data.get("waqi_sub_indices") or r_data.get("waqi_overall_aqi") is not None:
                    waqi_info_by_raw[existing_raw.id] = (r_data.get("waqi_sub_indices"), r_data.get("waqi_overall_aqi"))
            else:
                raw_obj = RawMeasurement.objects.create(
                    station=station,
                    recorded_at=r_data["recorded_at"],
                    **defaults
                )
                raw_created_count += 1
                saved_raw_objs.append(raw_obj)
                if r_data.get("waqi_sub_indices") or r_data.get("waqi_overall_aqi") is not None:
                    waqi_info_by_raw[raw_obj.id] = (r_data.get("waqi_sub_indices"), r_data.get("waqi_overall_aqi"))

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
            existing_clean = CleanMeasurement.objects.filter(
                station=station,
                recorded_at=c_dict["recorded_at"]
            ).first()

            if existing_clean:
                if not should_override_source(existing_clean.source, c_dict["source"]):
                    clean_obj = existing_clean
                else:
                    for k, v in clean_defaults.items():
                        setattr(existing_clean, k, v)
                    existing_clean.save()
                    clean_obj = existing_clean
            else:
                clean_obj = CleanMeasurement.objects.create(
                    station=station,
                    recorded_at=c_dict["recorded_at"],
                    **clean_defaults
                )
            clean_saved_count += 1

            # Recalculate AQI based on CleanMeasurement / linked RawMeasurement
            try:
                waqi_sub, waqi_overall = waqi_info_by_raw.get(c_dict["raw_obj"].id, (None, None))
                AQIService.calculate_for_measurement(
                    c_dict["raw_obj"],
                    waqi_sub_indices=waqi_sub,
                    waqi_overall_aqi=waqi_overall
                )
            except Exception as e:
                error_count += 1
                logger.error(f"Error calculating AQI at {c_dict['recorded_at']}: {e}")

        # Update station freshness attributes on MonitoringStation model
        latest_ground = RawMeasurement.objects.filter(
            station=station,
            source__in=['CPCB_OFFICIAL', 'OPENAQ_MEASURED', 'WAQI_FEED']
        ).order_by('-recorded_at').first()

        if latest_ground:
            station.last_ground_observation_at = latest_ground.recorded_at
            ground_age_h = (now_dt - latest_ground.recorded_at).total_seconds() / 3600.0
            max_ground_age = getattr(settings, 'GROUND_MAX_AGE_HOURS', 12)
            if ground_age_h > max_ground_age:
                station.consecutive_stale_cycles += 1
            else:
                station.consecutive_stale_cycles = 0
            station.save(update_fields=['last_ground_observation_at', 'consecutive_stale_cycles'])

        logger.info(f"Finished {station.name}: {raw_created_count} raw created, {raw_updated_count} raw updated, {clean_saved_count} clean saved.")
        return {
            "raw_created": raw_created_count,
            "raw_updated": raw_updated_count,
            "clean_saved": clean_saved_count,
            "total": raw_created_count + raw_updated_count,
            "error_count": error_count
        }

    @classmethod
    def run_full_mumbai_pipeline(cls, past_days: int = 3) -> dict:
        """
        Runs ingestion for all registered Mumbai monitoring stations with per-station isolation.
        Saves execution summary to IngestionRun model and updates operational telemetry.
        """
        t0 = time.time()
        start_time = timezone.now()
        IngestionTelemetry.start_pipeline_cycle()

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
            "total_errors": 0,
            "details": {}
        }

        successful_stations = 0
        failed_stations = 0

        for station in active_stations:
            try:
                res = cls.run_ingestion_for_station(station, past_days=past_days)
                summary["stations_processed"] += 1
                summary["total_raw_created"] += res["raw_created"]
                summary["total_raw_updated"] += res["raw_updated"]
                summary["total_records_created"] += res["raw_created"]
                summary["total_records_updated"] += res["raw_updated"]
                summary["total_clean_saved"] += res["clean_saved"]
                errs = res.get("error_count", 0)
                summary["total_errors"] += errs
                summary["details"][station.station_id] = {**res, "status": "SUCCESS" if errs == 0 else "PARTIAL"}
                successful_stations += 1
            except Exception as e:
                failed_stations += 1
                summary["total_errors"] += 1
                IngestionTelemetry.record_ingestion_error()
                logger.error(f"Station {station.station_id} ingestion failed completely: {e}")
                summary["details"][station.station_id] = {
                    "raw_created": 0,
                    "raw_updated": 0,
                    "clean_saved": 0,
                    "total": 0,
                    "error_count": 1,
                    "error": str(e),
                    "status": "FAILED"
                }

        cycle_duration = time.time() - t0
        end_time = timezone.now()

        # Determine overall cycle status
        if failed_stations == 0:
            cycle_status = "SUCCESS"
        elif successful_stations > 0:
            cycle_status = "PARTIAL"
        else:
            cycle_status = "FAILED"

        IngestionTelemetry.finish_pipeline_cycle(duration_sec=cycle_duration, summary=summary, status=cycle_status)

        # Persist to IngestionRun database table for multi-process sharing
        try:
            telemetry_snapshot = IngestionTelemetry.get_full_system_telemetry()
            IngestionRun.objects.create(
                started_at=start_time,
                completed_at=end_time,
                duration_seconds=round(cycle_duration, 2),
                status=cycle_status,
                total_stations=active_stations.count(),
                successful_stations=successful_stations,
                failed_stations=failed_stations,
                station_results=summary["details"],
                provider_telemetry=telemetry_snapshot.get("providers", {})
            )
        except Exception as e:
            logger.warning(f"Could not persist IngestionRun snapshot: {e}")

        return summary
