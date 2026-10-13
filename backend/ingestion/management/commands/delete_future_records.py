from django.core.management.base import BaseCommand
from django.utils import timezone
from ingestion.models import RawMeasurement, CleanMeasurement
from aqi_engine.models import AQIRecord

class Command(BaseCommand):
    help = "Deletes any measurement and AQI rows with recorded_at in the future (> now)"

    def handle(self, *args, **options):
        now = timezone.now()
        self.stdout.write(self.style.NOTICE(f"Checking for future records beyond {now}..."))

        future_raw = RawMeasurement.objects.filter(recorded_at__gt=now)
        raw_count = future_raw.count()

        future_clean = CleanMeasurement.objects.filter(recorded_at__gt=now)
        clean_count = future_clean.count()

        future_aqi = AQIRecord.objects.filter(recorded_at__gt=now)
        aqi_count = future_aqi.count()

        future_aqi.delete()
        future_clean.delete()
        future_raw.delete()

        self.stdout.write(self.style.SUCCESS(
            f"Successfully purged future rows:\n"
            f"  - RawMeasurement: {raw_count} deleted\n"
            f"  - CleanMeasurement: {clean_count} deleted\n"
            f"  - AQIRecord: {aqi_count} deleted"
        ))
