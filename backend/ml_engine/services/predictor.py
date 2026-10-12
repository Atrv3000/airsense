import os
import json
import logging
import joblib
import numpy as np
import pandas as pd
from datetime import timedelta
from typing import Dict, List, Any
from django.conf import settings
from core.models import MonitoringStation
from aqi_engine.models import AQIRecord
from aqi_engine.services.cpcb_calculator import CPCBCalculator
from .feature_engineering import FeatureEngineer

logger = logging.getLogger(__name__)

class AQIPredictor:
    """
    Loads the trained champion model and performs recursive multi-step forecasting
    for future Mumbai AQI horizons (1 to 48 hours).
    """
    _model = None
    _metadata = None

    @classmethod
    def get_model_and_metadata(cls):
        """
        Loads the serialized model and its metadata from disk (singleton pattern).
        """
        if cls._model is None or cls._metadata is None:
            save_dir = getattr(settings, 'ML_MODELS_DIR', os.path.join(settings.BASE_DIR, 'ml_engine', 'saved_models'))
            model_path = os.path.join(save_dir, 'champion_aqi_model.joblib')
            metadata_path = os.path.join(save_dir, 'model_metadata.json')

            if not os.path.exists(model_path) or not os.path.exists(metadata_path):
                raise FileNotFoundError("Model artifacts not found. Please run model training first.")

            cls._model = joblib.load(model_path)
            with open(metadata_path, 'r') as f:
                cls._metadata = json.load(f)

        return cls._model, cls._metadata

    @classmethod
    def forecast_station_aqi(cls, station_id: str, horizon_hours: int = 24) -> Dict[str, Any]:
        """
        Generates hourly AQI forecasts for a station for the next N hours.
        """
        station = MonitoringStation.objects.filter(station_id=station_id).first()
        if not station:
            raise ValueError(f"Station '{station_id}' not found.")

        model, metadata = cls.get_model_and_metadata()
        rmse = metadata.get("champion_metrics", {}).get("RMSE", 15.0)

        # Retrieve recent historical sequence (at least 30 hours) to build lag features
        recent_records = AQIRecord.objects.filter(
            station=station
        ).select_related('station', 'raw_measurement').order_by('-recorded_at')[:36]

        if len(recent_records) < 25:
            raise ValueError(f"Station '{station_id}' has insufficient recent data ({len(recent_records)} records).")

        # Convert to chronological DataFrame
        records_data = []
        for r in reversed(recent_records):
            records_data.append({
                'recorded_at': r.recorded_at,
                'overall_aqi': r.overall_aqi or 100.0,
                'pm25': r.raw_measurement.pm25,
                'pm10': r.raw_measurement.pm10,
                'no2': r.raw_measurement.no2,
                'so2': r.raw_measurement.so2,
                'co': r.raw_measurement.co,
                'o3': r.raw_measurement.o3,
                'temperature': r.raw_measurement.temperature,
                'humidity': r.raw_measurement.humidity,
                'wind_speed': r.raw_measurement.wind_speed,
                'wind_direction': r.raw_measurement.wind_direction
            })

        df_seq = pd.DataFrame(records_data)
        last_timestamp = df_seq['recorded_at'].iloc[-1]
        forecasts = []

        # Autoregressive multi-step prediction loop
        for step in range(1, horizon_hours + 1):
            next_time = last_timestamp + timedelta(hours=step)

            # Build feature row for the next step
            df_feat = FeatureEngineer.create_features(df_seq)
            if df_feat.empty:
                # Fallback to persistence if feature vector is short
                pred_aqi = df_seq['overall_aqi'].iloc[-1]
            else:
                X_latest = df_feat[FeatureEngineer.FEATURE_COLUMNS].iloc[[-1]]
                pred_aqi = float(model.predict(X_latest)[0])
                pred_aqi = max(10.0, min(500.0, round(pred_aqi, 1)))

            # Uncertainty expands with horizon length
            uncertainty_band = round(1.2 * rmse * np.sqrt(step / 6.0), 1)
            lower_bound = max(0.0, round(pred_aqi - uncertainty_band, 1))
            upper_bound = min(500.0, round(pred_aqi + uncertainty_band, 1))

            cat_name, hex_color = CPCBCalculator.get_category_and_color(pred_aqi)

            forecasts.append({
                "step_ahead_hours": step,
                "target_timestamp": next_time.isoformat(),
                "predicted_aqi": pred_aqi,
                "confidence_lower": lower_bound,
                "confidence_upper": upper_bound,
                "category": cat_name,
                "color_hex": hex_color
            })

            # Append predicted value into sequence to feed future autoregressive lags
            new_row = {
                'recorded_at': next_time,
                'overall_aqi': pred_aqi,
                'pm25': df_seq['pm25'].iloc[-1],
                'pm10': df_seq['pm10'].iloc[-1],
                'no2': df_seq['no2'].iloc[-1],
                'so2': df_seq['so2'].iloc[-1],
                'co': df_seq['co'].iloc[-1],
                'o3': df_seq['o3'].iloc[-1],
                'temperature': df_seq['temperature'].iloc[-1],
                'humidity': df_seq['humidity'].iloc[-1],
                'wind_speed': df_seq['wind_speed'].iloc[-1],
                'wind_direction': df_seq['wind_direction'].iloc[-1]
            }
            df_seq = pd.concat([df_seq, pd.DataFrame([new_row])], ignore_index=True)

        return {
            "station_id": station.station_id,
            "station_name": station.name,
            "forecast_generated_at": last_timestamp.isoformat(),
            "model_used": metadata.get("champion_model", "XGBoost"),
            "model_metrics": metadata.get("champion_metrics", {}),
            "horizon_hours": horizon_hours,
            "forecasts": forecasts
        }
