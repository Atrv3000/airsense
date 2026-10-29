import os
import json
import logging
import joblib
import numpy as np
import pandas as pd
from datetime import timedelta
from typing import Dict, List, Any
from django.conf import settings
from django.utils import timezone
from core.models import MonitoringStation
from ingestion.models import CleanMeasurement, RawMeasurement
from aqi_engine.models import AQIRecord
from aqi_engine.services.cpcb_calculator import CPCBCalculator
from ingestion.services.weather_client import WeatherClient
from ml_engine.models import ForecastRecord
from .feature_engineering import FeatureEngineer

logger = logging.getLogger(__name__)

class AQIPredictor:
    """
    Loads trained direct multi-horizon models (+1h, +3h, +6h, +12h, +24h) and generates
    direct, non-recursive AQI forecasts using dynamic Open-Meteo future weather covariates
    and calibrated empirical residual quantiles (split-conformal intervals).
    """
    _direct_models = None
    _model = None
    _metadata = None
    _last_mtime = 0

    @classmethod
    def get_models_and_metadata(cls):
        """
        Loads the direct multi-horizon model bundle, champion single model, and metadata.
        """
        save_dir = getattr(settings, 'ML_MODELS_DIR', os.path.join(settings.BASE_DIR, 'ml_engine', 'saved_models'))
        direct_path = os.path.join(save_dir, 'direct_models.joblib')
        model_path = os.path.join(save_dir, 'champion_aqi_model.joblib')
        metadata_path = os.path.join(save_dir, 'model_metadata.json')

        if not os.path.exists(metadata_path) or (not os.path.exists(direct_path) and not os.path.exists(model_path)):
            raise FileNotFoundError("Model artifacts not found. Please train models first via manage.py train_models.")

        mtime = os.path.getmtime(metadata_path)
        if cls._metadata is None or cls._last_mtime != mtime:
            with open(metadata_path, 'r') as f:
                cls._metadata = json.load(f)
            if os.path.exists(direct_path):
                cls._direct_models = joblib.load(direct_path)
            else:
                cls._direct_models = None
            if os.path.exists(model_path):
                cls._model = joblib.load(model_path)
            cls._last_mtime = mtime

        return cls._direct_models, cls._model, cls._metadata

    @classmethod
    def get_model_and_metadata(cls):
        """
        Backward-compatible getter returning (model, metadata).
        """
        direct_models, single_model, metadata = cls.get_models_and_metadata()
        model = single_model or (direct_models.get(1) if direct_models else None)
        return model, metadata

    @classmethod
    def forecast_station_aqi(cls, station_id: str, horizon_hours: int = 24) -> Dict[str, Any]:
        """
        Generates hourly AQI forecasts for a station for the next N hours using direct models.
        Direct predictions on anchor horizons (+1h, +3h, +6h, +12h, +24h) with dynamic Open-Meteo
        forecast weather covariates, smoothly interpolated across intermediate hours without
        compounding recursive errors. Calibrated empirical quantiles define uncertainty bands.
        """
        station = MonitoringStation.objects.filter(station_id=station_id).first()
        if not station:
            raise ValueError(f"Station '{station_id}' not found.")

        direct_models, single_model, metadata = cls.get_models_and_metadata()

        # Retrieve historical sequence (at least 25 hours) for lag and rolling state at time t
        recent_records = AQIRecord.objects.filter(
            station=station
        ).select_related('station', 'raw_measurement').order_by('-recorded_at')[:36]

        if len(recent_records) < 10:
            raise ValueError(f"Station '{station_id}' has insufficient recent data ({len(recent_records)} records).")

        records_data = []
        for r in reversed(recent_records):
            records_data.append({
                'station_id': station.station_id,
                'latitude': station.latitude,
                'longitude': station.longitude,
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
                'wind_direction': r.raw_measurement.wind_direction if r.raw_measurement else None
            })

        df_seq = pd.DataFrame(records_data)
        df_seq = df_seq.sort_values('recorded_at').reset_index(drop=True)
        last_timestamp = df_seq['recorded_at'].iloc[-1]

        # Extract latest state at observation time t
        latest_aqi = df_seq['overall_aqi'].iloc[-1]
        latest_pm25 = df_seq['pm25'].ffill().bfill().iloc[-1]
        latest_pm10 = df_seq['pm10'].ffill().bfill().iloc[-1]
        latest_no2 = df_seq['no2'].ffill().bfill().iloc[-1]
        latest_so2 = df_seq['so2'].ffill().bfill().iloc[-1]
        latest_co = df_seq['co'].ffill().bfill().iloc[-1]
        latest_o3 = df_seq['o3'].ffill().bfill().iloc[-1]

        latest_temp = df_seq['temperature'].ffill().bfill().iloc[-1]
        latest_humid = df_seq['humidity'].ffill().bfill().iloc[-1]
        latest_wspeed = df_seq['wind_speed'].ffill().bfill().iloc[-1]
        latest_wdir = df_seq['wind_direction'].ffill().bfill().iloc[-1]

        wdir_rad = np.radians(latest_wdir)
        latest_u_wind = -latest_wspeed * np.sin(wdir_rad)
        latest_v_wind = -latest_wspeed * np.cos(wdir_rad)

        # Autoregressive lags at observation time t
        aqi_s = df_seq['overall_aqi'].dropna()
        aqi_lag_1 = float(aqi_s.iloc[-1])
        aqi_lag_2 = float(aqi_s.iloc[-2]) if len(aqi_s) >= 2 else aqi_lag_1
        aqi_lag_3 = float(aqi_s.iloc[-3]) if len(aqi_s) >= 3 else aqi_lag_2
        aqi_lag_24 = float(aqi_s.iloc[-24]) if len(aqi_s) >= 24 else aqi_lag_3

        aqi_roll_6h = float(aqi_s.iloc[-6:].mean()) if len(aqi_s) >= 1 else aqi_lag_1
        aqi_roll_24h = float(aqi_s.iloc[-24:].mean()) if len(aqi_s) >= 1 else aqi_lag_1

        # Fetch future forecasted weather from Open-Meteo (1 to 48 hours)
        future_weather_map = WeatherClient.fetch_forecast_weather_for_coords(
            latitude=station.latitude,
            longitude=station.longitude,
            forecast_days=max(1, (horizon_hours // 24) + 1)
        )

        anchor_horizons = [1, 3, 6, 12, 24]
        conformal_intervals = metadata.get("conformal_intervals", {})
        fallback_std = metadata.get("residual_std", 15.0)

        # 1. Generate Direct Model Predictions on Anchor Horizons
        anchor_predictions: Dict[int, Dict[str, Any]] = {}

        for h in anchor_horizons:
            target_time = last_timestamp + timedelta(hours=h)
            target_iso = target_time.strftime("%Y-%m-%dT%H:00")

            step_w = future_weather_map.get(target_iso, {})
            f_temp = step_w.get("temperature", latest_temp)
            f_humid = step_w.get("humidity", latest_humid)
            f_wspeed = step_w.get("wind_speed", latest_wspeed)
            f_wdir = step_w.get("wind_direction", latest_wdir)

            f_wdir_rad = np.radians(f_wdir)
            f_u_wind = -f_wspeed * np.sin(f_wdir_rad)
            f_v_wind = -f_wspeed * np.cos(f_wdir_rad)

            f_hour = target_time.hour
            f_hour_sin = np.sin(2 * np.pi * f_hour / 24.0)
            f_hour_cos = np.cos(2 * np.pi * f_hour / 24.0)
            f_dow = target_time.weekday()
            f_is_weekend = int(f_dow >= 5)

            # Direct feature vector for horizon h
            feat_row = {
                'latitude': station.latitude,
                'longitude': station.longitude,
                'pm25': latest_pm25,
                'pm10': latest_pm10,
                'no2': latest_no2,
                'so2': latest_so2,
                'co': latest_co,
                'o3': latest_o3,
                'temperature': latest_temp,
                'humidity': latest_humid,
                'wind_speed': latest_wspeed,
                'u_wind': latest_u_wind,
                'v_wind': latest_v_wind,
                'aqi_lag_1': aqi_lag_1,
                'aqi_lag_2': aqi_lag_2,
                'aqi_lag_3': aqi_lag_3,
                'aqi_lag_24': aqi_lag_24,
                'aqi_roll_mean_6h': aqi_roll_6h,
                'aqi_roll_mean_24h': aqi_roll_24h,
                'future_temp': f_temp,
                'future_humidity': f_humid,
                'future_wind_speed': f_wspeed,
                'future_u_wind': f_u_wind,
                'future_v_wind': f_v_wind,
                'future_hour_sin': f_hour_sin,
                'future_hour_cos': f_hour_cos,
                'future_day_of_week': f_dow,
                'future_is_weekend': f_is_weekend
            }

            X_h = pd.DataFrame([feat_row])[FeatureEngineer.MULTI_HORIZON_FEATURE_COLUMNS]

            # Choose model: specific direct model for h, or fallback
            if direct_models and h in direct_models:
                m_h = direct_models[h]
                pred_val = float(m_h.predict(X_h)[0])
            elif single_model:
                # Fallback to single model
                pred_val = float(single_model.predict(X_h[FeatureEngineer.FEATURE_COLUMNS[:len(X_h.columns)]])[0]) if len(FeatureEngineer.FEATURE_COLUMNS) <= len(X_h.columns) else latest_aqi
            else:
                pred_val = latest_aqi

            pred_val = max(10.0, min(500.0, round(pred_val, 1)))

            # Empirical residual quantile uncertainty band (calibrated split-conformal interval)
            h_conf = conformal_intervals.get(str(h), {})
            h_band = float(h_conf.get("q90", fallback_std))
            h_band = max(3.0, round(h_band, 1))

            anchor_predictions[h] = {
                "predicted_aqi": pred_val,
                "error_band": h_band,
                "target_time": target_time
            }

        # 2. Populate All Continuous Steps (1 to horizon_hours) via Smooth Interpolation
        forecasts = []
        anchor_steps = sorted(anchor_predictions.keys())

        for step in range(1, horizon_hours + 1):
            target_time = last_timestamp + timedelta(hours=step)

            if step in anchor_predictions:
                pred_aqi = anchor_predictions[step]["predicted_aqi"]
                error_band = anchor_predictions[step]["error_band"]
            else:
                # Find bounding anchors for intermediate hour interpolation
                prev_anchors = [a for a in anchor_steps if a < step]
                next_anchors = [a for a in anchor_steps if a > step]

                if prev_anchors and next_anchors:
                    h_a = max(prev_anchors)
                    h_b = min(next_anchors)
                    alpha = (step - h_a) / (h_b - h_a)
                    pred_aqi = (1 - alpha) * anchor_predictions[h_a]["predicted_aqi"] + alpha * anchor_predictions[h_b]["predicted_aqi"]
                    error_band = (1 - alpha) * anchor_predictions[h_a]["error_band"] + alpha * anchor_predictions[h_b]["error_band"]
                elif prev_anchors:
                    pred_aqi = anchor_predictions[max(prev_anchors)]["predicted_aqi"]
                    error_band = anchor_predictions[max(prev_anchors)]["error_band"]
                else:
                    pred_aqi = anchor_predictions[min(next_anchors)]["predicted_aqi"]
                    error_band = anchor_predictions[min(next_anchors)]["error_band"]

            pred_aqi = max(10.0, min(500.0, round(pred_aqi, 1)))
            error_band = round(error_band, 1)
            lower_bound = max(0.0, round(pred_aqi - error_band, 1))
            upper_bound = min(500.0, round(pred_aqi + error_band, 1))

            cat_name, hex_color = CPCBCalculator.get_category_and_color(pred_aqi)

            forecasts.append({
                "step_ahead_hours": step,
                "target_timestamp": target_time.isoformat(),
                "predicted_aqi": pred_aqi,
                "expected_error_band": error_band,
                "confidence_lower": lower_bound,
                "confidence_upper": upper_bound,
                "category": cat_name,
                "color_hex": hex_color
            })

        return {
            "station_id": station.station_id,
            "station_name": station.name,
            "forecast_generated_at": last_timestamp.isoformat(),
            "model_used": metadata.get("champion_model", "Random_Forest"),
            "model_type": metadata.get("model_type", "Direct_Multi_Horizon"),
            "model_metrics": metadata.get("champion_metrics", {}),
            "per_horizon_metrics": metadata.get("per_horizon_metrics", {}),
            "residual_std": metadata.get("residual_std", fallback_std),
            "horizon_hours": horizon_hours,
            "forecasts": forecasts
        }

    @classmethod
    def precompute_and_store_forecasts(cls, horizon_hours: int = 24) -> int:
        """
        Precomputes forecasts for all active stations and persists them into ForecastRecord.
        Allows GIS maps and APIs to read from the DB without running live model inference.
        """
        active_stations = MonitoringStation.objects.filter(is_active=True)
        count = 0
        now_dt = timezone.now()

        for station in active_stations:
            try:
                # Retain past forecasts for model verification, only pruning records older than 30 days
                ForecastRecord.objects.filter(station=station, made_at__lt=now_dt - timedelta(days=30)).delete()

                result = cls.forecast_station_aqi(station.station_id, horizon_hours=horizon_hours)
                model_name = result.get("model_used", "ML_Model")

                for fc in result.get("forecasts", []):
                    target_time = pd.to_datetime(fc["target_timestamp"])
                    ForecastRecord.objects.update_or_create(
                        station=station,
                        made_at=now_dt,
                        horizon=fc["step_ahead_hours"],
                        defaults={
                            "target_time": target_time,
                            "predicted_aqi": fc["predicted_aqi"],
                            "category": fc["category"],
                            "color_hex": fc["color_hex"],
                            "expected_error_band": fc.get("expected_error_band", 15.0),
                            "model_version": model_name
                        }
                    )
                    count += 1
            except Exception as e:
                logger.warning(f"Could not precompute forecast for {station.station_id}: {e}")

        return count
