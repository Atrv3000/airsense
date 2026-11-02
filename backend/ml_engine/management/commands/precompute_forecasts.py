"""
Management command to precompute multi-horizon forecasts for all active stations
and store them in the ForecastRecord database table.
"""

from django.core.management.base import BaseCommand
from ml_engine.services.predictor import AQIPredictor

class Command(BaseCommand):
    help = "Precomputes multi-horizon AQI forecasts for all active monitoring stations"

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Forecast horizon in hours (default: 24)'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        self.stdout.write(self.style.NOTICE(f">>> Precomputing {hours}h forecasts for active stations..."))
        count = AQIPredictor.precompute_and_store_forecasts(horizon_hours=hours)
        self.stdout.write(self.style.SUCCESS(f"Successfully generated and stored {count} forecast records."))
