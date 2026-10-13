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
    Loads the trained champion model and performs multi-step forecasting
    for future Mumbai AQI horizons using dynamic forecast weather from Open-Meteo
    and empirical validation residual uncertainty error bands.
    """
    _model = None
    _metadata = None

    @classmethod
    def get_model_and_metadata(cls):
        """
        Loads the serialized model and its metadata from disk (singleton pattern).
        Raises FileNotFoundError if no model has been trained.
        """
        save_dir = getattr(settings, 'ML_MODELS_DIR', os.path.join(settings.BASE_DIR, 'ml_engine', 'saved_models'))
        model_path = os.path.join(save_dir, 'champion_aqi_model.joblib')
        metadata_path = os.path.join(save_dir, 'model_metadata.json')

        if not os.path.exists(model_path) or not os.path.exists(metadata_path):
            raise FileNotFoundError("Model artifacts not found. Please train models first via manage.py train_models.")

        mtime = os.path.getmtime(model_path)
        if cls._model is None or getattr(cls, '_last_mtime', 0) != mtime:
            cls._model = joblib.load(model_path)
            with open(metadata_path, 'r') as f:
                cls._metadata = json.load(f)
            cls._last_mtime = mtime

        return cls._model, cls._metadata

    @classmethod
    def forecast_station_aqi(cls, station_id: str, horizon_hours: int = 24) -> Dict[str, Any]:
        """
        Generates hourly AQI forecasts for a station for the next N hours.
        Incorporates dynamic Open-Meteo future weather rather than freezing weather.
        """
        station = MonitoringStation.objects.filter(station_id=station_id).first()
        if not station:
            raise ValueError(f"Station '{station_id}' not found.")

        model, metadata = cls.get_model_and_metadata()
        residual_std = metadata.get("residual_std", metadata.get("champion_metrics", {}).get("RMSE", 15.0))

        # Retrieve historical sequence (at least 25 hours) for lag features
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
        last_timestamp = df_seq['recorded_at'].iloc[-1]

        # Fetch future forecasted weather from Open-Meteo (1 to 48 hours)
        future_weather_map = WeatherClient.fetch_forecast_weather_for_coords(
            latitude=station.latitude,
            longitude=station.longitude,
            forecast_days=max(1, (horizon_hours // 24) + 1)
        )

        forecasts = []

        for step in range(1, horizon_hours + 1):
            next_time = last_timestamp + timedelta(hours=step)
            next_time_iso = next_time.strftime("%Y-%m-%dT%H:00")

            # Extract forecasted weather for this future step
            step_weather = future_weather_map.get(next_time_iso, {})
            temp = step_weather.get("temperature", df_seq['temperature'].iloc[-1])
            humid = step_weather.get("humidity", df_seq['humidity'].iloc[-1])
            wspeed = step_weather.get("wind_speed", df_seq['wind_speed'].iloc[-1])
            wdir = step_weather.get("wind_direction", df_seq['wind_direction'].iloc[-1])

            # Build feature row without needing a future target
            df_feat = FeatureEngineer.create_features(df_seq, is_training=False)
            if df_feat.empty:
                pred_aqi = df_seq['overall_aqi'].iloc[-1]
            else:
                X_latest = df_feat[FeatureEngineer.FEATURE_COLUMNS].iloc[[-1]]
                pred_aqi = float(model.predict(X_latest)[0])
                pred_aqi = max(10.0, min(500.0, round(pred_aqi, 1)))

            # Empirical validation residual uncertainty band: expands with horizon step
            expected_error = round(residual_std * np.sqrt(step / 6.0), 1)
            lower_bound = max(0.0, round(pred_aqi - expected_error, 1))
            upper_bound = min(500.0, round(pred_aqi + expected_error, 1))

            cat_name, hex_color = CPCBCalculator.get_category_and_color(pred_aqi)

            forecasts.append({
                "step_ahead_hours": step,
                "target_timestamp": next_time.isoformat(),
                "predicted_aqi": pred_aqi,
                "expected_error_band": expected_error,
                "confidence_lower": lower_bound,
                "confidence_upper": upper_bound,
                "category": cat_name,
                "color_hex": hex_color
            })

            # Append forward step into sequence with actual forecast weather
            new_row = {
                'station_id': station.station_id,
                'latitude': station.latitude,
                'longitude': station.longitude,
                'recorded_at': next_time,
                'overall_aqi': pred_aqi,
                'pm25': df_seq['pm25'].iloc[-1],
                'pm10': df_seq['pm10'].iloc[-1],
                'no2': df_seq['no2'].iloc[-1],
                'so2': df_seq['so2'].iloc[-1],
                'co': df_seq['co'].iloc[-1],
                'o3': df_seq['o3'].iloc[-1],
                'temperature': temp,
                'humidity': humid,
                'wind_speed': wspeed,
                'wind_direction': wdir
            }
            df_seq = pd.concat([df_seq, pd.DataFrame([new_row])], ignore_index=True)

        return {
            "station_id": station.station_id,
            "station_name": station.name,
            "forecast_generated_at": last_timestamp.isoformat(),
            "model_used": metadata.get("champion_model", "Random_Forest"),
            "model_metrics": metadata.get("champion_metrics", {}),
            "residual_std": metadata.get("residual_std", residual_std),
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
                # Clear previous forecasts for this station to avoid duplicate horizon accumulation
                ForecastRecord.objects.filter(station=station).delete()

                result = cls.forecast_station_aqi(station.station_id, horizon_hours=horizon_hours)
                model_name = result.get("model_used", "ML_Model")

                for fc in result.get("forecasts", []):
                    target_time = pd.to_datetime(fc["target_timestamp"])
                    ForecastRecord.objects.create(
                        station=station,
                        made_at=now_dt,
                        horizon=fc["step_ahead_hours"],
                        target_time=target_time,
                        predicted_aqi=fc["predicted_aqi"],
                        category=fc["category"],
                        color_hex=fc["color_hex"],
                        expected_error_band=fc.get("expected_error_band", 15.0),
                        model_version=model_name
                    )
                    count += 1
            except Exception as e:
                logger.warning(f"Could not precompute forecast for {station.station_id}: {e}")

        return count
