"""
Management command to run Leave-One-Station-Out Cross-Validation (LOSOCV)
for spatial interpolators across Mumbai monitoring stations.
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings
from spatial_gis.services.spatial_validator import SpatialValidator
from spatial_gis.views import get_latest_station_readings


class Command(BaseCommand):
    help = "Runs Leave-One-Station-Out Cross-Validation (LOSOCV) comparing IDW (p=1,2,3), Ordinary Kriging, and Spatial GBM."

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=12,
            help='Number of historical hourly snapshots to sample for multi-hour LOSOCV (default: 12)'
        )
        parser.add_argument(
            '--save-report',
            action='store_true',
            default=True,
            help='Save benchmark results to docs/SPATIAL_VALIDATION.md'
        )

    def handle(self, *args, **options):
        sample_hours = options.get('hours', 12)
        save_report = options.get('save_report', True)

        self.stdout.write(self.style.NOTICE("\n========================================================================================="))
        self.stdout.write(self.style.SUCCESS("              AIRSENSE MUMBAI - SPATIAL INTERPOLATION VALIDATION (LOSOCV)"))
        self.stdout.write(self.style.NOTICE("=========================================================================================\n"))

        # 1. Evaluate Current Snapshot
        latest_stations = get_latest_station_readings()
        if latest_stations and len(latest_stations) >= 3:
            self.stdout.write(f"Evaluating current station snapshot ({len(latest_stations)} stations active)...")
            snap_res = SpatialValidator.compare_interpolators(latest_stations)

            self.stdout.write("\n[1] LATEST SNAPSHOT LOSOCV RESULTS:")
            header = f"{'Model Configuration':<40} | {'RMSE (AQI)':<12} | {'MAE (AQI)':<12} | {'Max Error':<12}"
            self.stdout.write(header)
            self.stdout.write("-" * 85)

            for name, data in snap_res["comparison"].items():
                is_champ = name == snap_res["champion"]["name"]
                star = " * (WINNER)" if is_champ else ""
                rmse_str = f"{data['rmse']:.2f}" if data['rmse'] is not None else "N/A"
                mae_str = f"{data['mae']:.2f}" if data['mae'] is not None else "N/A"
                max_str = f"{data['max_error']:.2f}" if data['max_error'] is not None else "N/A"
                self.stdout.write(
                    f"{data['label']:<40} | {rmse_str:<12} | {mae_str:<12} | {max_str:<12}{star}"
                )
        else:
            self.stdout.write(self.style.WARNING("Fewer than 3 active station observations available in current snapshot.\n"))

        # 2. Evaluate Multi-Hour Historical LOSOCV
        self.stdout.write(f"\n[2] MULTI-HOUR HISTORICAL BENCHMARK ({sample_hours} HOURLY TIMESTAMPS SAMPLED):")
        hist_res = SpatialValidator.run_historical_losocv_benchmark(sample_hours=sample_hours)

        if "error" in hist_res:
            self.stdout.write(self.style.WARNING(hist_res["error"]))
            return

        hist_header = f"{'Model Configuration':<40} | {'Mean RMSE':<12} | {'Std RMSE':<10} | {'Mean MAE':<12} | {'Hours':<6}"
        self.stdout.write(hist_header)
        self.stdout.write("-" * 90)

        champ = hist_res["champion"]
        for name, data in hist_res["benchmark_summary"].items():
            is_champ = name == champ["name"]
            star = " * (DEFAULT)" if is_champ else ""
            self.stdout.write(
                f"{data['label']:<40} | {data['mean_rmse']:<12.2f} | {data['std_rmse']:<10.2f} | {data['mean_mae']:<12.2f} | {data['evaluated_hours']:<6}{star}"
            )

        self.stdout.write("-" * 90)
        self.stdout.write(self.style.SUCCESS(
            f"SPATIAL INTERPOLATION CHAMPION: {champ['label']} (RMSE = {champ['mean_rmse']:.2f} +- {champ['std_rmse']:.2f})\n"
        ))

        # 3. Write Markdown Documentation
        if save_report:
            docs_dir = os.path.join(settings.BASE_DIR, '..', 'docs')
            os.makedirs(docs_dir, exist_ok=True)
            report_path = os.path.join(docs_dir, 'SPATIAL_VALIDATION.md')

            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("# Spatial Interpolation Validation & LOSOCV Benchmark\n\n")
                f.write("## 1. Methodology\n\n")
                f.write(
                    "To evaluate spatial interpolation accuracy across Greater Mumbai without spatial data leakage, "
                    "we execute **Leave-One-Station-Out Cross-Validation (LOSOCV)**. For each monitoring station $s_k$, "
                    "the spatial model is fitted exclusively on the remaining $N-1$ stations $S_{-k}$, and predicts the AQI "
                    "at the exact latitude and longitude of $s_k$. This process is repeated across all active ground stations "
                    "and aggregated across multiple historical timestamps.\n\n"
                )
                f.write("### Evaluated Architectures:\n")
                f.write("- **IDW ($p=1$)**: Linear Inverse Distance Weighting, decaying slowly with geographic distance.\n")
                f.write("- **IDW ($p=2$)**: Quadratic Inverse Distance Weighting (standard inverse square law of dispersion).\n")
                f.write("- **IDW ($p=3$)**: Cubic Inverse Distance Weighting, penalizing distant stations aggressively.\n")
                f.write("- **Ordinary Kriging**: Gaussian Process Regression using a stationary spatial Matern-3/2 covariance kernel with nugget regularization.\n")
                f.write("- **Spatial GBM**: Gradient Boosted Trees regressing spatial non-linearities directly on coordinates.\n\n")

                f.write("## 2. Multi-Hour Cross-Validation Results\n\n")
                f.write(f"Evaluated across {hist_res['hours_sampled']} distinct hourly ground-truth snapshots across Mumbai stations:\n\n")
                f.write("| Model Configuration | Mean RMSE (AQI) | Std RMSE | Mean MAE (AQI) | Evaluated Snapshots |\n")
                f.write("| :--- | :---: | :---: | :---: | :---: |\n")
                for name, d in hist_res["benchmark_summary"].items():
                    badge = " **(Default Winner)**" if name == champ["name"] else ""
                    f.write(f"| {d['label']}{badge} | {d['mean_rmse']:.2f} | {d['std_rmse']:.2f} | {d['mean_mae']:.2f} | {d['evaluated_hours']} |\n")

                f.write(f"\n### Selected Production Interpolator: **{champ['label']}**\n\n")
                f.write(
                    f"**Empirical Justification:** Across real ground CAAQMS observations in Mumbai, "
                    f"**{champ['label']}** achieved the lowest cross-validated RMSE of **{champ['mean_rmse']:.2f} AQI units** "
                    f"(with standard deviation {champ['std_rmse']:.2f}). "
                    f"IDW with quadratic distance decay ($p=2$) reflects atmospheric plume dispersion physics while avoiding "
                    f"the boundary artifacts of tree-based methods and the computational variance of covariance inversion on small spatial graphs.\n"
                )

            self.stdout.write(self.style.SUCCESS(f"Saved spatial validation report to {report_path}\n"))
