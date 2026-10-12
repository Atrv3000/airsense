import pandas as pd
from django.core.management.base import BaseCommand
from aqi_engine.models import AQIRecord
from ml_engine.services.model_trainer import ModelTrainer

class Command(BaseCommand):
    help = "Extracts historical database records, trains Baseline, Ridge, RF and XGBoost models, and saves the champion model"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(">>> 1. Extracting historical records from PostgreSQL..."))
        records = AQIRecord.objects.select_related('station', 'raw_measurement').order_by('recorded_at')
        total_count = records.count()

        if total_count < 50:
            self.stdout.write(self.style.ERROR(
                f"Insufficient data in database ({total_count} records). Run 'python manage.py ingest_air_data' first."
            ))
            return

        self.stdout.write(self.style.SUCCESS(f"Extracted {total_count} records across Mumbai stations."))

        # Convert to pandas DataFrame
        data = []
        for r in records:
            data.append({
                'station_id': r.station.station_id,
                'recorded_at': r.recorded_at,
                'overall_aqi': r.overall_aqi,
                'pm25': r.raw_measurement.pm25,
                'pm10': r.raw_measurement.pm10,
                'no2': r.raw_measurement.no2,
                'so2': r.raw_measurement.so2,
                'co': r.raw_measurement.co,
                'o3': r.raw_measurement.o3,
                'temperature': r.raw_measurement.temperature,
                'humidity': r.raw_measurement.humidity,
                'wind_speed': r.raw_measurement.wind_speed,
                'wind_direction': r.raw_measurement.wind_direction,
            })

        df = pd.DataFrame(data)

        self.stdout.write(self.style.NOTICE(">>> 2. Running feature engineering & training benchmark suite..."))
        metadata = ModelTrainer.train_and_compare_models(df)

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("           MACHINE LEARNING MODEL BENCHMARK RESULTS"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"{'Model Name':<25} | {'MAE':<10} | {'RMSE':<10} | {'R2 Score':<10}")
        self.stdout.write("-" * 60)

        for model_name, metrics in metadata['metrics_comparison'].items():
            self.stdout.write(
                f"{model_name:<25} | {metrics['MAE']:<10} | {metrics['RMSE']:<10} | {metrics['R2_Score']:<10}"
            )

        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS(
            f"CHAMPION MODEL SELECTED: {metadata['champion_model']} (Saved to saved_models/)"
        ))
        self.stdout.write("=" * 60 + "\n")
