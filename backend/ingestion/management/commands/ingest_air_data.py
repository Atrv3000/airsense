from django.core.management.base import BaseCommand
from ingestion.services.station_seeder import seed_mumbai_stations
from ingestion.services.pipeline import DataPipeline

class Command(BaseCommand):
    help = "Ingests real-time and historical air quality and weather data for Mumbai monitoring stations"

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=3,
            help='Number of past days of hourly records to fetch (default: 3)'
        )
        parser.add_argument(
            '--seed-only',
            action='store_true',
            help='Only seed Mumbai monitoring stations without querying external APIs'
        )

    def handle(self, *args, **options):
        days = options['days']
        seed_only = options['seed_only']

        self.stdout.write(self.style.NOTICE(">>> 1. Seeding Mumbai monitoring stations..."))
        seed_res = seed_mumbai_stations()
        self.stdout.write(self.style.SUCCESS(
            f"Stations initialized: {seed_res['total']} (Created: {seed_res['created']}, Existing: {seed_res['updated']})"
        ))

        if seed_only:
            self.stdout.write(self.style.SUCCESS("Station seeding completed. Skipping external ingestion."))
            return

        self.stdout.write(self.style.NOTICE(f">>> 2. Ingesting {days} days of hourly data for all stations..."))
        summary = DataPipeline.run_full_mumbai_pipeline(past_days=days)

        self.stdout.write(self.style.SUCCESS(
            f"\n=== Ingestion Completed Successfully ==="
            f"\nStations processed: {summary['stations_processed']}"
            f"\nNew records created: {summary['total_records_created']}"
            f"\nRecords refreshed/updated: {summary['total_records_updated']}"
        ))
