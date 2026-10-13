import pandas as pd
from django.core.management.base import BaseCommand
from aqi_engine.models import AQIRecord
from ml_engine.services.model_trainer import ModelTrainer
from ml_engine.services.predictor import AQIPredictor

class Command(BaseCommand):
    help = "Extracts historical database records, trains Baseline, Ridge, RF and XGBoost models, saves champion model, and precomputes forecasts"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(">>> 1. Extracting historical records from database..."))
        records = AQIRecord.objects.select_related('station', 'raw_measurement').order_by('recorded_at')
        total_count = records.count()

        if total_count < 30:
            self.stdout.write(self.style.ERROR(
                f"Insufficient data in database ({total_count} records). Run 'python manage.py ingest_air_data' or backfill first."
            ))
            return

        self.stdout.write(self.style.SUCCESS(f"Extracted {total_count} records across Mumbai stations."))

        data = []
        for r in records:
            data.append({
                'station_id': r.station.station_id,
                'latitude': r.station.latitude,
                'longitude': r.station.longitude,
                'recorded_at': r.recorded_at,
                'overall_aqi': r.overall_aqi,
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

        df = pd.DataFrame(data)

        self.stdout.write(self.style.NOTICE(">>> 2. Running feature engineering & TimeSeriesSplit benchmark suite..."))
        metadata = ModelTrainer.train_and_compare_models(df)

        self.stdout.write("\n" + "=" * 65)
        self.stdout.write(self.style.SUCCESS("           MACHINE LEARNING MODEL BENCHMARK RESULTS"))
        self.stdout.write("=" * 65)
        self.stdout.write(f"{'Model Name':<25} | {'MAE':<10} | {'RMSE':<10} | {'R2 Score':<10}")
        self.stdout.write("-" * 65)

        for model_name, metrics in metadata['metrics_comparison'].items():
            self.stdout.write(
                f"{model_name:<25} | {metrics['MAE']:<10} | {metrics['RMSE']:<10} | {metrics['R2_Score']:<10}"
            )

        self.stdout.write("=" * 65)
        beats_p = metadata.get('beats_persistence', False)
        status_msg = "BEATS PERSISTENCE BASELINE" if beats_p else "DOES NOT BEAT PERSISTENCE BASELINE (Reported honestly)"
        self.stdout.write(self.style.SUCCESS(
            f"CHAMPION: {metadata['champion_model']} ({status_msg})\n"
            f"Champion RMSE: {metadata.get('champion_rmse')} vs Persistence RMSE: {metadata.get('persistence_rmse')}\n"
            f"Validation Residual Std Dev: {metadata.get('residual_std')}"
        ))
        self.stdout.write("=" * 65 + "\n")

        self.stdout.write(self.style.NOTICE(">>> 3. Precomputing multi-horizon forecasts into ForecastRecord..."))
        precomputed_count = AQIPredictor.precompute_and_store_forecasts(horizon_hours=24)
        self.stdout.write(self.style.SUCCESS(f"Precomputed and saved {precomputed_count} forecast entries into database.\n"))
