import os
import json
import joblib
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.conf import settings
from core.models import MonitoringStation
from ingestion.models import RawMeasurement
from aqi_engine.models import AQIRecord
from aqi_engine.services.aqi_service import AQIService
from ml_engine.models import ForecastRecord
from ml_engine.services.feature_engineering import FeatureEngineer
from ml_engine.services.model_trainer import ModelTrainer
from ml_engine.services.predictor import AQIPredictor

class MachineLearningPipelineTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tz = ZoneInfo("Asia/Kolkata")
        self.station = MonitoringStation.objects.create(
            station_id="OPENAQ_6927",
            name="Colaba, Mumbai - MPCB",
            latitude=18.91,
            longitude=72.82,
            zone_type="COASTAL"
        )

        # Generate 45 continuous hourly records to support lag feature testing
        base_time = datetime(2026, 10, 1, 0, 0, tzinfo=self.tz)
        for i in range(45):
            t = base_time + timedelta(hours=i)
            raw = RawMeasurement.objects.create(
                station=self.station,
                recorded_at=t,
                pm25=40.0 + (i % 10) * 5,
                pm10=80.0 + (i % 10) * 8,
                no2=25.0,
                so2=15.0,
                co=0.8,
                o3=40.0,
                temperature=28.0 + (i % 5),
                humidity=70.0 - (i % 5),
                wind_speed=12.0,
                wind_direction=180.0,
                source="OPENAQ_MEASURED"
            )
            AQIService.calculate_for_measurement(raw)

        # Train a model in setUp so tests are self-contained
        records = AQIRecord.objects.filter(station=self.station).select_related('station', 'raw_measurement').order_by('recorded_at')
        data = []
        for r in records:
            data.append({
                'station_id': r.station.station_id,
                'latitude': r.station.latitude,
                'longitude': r.station.longitude,
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
        self.metadata = ModelTrainer.train_and_compare_models(df)

    def test_feature_engineering_pipeline(self):
        records = AQIRecord.objects.filter(station=self.station).select_related('station', 'raw_measurement').order_by('recorded_at')
        data = []
        for r in records:
            data.append({
                'station_id': r.station.station_id,
                'latitude': r.station.latitude,
                'longitude': r.station.longitude,
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
        df_feats = FeatureEngineer.create_features(df, is_training=True)
        self.assertFalse(df_feats.empty)

        # Check required columns
        for col in FeatureEngineer.FEATURE_COLUMNS:
            self.assertIn(col, df_feats.columns)
        self.assertIn(FeatureEngineer.TARGET_COLUMN, df_feats.columns)

        # Check inference features build without requiring target
        df_inference = FeatureEngineer.create_features(df, is_training=False)
        self.assertFalse(df_inference.empty)
        self.assertEqual(len(df_inference), len(df))

    def test_predictor_forecast_logic(self):
        forecast = AQIPredictor.forecast_station_aqi(self.station.station_id, horizon_hours=12)
        self.assertEqual(forecast["station_id"], self.station.station_id)
        self.assertEqual(forecast["horizon_hours"], 12)
        self.assertEqual(len(forecast["forecasts"]), 12)

        first_step = forecast["forecasts"][0]
        self.assertEqual(first_step["step_ahead_hours"], 1)
        self.assertIn("predicted_aqi", first_step)
        self.assertIn("expected_error_band", first_step)
        self.assertIn("category", first_step)
        self.assertIn("color_hex", first_step)

    def test_forecast_precomputation_and_api(self):
        count = AQIPredictor.precompute_and_store_forecasts(horizon_hours=6)
        self.assertGreater(count, 0)
        self.assertTrue(ForecastRecord.objects.filter(station=self.station).exists())

        response = self.client.get(f'/api/v1/ml/predict/?station_id={self.station.station_id}&hours=6')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("forecasts", [])), 6)

    def test_api_models_endpoint(self):
        response = self.client.get('/api/v1/ml/models/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("champion_model", response.data)
        self.assertIn("metrics_comparison", response.data)
        self.assertIn("beats_persistence", response.data)
