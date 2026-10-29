"""
Management command to verify past ForecastRecord rows against actual AQIRecord observations
and report rolling verification metrics per forecast horizon.
"""

from django.core.management.base import BaseCommand
from ml_engine.services.forecast_verifier import ForecastVerifier


class Command(BaseCommand):
    help = "Verifies elapsed ForecastRecord predictions against actual ground-truth AQIRecord observations."

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Rolling performance evaluation window in days (default: 7)'
        )
        parser.add_argument(
            '--station',
            type=str,
            default=None,
            help='Optional station ID filter (e.g. OPENAQ_6927)'
        )

    def handle(self, *args, **options):
        days = options.get('days', 7)
        station_id = options.get('station')

        self.stdout.write(self.style.NOTICE(f"\nRunning forecast verification (evaluating elapsed target timestamps)..."))
        verify_summary = ForecastVerifier.verify_past_forecasts(station_id=station_id)

        self.stdout.write(self.style.SUCCESS(
            f"Verification scan complete:\n"
            f"  - Candidates evaluated: {verify_summary['total_candidates']}\n"
            f"  - Newly verified:       {verify_summary['verified_count']}\n"
            f"  - Unmatched:            {verify_summary['unmatched_count']}"
        ))

        # Retrieve rolling performance metrics
        metrics = ForecastVerifier.get_rolling_metrics(days=days, station_id=station_id)

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS(f"     AIRSENSE MUMBAI - ROLLING FORECAST VERIFICATION ({days} DAYS)"))
        self.stdout.write("=" * 70)

        if metrics['total_verified'] == 0:
            self.stdout.write(self.style.WARNING(f"No verified forecasts found in the past {days} days."))
            self.stdout.write("=" * 70 + "\n")
            return

        header = f"{'Horizon':<10} | {'Samples':<9} | {'Realized MAE':<14} | {'Realized RMSE':<14} | {'Bias':<10}"
        self.stdout.write(header)
        self.stdout.write("-" * 70)

        for h_str, h_data in metrics['horizons'].items():
            self.stdout.write(
                f"+{h_data['horizon']}h{'':<7} | {h_data['samples']:<9} | {h_data['mae']:<14.2f} | {h_data['rmse']:<14.2f} | {h_data['bias']:<+10.2f}"
            )

        self.stdout.write("-" * 70)
        self.stdout.write(
            f"{'OVERALL':<10} | {metrics['total_verified']:<9} | {metrics['overall_mae']:<14.2f} | {metrics['overall_rmse']:<14.2f} | {metrics['overall_bias']:<+10.2f}"
        )
        self.stdout.write("=" * 70 + "\n")
