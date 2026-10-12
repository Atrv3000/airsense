from django.core.management.base import BaseCommand
from aqi_engine.services.aqi_service import AQIService
from aqi_engine.models import AQIRecord
from ingestion.models import RawMeasurement

class Command(BaseCommand):
    help = "Calculates CPCB NAQI for all pending or existing RawMeasurement records"

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Recalculate AQI for all RawMeasurements in the database (even if already calculated)'
        )

    def handle(self, *args, **options):
        recalculate_all = options['all']

        if recalculate_all:
            self.stdout.write(self.style.NOTICE("Recalculating AQI for ALL raw measurements..."))
            measurements = RawMeasurement.objects.all().select_related('station')
            count = 0
            for m in measurements:
                AQIService.calculate_for_measurement(m)
                count += 1
            self.stdout.write(self.style.SUCCESS(f"Recalculated AQI for {count} measurements."))
        else:
            self.stdout.write(self.style.NOTICE("Calculating AQI for pending raw measurements..."))
            count = AQIService.calculate_all_pending()
            self.stdout.write(self.style.SUCCESS(f"Processed {count} pending measurements."))

        total_aqi_records = AQIRecord.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Total AQI records in database: {total_aqi_records}"))
