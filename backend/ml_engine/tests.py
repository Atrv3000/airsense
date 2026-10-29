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
from ml_engine.services.forecast_verifier import ForecastVerifier

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
        self.station2 = MonitoringStation.objects.create(
            station_id="OPENAQ_6959",
            name="Worli, Mumbai - IITM",
            latitude=19.01,
            longitude=72.81,
            zone_type="URBAN"
        )

        # Generate 580 continuous hourly records (290 hours x 2 stations) to test minimum training size and multi-station split
        base_time = datetime(2026, 8, 1, 0, 0, tzinfo=self.tz)
        raw_list = []
        for st in [self.station, self.station2]:
            for i in range(290):
                t = base_time + timedelta(hours=i)
                raw_list.append(RawMeasurement(
                    station=st,
                    recorded_at=t,
                    pm25=40.0 + (i % 10) * 4.0,
                    pm10=70.0 + (i % 10) * 6.0,
                    no2=22.0 + (i % 5),
                    so2=14.0,
                    co=0.7 + (i % 3) * 0.1,
                    o3=35.0 + (i % 8),
                    temperature=27.0 + (i % 6),
                    humidity=68.0 - (i % 5),
                    wind_speed=10.0 + (i % 4),
                    wind_direction=180.0,
                    source="OPENAQ_MEASURED"
                ))
        created_raws = RawMeasurement.objects.bulk_create(raw_list)

        aqi_list = []
        for raw in created_raws:
            aqi_val = raw.pm25 * 1.5
            aqi_list.append(AQIRecord(
                station=raw.station,
                raw_measurement=raw,
                recorded_at=raw.recorded_at,
                sub_index_pm25=aqi_val,
                sub_index_pm10=raw.pm10 * 0.9,
                sub_index_no2=raw.no2,
                sub_index_so2=raw.so2,
                sub_index_co=raw.co * 50,
                sub_index_o3=raw.o3,
                overall_aqi=aqi_val,
                prominent_pollutant="PM25",
                aqi_category="Satisfactory",
                color_hex="#92D050",
                valid_criteria_met=True
            ))
        AQIRecord.objects.bulk_create(aqi_list)

        # Train model with full multi-station dataset (580 rows >= 500 threshold)
        records = AQIRecord.objects.select_related('station', 'raw_measurement').order_by('recorded_at')
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
        self.metadata = ModelTrainer.train_and_compare_models(df, min_samples=500)
        self.multi_metadata = ModelTrainer.train_direct_multi_horizon_models(df, horizons=[1, 3, 6, 12, 24], min_samples=500)

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
        self.assertIn("beats_seasonal_naive", response.data)

    def test_temporal_split_no_test_earlier_than_train(self):
        records = AQIRecord.objects.select_related('station', 'raw_measurement').order_by('recorded_at')
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

        X_train, X_test, y_train, y_test, train_df, test_df = FeatureEngineer.temporal_train_test_split(
            df_feats, train_ratio=0.8, return_dfs=True
        )

        self.assertFalse(train_df.empty)
        self.assertFalse(test_df.empty)

        # 1. No test timestamp earlier than any train timestamp
        max_train_ts = train_df['recorded_at'].max()
        min_test_ts = test_df['recorded_at'].min()
        self.assertLessEqual(max_train_ts, min_test_ts)
        self.assertTrue(all(ts >= max_train_ts for ts in test_df['recorded_at']))

        # 2. Both stations appear in both train and test partitions
        train_stations = set(train_df['station_id'].unique())
        test_stations = set(test_df['station_id'].unique())
        self.assertEqual(train_stations, {self.station.station_id, self.station2.station_id})
        self.assertEqual(test_stations, {self.station.station_id, self.station2.station_id})

    def test_minimum_training_size_enforcement(self):
        small_df = pd.DataFrame({
            'station_id': ['OPENAQ_6927'] * 15,
            'latitude': [18.91] * 15,
            'longitude': [72.82] * 15,
            'recorded_at': [datetime(2026, 8, 1, h, 0, tzinfo=self.tz) for h in range(15)],
            'overall_aqi': [80.0] * 15,
            'pm25': [40.0] * 15,
            'pm10': [70.0] * 15,
            'no2': [20.0] * 15,
            'so2': [10.0] * 15,
            'co': [0.5] * 15,
            'o3': [30.0] * 15,
            'temperature': [28.0] * 15,
            'humidity': [65.0] * 15,
            'wind_speed': [10.0] * 15,
            'wind_direction': [180.0] * 15
        })
        with self.assertRaises(ValueError) as ctx:
            ModelTrainer.train_and_compare_models(small_df, min_samples=500)
        self.assertIn("Insufficient historical data", str(ctx.exception))
        self.assertIn("500", str(ctx.exception))

    def test_cross_validation_and_baselines_in_metadata(self):
        comparison = self.metadata["metrics_comparison"]
        self.assertIn("Baseline_Persistence", comparison)
        self.assertIn("Baseline_Seasonal_Naive", comparison)

        for model_name in ["Baseline_Persistence", "Baseline_Seasonal_Naive", "Ridge_Linear", "Random_Forest", "XGBoost"]:
            m = comparison[model_name]
            self.assertIn("cv_rmse_mean", m)
            self.assertIn("cv_rmse_std", m)
            self.assertIn("cv_mae_mean", m)
            self.assertIn("cv_mae_std", m)
            self.assertIn("cv_folds", m)

        self.assertIn("beats_seasonal_naive", self.metadata)
        self.assertIn("seasonal_naive_rmse", self.metadata)
        self.assertIn("cv_splits", self.metadata)
        self.assertGreaterEqual(self.metadata["cv_splits"], 2)

    def test_train_models_command_and_measured_only_option(self):
        from io import StringIO
        from django.core.management import call_command
        # 1. Run train_models default (all data)
        out = StringIO()
        call_command('train_models', stdout=out)
        out_str = out.getvalue()
        self.assertIn("ML BENCHMARK: ALL INGESTED DATA", out_str)
        self.assertIn("CHAMPION:", out_str)

        # 2. Run train_models with --measured-only
        out_meas = StringIO()
        call_command('train_models', measured_only=True, stdout=out_meas)
        out_meas_str = out_meas.getvalue()
        self.assertIn("ML BENCHMARK: GROUND MEASURED ONLY", out_meas_str)
        self.assertIn("Active Saved Model:", out_meas_str)
        self.assertIn("MEASURED-ONLY", out_meas_str)

        # 3. Check model_metadata.json contains dual_evaluation
        save_dir = getattr(settings, 'ML_MODELS_DIR', os.path.join(settings.BASE_DIR, 'ml_engine', 'saved_models'))
        meta_path = os.path.join(save_dir, 'model_metadata.json')
        self.assertTrue(os.path.exists(meta_path))
        with open(meta_path, 'r') as f:
            saved = json.load(f)
        self.assertIn('dual_evaluation', saved)
        self.assertTrue(saved['dual_evaluation']['measured_only_active'])
        self.assertGreaterEqual(saved['dual_evaluation']['measured_only_samples'], 500)

    def test_direct_multi_horizon_training_and_conformal_intervals(self):
        # 1. Horizons verified
        self.assertEqual(self.multi_metadata['horizons'], [1, 3, 6, 12, 24])
        self.assertEqual(self.multi_metadata['model_type'], 'Direct_Multi_Horizon')

        # 2. Per-horizon metrics structure
        per_h = self.multi_metadata['per_horizon_metrics']
        for h_key in ['1', '3', '6', '12', '24']:
            self.assertIn(h_key, per_h)
            h_stat = per_h[h_key]
            self.assertIn('MAE', h_stat)
            self.assertIn('RMSE', h_stat)
            self.assertIn('persistence_RMSE', h_stat)
            self.assertIn('seasonal_naive_RMSE', h_stat)
            self.assertIn('beats_persistence', h_stat)
            self.assertIn('beats_seasonal_naive', h_stat)
            self.assertIn('conformal_error_band', h_stat)

        # 3. Conformal intervals (empirical quantiles)
        conf_int = self.multi_metadata['conformal_intervals']
        for h_key in ['1', '3', '6', '12', '24']:
            self.assertIn(h_key, conf_int)
            self.assertIn('q80', conf_int[h_key])
            self.assertIn('q90', conf_int[h_key])
            self.assertGreaterEqual(conf_int[h_key]['q90'], 0)

        # 4. Direct models joblib bundle saved on disk
        save_dir = getattr(settings, 'ML_MODELS_DIR', os.path.join(settings.BASE_DIR, 'ml_engine', 'saved_models'))
        direct_path = os.path.join(save_dir, 'direct_models.joblib')
        self.assertTrue(os.path.exists(direct_path))
        loaded_bundle = joblib.load(direct_path)
        for h in [1, 3, 6, 12, 24]:
            self.assertIn(h, loaded_bundle)

    def test_metrics_endpoint_reports_per_horizon_baselines(self):
        # Test both /api/v1/ml/models/ and /api/v1/ml/metrics/
        for endpoint in ['/api/v1/ml/models/', '/api/v1/ml/metrics/']:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("per_horizon_metrics", response.data)
            self.assertIn("conformal_intervals", response.data)
            per_h = response.data["per_horizon_metrics"]
            for h in ['1', '3', '6', '12', '24']:
                self.assertIn(h, per_h)
                self.assertIn('persistence_RMSE', per_h[h])
                self.assertIn('seasonal_naive_RMSE', per_h[h])

    def test_direct_multi_horizon_predictor_smooth_continuous_forecast(self):
        forecast = AQIPredictor.forecast_station_aqi(self.station.station_id, horizon_hours=24)
        self.assertEqual(forecast["station_id"], self.station.station_id)
        self.assertEqual(forecast["horizon_hours"], 24)
        self.assertEqual(len(forecast["forecasts"]), 24)
        self.assertEqual(forecast["model_type"], "Direct_Multi_Horizon")

        # Verify all 24 steps have valid calibrated confidence bands and predicted AQI
        for i, fc in enumerate(forecast["forecasts"]):
            self.assertEqual(fc["step_ahead_hours"], i + 1)
            self.assertGreater(fc["predicted_aqi"], 0)
            self.assertGreater(fc["expected_error_band"], 0)
            self.assertLessEqual(fc["confidence_lower"], fc["predicted_aqi"])
            self.assertGreaterEqual(fc["confidence_upper"], fc["predicted_aqi"])

        # Precompute and verify ForecastRecord database persistence
        count = AQIPredictor.precompute_and_store_forecasts(horizon_hours=24)
        self.assertGreaterEqual(count, 24)
        db_records = ForecastRecord.objects.filter(station=self.station).order_by('horizon')
        self.assertEqual(db_records.count(), 24)


class ForecastVerificationTestCase(TestCase):
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

    def test_verification_past_forecast_matches_aqi_record(self):
        now = datetime.now(self.tz)
        t_target = now - timedelta(hours=3)
        t_made = now - timedelta(hours=6)

        # 1. Create actual ground truth measurement and AQIRecord
        raw = RawMeasurement.objects.create(
            station=self.station,
            recorded_at=t_target,
            pm25=55.0,
            pm10=100.0,
            source="OPENAQ_MEASURED"
        )
        aqi_rec = AQIRecord.objects.create(
            station=self.station,
            raw_measurement=raw,
            recorded_at=t_target,
            overall_aqi=140.0,
            prominent_pollutant="pm25",
            aqi_category="Moderate"
        )

        # 2. Create past forecast predicting 145.0 (+3h horizon)
        forecast_rec = ForecastRecord.objects.create(
            station=self.station,
            made_at=t_made,
            target_time=t_target,
            horizon=3,
            predicted_aqi=145.0,
            category="Moderate",
            expected_error_band=15.0
        )
        self.assertFalse(forecast_rec.is_verified)

        # 3. Run verification
        res = ForecastVerifier.verify_past_forecasts(station_id=self.station.station_id)
        self.assertEqual(res["verified_count"], 1)

        forecast_rec.refresh_from_db()
        self.assertTrue(forecast_rec.is_verified)
        self.assertEqual(forecast_rec.actual_aqi, 140.0)
        self.assertEqual(forecast_rec.absolute_error, 5.0)
        self.assertEqual(forecast_rec.signed_error, 5.0) # +5 overprediction
        self.assertIsNotNone(forecast_rec.verified_at)

    def test_future_forecast_remains_unverified(self):
        now = datetime.now(self.tz)
        future_target = now + timedelta(hours=4)
        future_fc = ForecastRecord.objects.create(
            station=self.station,
            made_at=now,
            target_time=future_target,
            horizon=4,
            predicted_aqi=110.0
        )

        res = ForecastVerifier.verify_past_forecasts(station_id=self.station.station_id)
        self.assertEqual(res["verified_count"], 0)

        future_fc.refresh_from_db()
        self.assertFalse(future_fc.is_verified)
        self.assertIsNone(future_fc.actual_aqi)

    def test_rolling_metrics_calculation(self):
        now = datetime.now(self.tz)
        # Create verified forecasts for horizon 1 (+1h)
        ForecastRecord.objects.create(
            station=self.station,
            made_at=now - timedelta(hours=5),
            target_time=now - timedelta(hours=4),
            horizon=1,
            predicted_aqi=110.0,
            actual_aqi=100.0,
            absolute_error=10.0,
            signed_error=10.0,
            is_verified=True,
            verified_at=now
        )
        ForecastRecord.objects.create(
            station=self.station,
            made_at=now - timedelta(hours=3),
            target_time=now - timedelta(hours=2),
            horizon=1,
            predicted_aqi=110.0,
            actual_aqi=120.0,
            absolute_error=10.0,
            signed_error=-10.0,
            is_verified=True,
            verified_at=now
        )

        # Create verified forecast for horizon 3 (+3h)
        ForecastRecord.objects.create(
            station=self.station,
            made_at=now - timedelta(hours=10),
            target_time=now - timedelta(hours=7),
            horizon=3,
            predicted_aqi=120.0,
            actual_aqi=100.0,
            absolute_error=20.0,
            signed_error=20.0,
            is_verified=True,
            verified_at=now
        )

        metrics = ForecastVerifier.get_rolling_metrics(days=7, station_id=self.station.station_id)
        self.assertEqual(metrics["total_verified"], 3)
        self.assertIn("1", metrics["horizons"])
        self.assertIn("3", metrics["horizons"])

        # Horizon 1: abs errors [10, 10] -> MAE 10.0, RMSE 10.0, Bias 0.0
        h1 = metrics["horizons"]["1"]
        self.assertEqual(h1["samples"], 2)
        self.assertEqual(h1["mae"], 10.0)
        self.assertEqual(h1["rmse"], 10.0)
        self.assertEqual(h1["bias"], 0.0)

        # Horizon 3: abs error [20] -> MAE 20.0, RMSE 20.0, Bias +20.0
        h3 = metrics["horizons"]["3"]
        self.assertEqual(h3["samples"], 1)
        self.assertEqual(h3["mae"], 20.0)
        self.assertEqual(h3["rmse"], 20.0)
        self.assertEqual(h3["bias"], 20.0)

    def test_verification_api_endpoint(self):
        # 1. Empty / no verified data
        res = self.client.get('/api/v1/ml/verification/?days=7')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total_verified"], 0)
        self.assertIn("window_days", res.data)

        # 2. With verified data
        now = datetime.now(self.tz)
        ForecastRecord.objects.create(
            station=self.station,
            made_at=now - timedelta(hours=2),
            target_time=now - timedelta(hours=1),
            horizon=1,
            predicted_aqi=95.0,
            actual_aqi=90.0,
            absolute_error=5.0,
            signed_error=5.0,
            is_verified=True,
            verified_at=now
        )
        res2 = self.client.get('/api/v1/ml/verification/?days=7')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data["total_verified"], 1)
        self.assertIn("1", res2.data["horizons"])
        self.assertEqual(res2.data["horizons"]["1"]["mae"], 5.0)

    def test_verify_forecasts_command(self):
        from io import StringIO
        from django.core.management import call_command

        now = datetime.now(self.tz)
        ForecastRecord.objects.create(
            station=self.station,
            made_at=now - timedelta(hours=2),
            target_time=now - timedelta(hours=1),
            horizon=1,
            predicted_aqi=95.0,
            actual_aqi=90.0,
            absolute_error=5.0,
            signed_error=5.0,
            is_verified=True,
            verified_at=now
        )

        out = StringIO()
        call_command('verify_forecasts', days=7, stdout=out)
        output = out.getvalue()
        self.assertIn("Verification scan complete:", output)
        self.assertIn("AIRSENSE MUMBAI - ROLLING FORECAST VERIFICATION", output)
        self.assertIn("Realized MAE", output)
        self.assertIn("+1h", output)
