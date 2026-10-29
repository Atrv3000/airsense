import json
import os
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from aqi_engine.models import AQIRecord
from ml_engine.services.model_trainer import ModelTrainer
from ml_engine.services.predictor import AQIPredictor

class Command(BaseCommand):
    help = "Trains direct multi-horizon models (+1h, +3h, +6h, +12h, +24h), benchmarks against Persistence and Seasonal-Naive, saves champion models, and precomputes forecasts"

    def add_arguments(self, parser):
        parser.add_argument(
            '--measured-only',
            action='store_true',
            help='Train champion models exclusively on ground-truth measured data (OPENAQ_MEASURED, CPCB_OFFICIAL)'
        )

    def _print_metrics_table(self, title: str, metadata: dict):
        self.stdout.write("\n" + "=" * 92)
        self.stdout.write(self.style.SUCCESS(f"  {title.upper()}"))
        self.stdout.write("=" * 92)
        self.stdout.write(
            f"{'Model Name':<25} | {'Test MAE':<9} | {'Test RMSE':<9} | {'Test R2':<8} | {'CV RMSE (mean+-std)':<18} | {'CV MAE (mean+-std)':<16}"
        )
        self.stdout.write("-" * 92)

        for model_name, metrics in metadata['metrics_comparison'].items():
            cv_rmse_str = f"{metrics.get('cv_rmse_mean', 0.0):.2f} +- {metrics.get('cv_rmse_std', 0.0):.2f}"
            cv_mae_str = f"{metrics.get('cv_mae_mean', 0.0):.2f} +- {metrics.get('cv_mae_std', 0.0):.2f}"
            self.stdout.write(
                f"{model_name:<25} | {metrics['MAE']:<9} | {metrics['RMSE']:<9} | {metrics['R2_Score']:<8} | {cv_rmse_str:<18} | {cv_mae_str:<16}"
            )

        self.stdout.write("=" * 92)
        beats_p = metadata.get('beats_persistence', False)
        beats_sn = metadata.get('beats_seasonal_naive', False)
        p_status = "BEATS" if beats_p else "DOES NOT BEAT"
        sn_status = "BEATS" if beats_sn else "DOES NOT BEAT"

        self.stdout.write(self.style.SUCCESS(
            f"CHAMPION: {metadata['champion_model']}\n"
            f"  - Persistence Baseline:    {p_status} (Champion RMSE: {metadata.get('champion_rmse')} vs Persistence RMSE: {metadata.get('persistence_rmse')})\n"
            f"  - Seasonal-Naive Baseline: {sn_status} (Champion RMSE: {metadata.get('champion_rmse')} vs Seasonal-Naive RMSE: {metadata.get('seasonal_naive_rmse')})\n"
            f"  - Cross-Validation Splits: {metadata.get('cv_splits', 5)} folds (TimeSeriesSplit)\n"
            f"  - Validation Residual std: {metadata.get('residual_std')}"
        ))
        self.stdout.write("=" * 92 + "\n")

    def _print_multi_horizon_table(self, title: str, multi_metadata: dict):
        self.stdout.write("\n" + "=" * 115)
        self.stdout.write(self.style.SUCCESS(f"  {title.upper()}"))
        self.stdout.write("=" * 115)
        self.stdout.write(
            f"{'Horizon':<8} | {'Champion Model':<16} | {'Test MAE':<9} | {'Test RMSE':<10} | "
            f"{'Persist RMSE':<13} | {'Seas-Naive RMSE':<16} | {'Error Band (q90)':<17} | {'Baseline Status':<16}"
        )
        self.stdout.write("-" * 115)

        for h_str, h_meta in multi_metadata.get('per_horizon_metrics', {}).items():
            h_num = h_meta.get('horizon_hours', h_str)
            champ = h_meta.get('champion_model', 'N/A')
            mae = h_meta.get('MAE', 0.0)
            rmse = h_meta.get('RMSE', 0.0)
            p_rmse = h_meta.get('persistence_RMSE', 0.0)
            sn_rmse = h_meta.get('seasonal_naive_RMSE', 0.0)
            band = h_meta.get('conformal_error_band', 0.0)

            beats_p = h_meta.get('beats_persistence', False)
            beats_sn = h_meta.get('beats_seasonal_naive', False)
            if beats_p and beats_sn:
                status_str = "BEATS BOTH"
            elif beats_p:
                status_str = "BEATS PERSIST"
            elif beats_sn:
                status_str = "BEATS SEAS-NAIVE"
            else:
                status_str = "DOES NOT BEAT"

            self.stdout.write(
                f"+{h_num}h{'':<5} | {champ:<16} | {mae:<9.2f} | {rmse:<10.2f} | "
                f"{p_rmse:<13.2f} | {sn_rmse:<16.2f} | +- {band:<14.1f} | {status_str:<16}"
            )
        self.stdout.write("=" * 115 + "\n")

    def handle(self, *args, **options):
        measured_only = options.get('measured_only', False)

        self.stdout.write(self.style.NOTICE(">>> 1. Extracting historical records from database..."))
        records = AQIRecord.objects.select_related('station', 'raw_measurement').order_by('recorded_at')
        total_count = records.count()

        if total_count < 500:
            self.stdout.write(self.style.ERROR(
                f"Insufficient data in database ({total_count} records). Minimum required is 500 rows. Run 'python manage.py backfill_history' or ingestion first."
            ))
            return

        data = []
        for r in records:
            source = r.raw_measurement.source if r.raw_measurement else 'UNKNOWN'
            data.append({
                'station_id': r.station.station_id,
                'latitude': r.station.latitude,
                'longitude': r.station.longitude,
                'recorded_at': r.recorded_at,
                'overall_aqi': r.overall_aqi,
                'source': source,
                'pm25': r.raw_measurement.pm25 if r.raw_measurement else None,
                'pm10': r.raw_measurement.pm10 if r.raw_measurement else None,
                'no2': r.raw_measurement.no2 if r.raw_measurement else None,
                'so2': r.raw_measurement.so2 if r.raw_measurement else None,
                'co': r.raw_measurement.co if r.raw_measurement else None,
                'o3': r.raw_measurement.o3 if r.raw_measurement else None,
                'temperature': r.raw_measurement.temperature if r.raw_measurement else None,
                'humidity': r.raw_measurement.humidity if r.raw_measurement else None,
                'wind_speed': r.raw_measurement.wind_speed if r.raw_measurement else None,
                'wind_direction': r.raw_measurement.wind_direction if r.raw_measurement else None,
            })

        df_all = pd.DataFrame(data)
        df_measured = df_all[df_all['source'].isin(['OPENAQ_MEASURED', 'CPCB_OFFICIAL'])].copy()

        self.stdout.write(self.style.SUCCESS(
            f"Extracted {len(df_all)} total records across Mumbai stations.\n"
            f"  - Ground Measured Records: {len(df_measured)}\n"
            f"  - Modelled Fallback Records: {len(df_all) - len(df_measured)}"
        ))

        if measured_only and len(df_measured) < 500:
            self.stdout.write(self.style.ERROR(
                f"Insufficient ground measured data ({len(df_measured)} records). "
                f"Minimum required for --measured-only is 500 rows. "
                f"Run 'python manage.py backfill_history' to fetch more historical OpenAQ measurements."
            ))
            return

        self.stdout.write(self.style.NOTICE("\n>>> 2. Running direct multi-horizon training suite (+1h, +3h, +6h, +12h, +24h)..."))

        # 1. Train multi-horizon models on All Data
        all_save = (not measured_only)
        all_multi_meta = ModelTrainer.train_direct_multi_horizon_models(
            df_all,
            horizons=[1, 3, 6, 12, 24],
            min_samples=500,
            save_models=all_save,
            dataset_label="All Data (Modelled + Measured)"
        )
        self._print_multi_horizon_table("Direct Multi-Horizon Benchmark: All Ingested Data", all_multi_meta)
        self._print_metrics_table(f"ML Benchmark: All Ingested Data (N={len(df_all)})", all_multi_meta)

        # 2. Train multi-horizon models on Measured-Only Data if >= 500 samples
        measured_multi_meta = None
        if len(df_measured) >= 500:
            meas_save = measured_only
            measured_multi_meta = ModelTrainer.train_direct_multi_horizon_models(
                df_measured,
                horizons=[1, 3, 6, 12, 24],
                min_samples=500,
                save_models=meas_save,
                dataset_label="Measured-Only Data (OPENAQ_MEASURED, CPCB_OFFICIAL)"
            )
            self._print_multi_horizon_table("Direct Multi-Horizon Benchmark: Ground Measured Only", measured_multi_meta)
            self._print_metrics_table(f"ML Benchmark: Ground Measured Only (N={len(df_measured)})", measured_multi_meta)

            # Save dual comparison into model_metadata.json
            save_dir = getattr(settings, 'ML_MODELS_DIR', os.path.join(settings.BASE_DIR, 'ml_engine', 'saved_models'))
            meta_path = os.path.join(save_dir, 'model_metadata.json')
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as f:
                    saved_meta = json.load(f)
                saved_meta['dual_evaluation'] = {
                    'measured_only_active': measured_only,
                    'all_data_samples': len(df_all),
                    'measured_only_samples': len(df_measured),
                    'all_data_champion_rmse': all_multi_meta.get('champion_rmse'),
                    'measured_only_champion_rmse': measured_multi_meta.get('champion_rmse'),
                    'all_data_champion': all_multi_meta.get('champion_model'),
                    'measured_only_champion': measured_multi_meta.get('champion_model'),
                }
                with open(meta_path, 'w') as f:
                    json.dump(saved_meta, f, indent=4)
        else:
            self.stdout.write(self.style.WARNING(
                f"Note: Measured-only dataset has {len(df_measured)} samples (< 500 required for cross-validation). "
                f"Dual comparison requires running backfill_history with OpenAQ ground readings."
            ))

        active_meta = measured_multi_meta if (measured_only and measured_multi_meta) else all_multi_meta
        self.stdout.write(self.style.SUCCESS(
            f"Active Saved Model: {active_meta['champion_model']} "
            f"(Trained on: {'MEASURED-ONLY' if measured_only else 'ALL DATA'}, "
            f"Horizon +1h RMSE: {active_meta['champion_rmse']})\n"
        ))

        self.stdout.write(self.style.NOTICE(">>> 3. Precomputing multi-horizon forecasts into ForecastRecord..."))
        precomputed_count = AQIPredictor.precompute_and_store_forecasts(horizon_hours=24)
        self.stdout.write(self.style.SUCCESS(f"Precomputed and saved {precomputed_count} forecast entries into database.\n"))
