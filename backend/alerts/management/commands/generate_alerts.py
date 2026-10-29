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
        parser.add_argument(
            '--no-push',
            action='store_true',
            default=False,
            help='Skip sending real push notifications via Expo'
        )

    def handle(self, *args, **options):
        threshold = options['threshold']
        send_push = not options['no_push']
        self.stdout.write(self.style.NOTICE(f">>> Evaluating observed and forecast AQI with threshold={threshold} (send_push={send_push})..."))
        alerts = AlertEngine.evaluate_and_generate_alerts(threshold_override=threshold, send_push=send_push)
        self.stdout.write(self.style.SUCCESS(f"Evaluation complete. New alerts created: {len(alerts)}"))
        for a in alerts:
            self.stdout.write(f"  - [{a.severity}] {a.title} (AQI {a.aqi_value})")
