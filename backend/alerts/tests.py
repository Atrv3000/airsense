from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from core.models import MonitoringStation
from ingestion.models import RawMeasurement
from aqi_engine.models import AQIRecord
from ml_engine.models import ForecastRecord
from alerts.models import AlertNotification, DeviceToken
from alerts.services import AlertEngine

class AlertEngineTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.station = MonitoringStation.objects.create(
            station_id="OPENAQ_6927",
            name="Colaba, Mumbai - MPCB",
            latitude=18.91,
            longitude=72.82,
            is_active=True
        )

    def test_alert_generation_for_poor_aqi(self):
        now = timezone.now()
        raw = RawMeasurement.objects.create(
            station=self.station,
            recorded_at=now,
            pm25=120.0,
            pm10=220.0
        )
        AQIRecord.objects.create(
            station=self.station,
            raw_measurement=raw,
            recorded_at=now,
            overall_aqi=245.0,
            aqi_category='Poor',
            prominent_pollutant='PM25',
            valid_criteria_met=True
        )

        alerts = AlertEngine.evaluate_and_generate_alerts(threshold_override=201.0)
        self.assertGreaterEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert.station, self.station)
        self.assertEqual(alert.severity, 'WARNING')
        self.assertEqual(alert.category, 'Poor')
        self.assertIn("N95", " ".join(alert.health_recommendations))

    def test_alert_safe_when_overall_aqi_none(self):
        now = timezone.now()
        raw = RawMeasurement.objects.create(
            station=self.station,
            recorded_at=now,
            pm25=None,
            pm10=None
        )
        AQIRecord.objects.create(
            station=self.station,
            raw_measurement=raw,
            recorded_at=now,
            overall_aqi=None,
            aqi_category='Insufficient Data',
            valid_criteria_met=False
        )
        # Should not crash
        alerts = AlertEngine.evaluate_and_generate_alerts()
        self.assertEqual(len(alerts), 0)

    def test_auto_resolve_alerts_when_aqi_drops(self):
        # Create active alert
        alert = AlertNotification.objects.create(
            station=self.station,
            title="Warning Alert",
            message="Elevated pollution",
            severity="WARNING",
            aqi_value=250.0,
            category="Poor",
            is_active=True
        )

        # Now station AQI drops to Good (45.0)
        now = timezone.now()
        raw = RawMeasurement.objects.create(
            station=self.station,
            recorded_at=now,
            pm25=12.0,
            pm10=25.0
        )
        AQIRecord.objects.create(
            station=self.station,
            raw_measurement=raw,
            recorded_at=now,
            overall_aqi=45.0,
            aqi_category='Good',
            valid_criteria_met=True
        )

        AlertEngine.evaluate_and_generate_alerts(threshold_override=201.0)
        alert.refresh_from_db()
        self.assertFalse(alert.is_active)
        self.assertIsNotNone(alert.resolved_at)

    def test_forecast_based_alert_generation(self):
        now = timezone.now()
        # Add high forecast breach for +6h
        ForecastRecord.objects.create(
            station=self.station,
            made_at=now,
            target_time=now + timezone.timedelta(hours=6),
            horizon=6,
            predicted_aqi=310.0,
            category="Very Poor",
            expected_error_band=18.0
        )

        alerts = AlertEngine.evaluate_and_generate_alerts(threshold_override=201.0)
        f_alerts = [a for a in alerts if a.is_forecast_alert]
        self.assertGreaterEqual(len(f_alerts), 1)
        self.assertEqual(f_alerts[0].forecast_horizon_hours, 6)
        self.assertEqual(f_alerts[0].severity, "CRITICAL")

    def test_api_active_alerts_list_and_limit_validation(self):
        AlertNotification.objects.create(
            station=self.station,
            title="Active Alert 1",
            message="Alert msg",
            severity="WARNING",
            aqi_value=220.0,
            category="Poor",
            is_active=True
        )
        # Test limit query param with invalid string -> safely handles
        response = self.client.get('/api/v1/alerts/?limit=invalid')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data.get('count', 0), 1)

    def test_device_token_registration_api(self):
        payload = {
            "token": "ExponentPushToken[test-token-12345]",
            "platform": "ANDROID",
            "station_id": self.station.station_id
        }
        response = self.client.post('/api/v1/alerts/device-token/', data=payload, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertTrue(DeviceToken.objects.filter(token="ExponentPushToken[test-token-12345]").exists())
