import os
import json
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.utils import timezone
from .services.predictor import AQIPredictor
from .models import ForecastRecord
from aqi_engine.models import AQIRecord
from core.models import MonitoringStation
from ingestion.services.telemetry import IngestionTelemetry

logger = logging.getLogger(__name__)

class ForecastAPIView(APIView):
    """
    Returns future AQI predictions for a specific Mumbai monitoring station.
    Reads from precomputed ForecastRecord if available, or computes on demand.
    Returns HTTP 404 if station is specified but nonexistent.
    """
    @staticmethod
    def _get_dynamic_model_metadata():
        save_dir = getattr(settings, 'ML_MODELS_DIR', os.path.join(settings.BASE_DIR, 'ml_engine', 'saved_models'))
        metadata_path = os.path.join(save_dir, 'model_metadata.json')
        if not os.path.exists(metadata_path):
            return {
                "champion_model": None,
                "model_version": None,
                "mae": None,
                "rmse": None,
                "r2": None,
                "validation_type": None,
                "horizons": None
            }
        try:
            with open(metadata_path, 'r') as f:
                raw = json.load(f)
            champ_metrics = raw.get("champion_metrics", {})
            return {
                "champion_model": raw.get("champion_model"),
                "model_version": raw.get("champion_model"),
                "mae": champ_metrics.get("MAE"),
                "rmse": champ_metrics.get("RMSE"),
                "r2": champ_metrics.get("R2_Score"),
                "validation_type": raw.get("validation_type", "TimeSeriesSplit (5-Fold)"),
                "horizons": raw.get("horizons", [1, 3, 6, 12, 24])
            }
        except Exception as e:
            logger.warning(f"Error reading model_metadata.json: {e}")
            return {
                "champion_model": None,
                "model_version": None,
                "mae": None,
                "rmse": None,
                "r2": None,
                "validation_type": None,
                "horizons": None
            }

    def get(self, request):
        station_id_param = request.query_params.get('station_id')
        hours = request.query_params.get('hours', 24)

        try:
            hours_int = int(hours)
            hours_int = max(1, min(48, hours_int))
        except ValueError:
            hours_int = 24

        if station_id_param:
            station = MonitoringStation.objects.filter(station_id=station_id_param).first()
            if not station:
                return Response({"error": f"Station '{station_id_param}' not found."}, status=status.HTTP_404_NOT_FOUND)
            station_id = station_id_param
        else:
            station = MonitoringStation.objects.filter(is_active=True).first()
            if not station:
                return Response({"error": "No monitoring stations registered."}, status=status.HTTP_404_NOT_FOUND)
            station_id = station.station_id

        meta_dict = self._get_dynamic_model_metadata()
        max_age_hours = getattr(settings, 'FORECAST_MAX_AGE_HOURS', 3)
        now_dt = timezone.now()

        # 1. Try reading from precomputed ForecastRecord for the latest batch
        latest_rec = ForecastRecord.objects.filter(station=station).order_by('-made_at').first()
        if latest_rec:
            age_hours = round((now_dt - latest_rec.made_at).total_seconds() / 3600.0, 1)
            is_stale = age_hours > max_age_hours

            cached_forecasts = ForecastRecord.objects.filter(
                station=station,
                made_at=latest_rec.made_at,
                horizon__lte=hours_int
            ).order_by('horizon')

            if cached_forecasts.count() >= min(hours_int, 24):
                forecast_items = []
                for cf in cached_forecasts[:hours_int]:
                    forecast_items.append({
                        "step_ahead_hours": cf.horizon,
                        "target_timestamp": cf.target_time.isoformat(),
                        "predicted_aqi": cf.predicted_aqi,
                        "expected_error_band": cf.expected_error_band,
                        "confidence_lower": max(0.0, round(cf.predicted_aqi - cf.expected_error_band, 1)),
                        "confidence_upper": min(500.0, round(cf.predicted_aqi + cf.expected_error_band, 1)),
                        "category": cf.category,
                        "color_hex": cf.color_hex
                    })

                # Fetch recent verified actuals vs predictions for evaluation/chart comparison
                verified_records = ForecastRecord.objects.filter(
                    station=station,
                    is_verified=True
                ).order_by('-target_time')[:12]
                comparison = []
                for vr in reversed(list(verified_records)):
                    comparison.append({
                        "target_time": vr.target_time.isoformat(),
                        "actual_aqi": vr.actual_aqi,
                        "predicted_aqi": vr.predicted_aqi,
                        "absolute_error": vr.absolute_error,
                        "horizon": vr.horizon
                    })

                return Response({
                    "station_id": station.station_id,
                    "station_name": station.name,
                    "forecast_generated_at": latest_rec.made_at.isoformat(),
                    "model_used": latest_rec.model_version,
                    "model_version": latest_rec.model_version,
                    "horizon_hours": len(forecast_items),
                    "is_stale": is_stale,
                    "input_data_age_hours": age_hours,
                    "forecasts": forecast_items,
                    "actual_vs_predicted": comparison,
                    "model_metadata": meta_dict
                }, status=status.HTTP_200_OK)

        # 2. Compute on demand
        try:
            forecast_data = AQIPredictor.forecast_station_aqi(station_id, horizon_hours=hours_int)
            forecast_data["model_metadata"] = meta_dict
            return Response(forecast_data, status=status.HTTP_200_OK)
        except FileNotFoundError as e:
            return Response({
                "status": "not_trained",
                "message": "Model not trained. Please train the forecasting model first."
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Internal prediction error for station {station_id}: {e}", exc_info=True)
            IngestionTelemetry.record_ml_error()
            return Response({"error": "An internal error occurred during prediction computation."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ModelMetricsAPIView(APIView):
    """
    Returns model training evaluation metrics comparing Baseline, Ridge, Random Forest,
    and XGBoost from genuine holdout cross-validation data.
    """
    def get(self, request):
        save_dir = getattr(settings, 'ML_MODELS_DIR', os.path.join(settings.BASE_DIR, 'ml_engine', 'saved_models'))
        metadata_path = os.path.join(save_dir, 'model_metadata.json')

        if not os.path.exists(metadata_path):
            return Response({
                "status": "not_trained",
                "message": "No trained model found. Please run 'python manage.py train_models'."
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            return Response(metadata, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error reading model metrics: {e}", exc_info=True)
            return Response({"error": "Unable to read model metrics."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ForecastVerificationAPIView(APIView):
    """
    Returns rolling forecast verification metrics (MAE, RMSE, bias) per horizon
    over the requested lookback window (default 7 days).
    Also accepts an optional 'verify=true' parameter to trigger on-demand evaluation.
    """
    def get(self, request):
        days_param = request.query_params.get('days', 7)
        station_id = request.query_params.get('station_id')
        trigger_verify = request.query_params.get('verify', 'false').lower() in ['true', '1', 'yes']

        try:
            days = int(days_param)
            days = max(1, min(90, days))
        except ValueError:
            days = 7

        from .services.forecast_verifier import ForecastVerifier

        if trigger_verify:
            ForecastVerifier.verify_past_forecasts(station_id=station_id)

        metrics = ForecastVerifier.get_rolling_metrics(days=days, station_id=station_id)
        return Response(metrics, status=status.HTTP_200_OK)
