import os
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .services.predictor import AQIPredictor

class ForecastAPIView(APIView):
    """
    Returns future AQI predictions for a specific Mumbai monitoring station.
    Query parameters:
    - station_id: e.g. MUM_BKC (default: MUM_BKC)
    - hours: forecast horizon in hours (default: 24, max: 48)
    """
    def get(self, request):
        station_id = request.query_params.get('station_id', 'MUM_BKC')
        hours = request.query_params.get('hours', 24)

        try:
            hours_int = int(hours)
            hours_int = max(1, min(48, hours_int))  # Clamp between 1 and 48 hours
        except ValueError:
            hours_int = 24

        try:
            forecast_data = AQIPredictor.forecast_station_aqi(station_id, horizon_hours=hours_int)
            return Response(forecast_data, status=status.HTTP_200_OK)
        except (ValueError, FileNotFoundError) as e:
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
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            return Response(metadata, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
