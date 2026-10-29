import requests
import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import MonitoringStation
from ingestion.models import RawMeasurement, CleanMeasurement
from ingestion.services.preprocessor import DataPreprocessor
from ingestion.services.station_seeder import seed_mumbai_stations
from aqi_engine.services.aqi_service import AQIService
from ingestion.services.air_quality_client import AirQualityClient

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Backfills historical hourly air quality and weather records for Mumbai stations over specified months/days"

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of past days to backfill (default: 90 days = ~3 months)'
        )
        parser.add_argument(
            '--station',
            type=str,
            default=None,
            help='Optional specific station ID (e.g. OPENAQ_6927)'
        )

    def handle(self, *args, **options):
        days = options['days']
        station_filter = options['station']

        self.stdout.write(self.style.NOTICE(f">>> 1. Initializing verified Mumbai monitoring stations..."))
        seed_mumbai_stations()

        stations_qs = MonitoringStation.objects.filter(is_active=True)
        if station_filter:
            stations_qs = stations_qs.filter(station_id=station_filter)

        total_stations = stations_qs.count()
        self.stdout.write(self.style.NOTICE(f">>> 2. Starting historical backfill for {total_stations} station(s) across past {days} days..."))

        end_date = (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        start_date = (timezone.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        self.stdout.write(self.style.NOTICE(f"Date range: {start_date} to {end_date}"))

        tz = ZoneInfo("Asia/Kolkata")
        now_dt = timezone.now()

        total_raw_created = 0
        total_clean_saved = 0

        for station in stations_qs:
            self.stdout.write(f"Fetching archive for {station.name} ({station.station_id})...")

            # 1. Fetch Air Quality Archive
            aq_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
            aq_params = {
                "latitude": round(station.latitude, 4),
                "longitude": round(station.longitude, 4),
                "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
                "timezone": "Asia/Kolkata",
                "start_date": start_date,
                "end_date": end_date
            }

            # 2. Fetch Weather Archive
            w_url = "https://archive-api.open-meteo.com/v1/archive"
            w_params = {
                "latitude": round(station.latitude, 4),
                "longitude": round(station.longitude, 4),
                "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m",
                "timezone": "Asia/Kolkata",
                "start_date": start_date,
                "end_date": end_date
            }

            try:
                aq_res = requests.get(aq_url, params=aq_params, timeout=20)
                w_res = requests.get(w_url, params=w_params, timeout=20)

                if aq_res.status_code != 200 or w_res.status_code != 200:
                    self.stdout.write(self.style.WARNING(f"Failed to fetch archive for {station.name}: AQ {aq_res.status_code}, Weather {w_res.status_code}"))
                    continue

                aq_hourly = aq_res.json().get("hourly", {})
                w_hourly = w_res.json().get("hourly", {})

                times = aq_hourly.get("time", [])
                pm25 = aq_hourly.get("pm2_5", [])
                pm10 = aq_hourly.get("pm10", [])
                no2 = aq_hourly.get("nitrogen_dioxide", [])
                so2 = aq_hourly.get("sulphur_dioxide", [])
                co = aq_hourly.get("carbon_monoxide", [])
                o3 = aq_hourly.get("ozone", [])

                temps = w_hourly.get("temperature_2m", [])
                humids = w_hourly.get("relative_humidity_2m", [])
                winds = w_hourly.get("wind_speed_10m", [])
                wdirs = w_hourly.get("wind_direction_10m", [])

                # 3. Fetch OpenAQ v3 historical ground sensor hours if available
                start_dt_utc = timezone.now() - timedelta(days=days)
                end_dt_utc = timezone.now()
                openaq_history = AirQualityClient.fetch_openaq_historical_data(
                    station_id_code=station.station_id,
                    start_dt=start_dt_utc,
                    end_dt=end_dt_utc
                )
                if openaq_history:
                    self.stdout.write(f"  Retrieved OpenAQ ground measurements for {len(openaq_history)} hours.")

                station_measured_count = 0
                station_modelled_count = 0

                raw_objs = []
                for i in range(len(times)):
                    t_str = times[i]
                    dt_naive = datetime.fromisoformat(t_str)
                    dt_aware = dt_naive.replace(tzinfo=tz)

                    if dt_aware > now_dt:
                        continue

                    co_raw = co[i] if i < len(co) else None
                    co_mg = round(co_raw / 1000.0, 3) if co_raw is not None else None

                    # Check if OpenAQ measured ground reading exists for this hour
                    hour_key = dt_aware.strftime("%Y-%m-%dT%H:00")
                    openaq_hour = openaq_history.get(hour_key, {})

                    if openaq_hour:
                        station_measured_count += 1
                        record_source = "OPENAQ_MEASURED"
                        pm25_val = openaq_hour.get("pm25", pm25[i] if i < len(pm25) else None)
                        pm10_val = openaq_hour.get("pm10", pm10[i] if i < len(pm10) else None)
                        no2_val = openaq_hour.get("no2", no2[i] if i < len(no2) else None)
                        so2_val = openaq_hour.get("so2", so2[i] if i < len(so2) else None)
                        co_val = openaq_hour.get("co", co_mg)
                        o3_val = openaq_hour.get("o3", o3[i] if i < len(o3) else None)
                    else:
                        station_modelled_count += 1
                        record_source = "OPEN_METEO_MODELLED"
                        pm25_val = pm25[i] if i < len(pm25) else None
                        pm10_val = pm10[i] if i < len(pm10) else None
                        no2_val = no2[i] if i < len(no2) else None
                        so2_val = so2[i] if i < len(so2) else None
                        co_val = co_mg
                        o3_val = o3[i] if i < len(o3) else None

                    defaults = {
                        "pm25": pm25_val,
                        "pm10": pm10_val,
                        "no2": no2_val,
                        "so2": so2_val,
                        "co": co_val,
                        "o3": o3_val,
                        "temperature": temps[i] if i < len(temps) else None,
                        "humidity": humids[i] if i < len(humids) else None,
                        "wind_speed": winds[i] if i < len(winds) else None,
                        "wind_direction": wdirs[i] if i < len(wdirs) else None,
                        "source": record_source,
                        "is_validated": True
                    }

                    raw_obj, created = RawMeasurement.objects.update_or_create(
                        station=station,
                        recorded_at=dt_aware,
                        defaults=defaults
                    )
                    if created:
                        total_raw_created += 1
                    raw_objs.append(raw_obj)

                # Preprocess and save CleanMeasurement
                clean_dicts = []
                prev_clean = None
                for r_obj in raw_objs:
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
                    c = DataPreprocessor.clean_record(r_dict, prev_record=prev_clean)
                    c["raw_obj"] = r_obj
                    clean_dicts.append(c)
                    prev_clean = c

                interpolated = DataPreprocessor.interpolate_short_gaps(clean_dicts, max_gap_hours=3)

                for c_dict in interpolated:
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
                    CleanMeasurement.objects.update_or_create(
                        station=station,
                        recorded_at=c_dict["recorded_at"],
                        defaults=clean_defaults
                    )
                    total_clean_saved += 1
                    AQIService.calculate_for_measurement(c_dict["raw_obj"])

                self.stdout.write(self.style.SUCCESS(
                    f"  Processed {len(raw_objs)} records for {station.name} "
                    f"(Measured: {station_measured_count}, Modelled: {station_modelled_count})."
                ))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error backfilling {station.name}: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"\n=== Historical Backfill Completed ===\n"
            f"Raw records added/updated: {total_raw_created}\n"
            f"Clean measurements saved: {total_clean_saved}"
        ))
