from django.core.management.base import BaseCommand
from alerts.services import AlertEngine

class Command(BaseCommand):
    help = "Evaluates observed and forecasted air quality records, generates alerts, and auto-resolves subsided alerts"

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold',
            type=float,
            default=201.0,
            help='AQI threshold to trigger alerts (default: 201.0 for CPCB Poor)'
        )

    def handle(self, *args, **options):
        threshold = options['threshold']
        self.stdout.write(self.style.NOTICE(f">>> Evaluating observed and forecast AQI with threshold={threshold}..."))
        alerts = AlertEngine.evaluate_and_generate_alerts(threshold_override=threshold)
        self.stdout.write(self.style.SUCCESS(f"Evaluation complete. New alerts created: {len(alerts)}"))
        for a in alerts:
            self.stdout.write(f"  - [{a.severity}] {a.title} (AQI {a.aqi_value})")
