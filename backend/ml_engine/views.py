import os
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .services.predictor import AQIPredictor
from .models import ForecastRecord
from core.models import MonitoringStation

class ForecastAPIView(APIView):
    """
    Returns future AQI predictions for a specific Mumbai monitoring station.
    Reads from precomputed ForecastRecord if available, or computes on demand.
    Returns HTTP 503 if no model is trained yet.
    """
    def get(self, request):
        station_id = request.query_params.get('station_id', 'OPENAQ_6927')
        hours = request.query_params.get('hours', 24)

        try:
            hours_int = int(hours)
            hours_int = max(1, min(48, hours_int))
        except ValueError:
            hours_int = 24

        station = MonitoringStation.objects.filter(station_id=station_id).first()
        if not station:
            # Fallback to first available active station
            station = MonitoringStation.objects.filter(is_active=True).first()
            if not station:
                return Response({"error": "No monitoring stations registered."}, status=status.HTTP_404_NOT_FOUND)
            station_id = station.station_id

        # 1. Try reading from precomputed ForecastRecord for the latest batch
        latest_rec = ForecastRecord.objects.filter(station=station).order_by('-made_at').first()
        if latest_rec:
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
                return Response({
                    "station_id": station.station_id,
                    "station_name": station.name,
                    "forecast_generated_at": latest_rec.made_at.isoformat(),
                    "model_used": latest_rec.model_version,
                    "horizon_hours": len(forecast_items),
                    "forecasts": forecast_items
                }, status=status.HTTP_200_OK)

        # 2. Compute on demand
        try:
            forecast_data = AQIPredictor.forecast_station_aqi(station_id, horizon_hours=hours_int)
            return Response(forecast_data, status=status.HTTP_200_OK)
        except FileNotFoundError as e:
            return Response({
                "status": "not_trained",
                "message": "Model not trained. Please train the forecasting model first."
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Internal prediction error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ModelMetricsAPIView(APIView):
    """
    Returns model training evaluation metrics comparing Baseline, Ridge, Random Forest,
    and XGBoost. Used for viva explanation and model transparency dashboards.
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
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
