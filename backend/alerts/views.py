from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import AlertNotification, UserAlertSubscription
from .serializers import AlertNotificationSerializer, UserAlertSubscriptionSerializer
from .services import AlertEngine

class ActiveAlertsListView(APIView):
    """
    GET /api/v1/alerts/
    Returns currently active alert notifications across Mumbai.
    Optional query params:
      - severity (e.g., WARNING, CRITICAL)
      - station_id (e.g., MUM_BKC)
      - limit (default: 20)
    """
    def get(self, request):
        # Auto-evaluate latest records to generate any new threshold breaches
        AlertEngine.evaluate_and_generate_alerts()

        queryset = AlertNotification.objects.filter(is_active=True)

        severity = request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity__iexact=severity)

        station_id = request.query_params.get('station_id')
        if station_id:
            queryset = queryset.filter(station__station_id__iexact=station_id)

        limit = int(request.query_params.get('limit', 20))
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


class UserSubscriptionView(APIView):
    """
    GET  /api/v1/alerts/subscribe/ -> List active subscriptions
    POST /api/v1/alerts/subscribe/ -> Register alert preferences
    """
    def get(self, request):
        subs = UserAlertSubscription.objects.filter(is_active=True)[:50]
        serializer = UserAlertSubscriptionSerializer(subs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = UserAlertSubscriptionSerializer(data=request.data)
        if serializer.is_valid():
            sub = serializer.save()
            return Response({
                'message': 'Alert subscription registered successfully.',
                'subscription': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
