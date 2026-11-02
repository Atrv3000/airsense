"""
Automated Task Scheduler for AirSense Mumbai.
Orchestrates periodic background jobs suitable for Docker containers and headless deployments:
  1. Air quality & meteorological data ingestion (ingest_air_data)
  2. Multi-horizon ML forecast precomputation (precompute_forecasts)
  3. Forecast accuracy verification & rolling error metrics (verify_forecasts)
  4. CPCB health alert evaluation and Expo push delivery (generate_alerts)
Schedules by wall clock to prevent time drift between cycles.
"""

import time
import signal
import sys
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Runs automated background pipeline (ingestion, forecasts, verification, alerts) on a periodic wall-clock schedule."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = True

    def add_arguments(self, parser):
        default_interval = getattr(settings, 'SCHEDULER_INTERVAL_SECONDS', 900)
        parser.add_argument(
            '--interval',
            type=int,
            default=default_interval,
            help=f'Target cycle interval in seconds (default: {default_interval}s / {round(default_interval/60)} minutes, configurable via SCHEDULER_INTERVAL_SECONDS)'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            default=False,
            help='Execute a single pipeline cycle and exit immediately (useful for testing & CI)'
        )
        parser.add_argument(
            '--skip-ingestion',
            action='store_true',
            default=False,
            help='Skip the data ingestion step'
        )
        parser.add_argument(
            '--skip-forecasts',
            action='store_true',
            default=False,
            help='Skip the forecast precomputation step'
        )
        parser.add_argument(
            '--skip-alerts',
            action='store_true',
            default=False,
            help='Skip the alert generation & push notification step'
        )

    def _handle_signal(self, signum, frame):
        self.stdout.write(self.style.WARNING(f"\n[Scheduler] Received signal {signum}. Shutting down gracefully..."))
        self.running = False

    def run_pipeline_cycle(self, options):
        cycle_start = timezone.now()
        self.stdout.write(self.style.NOTICE(
            f"\n======================================================\n"
            f"[Scheduler] Starting Pipeline Cycle at {cycle_start.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
            f"======================================================"
        ))

        # 1. Air Quality & Weather Data Ingestion
        if not options['skip_ingestion']:
            try:
                self.stdout.write(self.style.HTTP_INFO("[Step 1/4] Running air quality & meteorological ingestion..."))
                call_command('ingest_air_data')
                self.stdout.write(self.style.SUCCESS("[Step 1/4] Ingestion completed."))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"[Step 1/4] Ingestion failed: {e}"))
        else:
            self.stdout.write(self.style.WARNING("[Step 1/4] Ingestion skipped (--skip-ingestion)."))

        # 2. Multi-Horizon Forecast Precomputation
        if not options['skip_forecasts']:
            try:
                self.stdout.write(self.style.HTTP_INFO("[Step 2/4] Precomputing multi-horizon ML forecasts..."))
                call_command('precompute_forecasts')
                self.stdout.write(self.style.SUCCESS("[Step 2/4] Forecast precomputation completed."))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"[Step 2/4] Forecast precomputation failed: {e}"))
        else:
            self.stdout.write(self.style.WARNING("[Step 2/4] Forecasts skipped (--skip-forecasts)."))

        # 3. Forecast Verification (Model Monitoring)
        try:
            self.stdout.write(self.style.HTTP_INFO("[Step 3/4] Verifying past forecasts against actual observations..."))
            call_command('verify_forecasts', days=7)
            self.stdout.write(self.style.SUCCESS("[Step 3/4] Forecast verification completed."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"[Step 3/4] Forecast verification failed: {e}"))

        # 4. Alert Evaluation & Push Notification Dispatch
        if not options['skip_alerts']:
            try:
                self.stdout.write(self.style.HTTP_INFO("[Step 4/4] Evaluating CPCB health alerts and dispatching push notifications..."))
                call_command('generate_alerts')
                self.stdout.write(self.style.SUCCESS("[Step 4/4] Alerts evaluated."))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"[Step 4/4] Alerts evaluation failed: {e}"))
        else:
            self.stdout.write(self.style.WARNING("[Step 4/4] Alerts skipped (--skip-alerts)."))

        duration = (timezone.now() - cycle_start).total_seconds()
        self.stdout.write(self.style.SUCCESS(
            f"[Scheduler] Cycle finished in {duration:.1f}s at {timezone.now().strftime('%Y-%m-%d %H:%M:%S %Z')}.\n"
        ))

    def handle(self, *args, **options):
        interval = options['interval']
        run_once = options['once']
        interval_min = max(1, round(interval / 60))

        # Setup graceful signal handlers
        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except (ValueError, AttributeError):
            pass  # Windows non-main thread fallback

        self.stdout.write(self.style.SUCCESS(
            f">>> AirSense Automated Scheduler Initialized.\n"
            f"    Target Wall-Clock Interval: {interval}s ({interval_min} min) | Run Once: {run_once}\n"
            f"    Note: Scheduled by wall clock (next run = start + interval) to prevent execution drift.\n"
        ))

        while self.running:
            cycle_wall_start = time.time()
            self.run_pipeline_cycle(options)

            if run_once or not self.running:
                break

            # Wall-clock scheduling: next run = cycle_wall_start + interval
            elapsed = time.time() - cycle_wall_start
            sleep_duration = max(1.0, interval - elapsed)
            next_run_str = datetime.fromtimestamp(cycle_wall_start + interval).strftime('%H:%M:%S')
            self.stdout.write(f"[Scheduler] Sleeping {sleep_duration:.1f}s until next wall-clock cycle at {next_run_str} (Ctrl+C to stop)...")

            sleep_target = time.time() + sleep_duration
            while self.running and time.time() < sleep_target:
                time.sleep(min(1.0, sleep_target - time.time()))

        self.stdout.write(self.style.SUCCESS("[Scheduler] Stopped cleanly."))
