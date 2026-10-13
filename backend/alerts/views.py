from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import AlertNotification, DeviceToken
from .serializers import AlertNotificationSerializer, DeviceTokenSerializer
from .services import AlertEngine

class ActiveAlertsListView(APIView):
    """
    GET /api/v1/alerts/
    Returns currently active alert notifications across Mumbai.
    Alert generation is scheduled via generate_alerts management command,
    not generated inline during read GET requests.
    Validates limit parameter safely.
    Optional query params:
      - severity (e.g., WARNING, CRITICAL)
      - station_id (e.g., OPENAQ_6927)
      - limit (default: 20)
    """
    def get(self, request):
        queryset = AlertNotification.objects.filter(is_active=True)

        severity = request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity__iexact=severity)

        station_id = request.query_params.get('station_id')
        if station_id:
            queryset = queryset.filter(station__station_id__iexact=station_id)

        limit_param = request.query_params.get('limit', 20)
        try:
            limit = int(limit_param)
            limit = max(1, min(100, limit))
        except (ValueError, TypeError):
            limit = 20

        queryset = queryset[:limit]

        serializer = AlertNotificationSerializer(queryset, many=True)
        return Response({
            'count': len(serializer.data),
            'alerts': serializer.data
        }, status=status.HTTP_200_OK)


class AdvisoryRecommendationView(APIView):
    """
    GET /api/v1/alerts/advisory/?category=Poor&pollutant=O3
    Returns dynamic health guidelines for given category and pollutant.
    """
    def get(self, request):
        category = request.query_params.get('category', 'Moderate')
        pollutant = request.query_params.get('pollutant')

        advisory = AlertEngine.get_station_advisory(category, pollutant)
        return Response(advisory, status=status.HTTP_200_OK)


class DeviceRegistrationView(APIView):
    """
    POST /api/v1/alerts/device-token/ -> Registers or refreshes mobile device push token.
    Does not expose public listings of subscriber contacts.
    """
    def post(self, request):
        token_str = request.data.get('token')
        if not token_str:
            return Response({"error": "Device token is required."}, status=status.HTTP_400_BAD_REQUEST)

        platform = request.data.get('platform', 'ANDROID')
        station_id = request.data.get('station_id')

        station = None
        if station_id:
            from core.models import MonitoringStation
            station = MonitoringStation.objects.filter(station_id=station_id).first()

        device, created = DeviceToken.objects.update_or_create(
            token=token_str,
            defaults={
                'platform': platform,
                'station': station,
                'is_active': True
            }
        )

        return Response({
            'message': 'Device token registered successfully.',
            'created': created
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
