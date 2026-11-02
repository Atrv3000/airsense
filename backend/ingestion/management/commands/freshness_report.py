from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import MonitoringStation
from ingestion.models import RawMeasurement
from aqi_engine.models import AQIRecord
from ingestion.services.cpcb_client import WAQIClient
from ingestion.services.air_quality_client import AirQualityClient

class Command(BaseCommand):
    help = "Diagnoses data freshness per active monitoring station across all sources"

    def handle(self, *args, **options):
        now = timezone.now()
        stations = MonitoringStation.objects.filter(is_active=True).order_by('name')
        self.stdout.write(f"\n=======================================================")
        self.stdout.write(f" AIRSENSE DATA FRESHNESS REPORT — {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        self.stdout.write(f" Total Active Stations: {stations.count()}")
        self.stdout.write(f"=======================================================\n")

        sources = ['OPENAQ_MEASURED', 'WAQI_FEED', 'CPCB_OFFICIAL', 'OPEN_METEO_MODELLED']
        ground_sources = ['OPENAQ_MEASURED', 'WAQI_FEED', 'CPCB_OFFICIAL']

        for st in stations:
            self.stdout.write(self.style.MIGRATE_HEADING(f"[{st.station_id}] {st.name}"))

            # 1. Latest RawMeasurement for each source
            self.stdout.write("  Raw Measurements by Source:")
            latest_ground_dt = None
            for src in sources:
                latest_raw = RawMeasurement.objects.filter(station=st, source=src).order_by('-recorded_at').first()
                if latest_raw:
                    age_h = (now - latest_raw.recorded_at).total_seconds() / 3600.0
                    self.stdout.write(f"    - {src:<20}: {latest_raw.recorded_at.isoformat()} ({age_h:.1f}h ago)")
                    if src in ground_sources:
                        if latest_ground_dt is None or latest_raw.recorded_at > latest_ground_dt:
                            latest_ground_dt = latest_raw.recorded_at
                else:
                    self.stdout.write(f"    - {src:<20}: None")

            # 2. Latest AQIRecord
            latest_aqi = AQIRecord.objects.filter(station=st).select_related('raw_measurement').order_by('-recorded_at').first()
            if latest_aqi:
                aqi_src = latest_aqi.raw_measurement.source if latest_aqi.raw_measurement else "UNKNOWN"
                aqi_age_h = (now - latest_aqi.recorded_at).total_seconds() / 3600.0
                self.stdout.write(f"  Latest AQIRecord       : {latest_aqi.recorded_at.isoformat()} ({aqi_age_h:.1f}h ago) | AQI={latest_aqi.overall_aqi} | Source={aqi_src}")
            else:
                self.stdout.write("  Latest AQIRecord       : None")

            # 3. Hours since last ground observation
            if latest_ground_dt:
                ground_age_h = (now - latest_ground_dt).total_seconds() / 3600.0
                self.stdout.write(f"  Ground Data Freshness  : {latest_ground_dt.isoformat()} ({ground_age_h:.1f}h ago)")
            else:
                self.stdout.write(self.style.WARNING("  Ground Data Freshness  : NO GROUND OBSERVATIONS FOUND"))

            # 4. Upstream identifiers check
            openaq_id = AirQualityClient._extract_location_id(st.station_id)
            waqi_slug = WAQIClient.STATION_FEED_MAP.get(st.station_id)
            self.stdout.write(f"  Upstream Mapping       : OpenAQ Location ID={openaq_id} | WAQI Slug={waqi_slug}\n")
