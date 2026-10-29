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

    def test_alert_suppressed_when_valid_criteria_not_met(self):
        now = timezone.now()
        raw = RawMeasurement.objects.create(
            station=self.station,
            recorded_at=now,
            pm25=180.0
        )
        # Record with severe AQI but failing valid_criteria_met (e.g. only 1 pollutant)
        AQIRecord.objects.create(
            station=self.station,
            raw_measurement=raw,
            recorded_at=now,
            overall_aqi=320.0,
            aqi_category='Very Poor',
            prominent_pollutant='PM25',
            valid_criteria_met=False
        )

        alerts = AlertEngine.evaluate_and_generate_alerts(threshold_override=201.0)
        # Must not generate alert because valid_criteria_met is False
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

        # Test devices/ alias endpoint
        response_alias = self.client.post('/api/v1/alerts/devices/', data={"token": "ExponentPushToken[alias-1]"}, format='json')
        self.assertIn(response_alias.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertTrue(DeviceToken.objects.filter(token="ExponentPushToken[alias-1]").exists())


from unittest.mock import patch, MagicMock
from alerts.services_push import ExpoPushClient

class ExpoPushClientTestCase(TestCase):
    def setUp(self):
        self.station1 = MonitoringStation.objects.create(
            station_id="OPENAQ_BKC",
            name="BKC, Mumbai",
            latitude=19.06,
            longitude=72.86
        )
        self.station2 = MonitoringStation.objects.create(
            station_id="OPENAQ_WORLI",
            name="Worli, Mumbai",
            latitude=19.01,
            longitude=72.81
        )
        self.alert = AlertNotification.objects.create(
            station=self.station1,
            title="WARNING AQI Alert: BKC",
            message="AQI has reached 250.0 (Poor).",
            severity="WARNING",
            aqi_value=250.0,
            category="Poor",
            is_active=True
        )

    @patch('requests.post')
    def test_expo_push_batch_chunking_and_send(self, mock_post):
        # Create 105 active device tokens (exceeding MAX_BATCH_SIZE=100)
        tokens = [
            DeviceToken(token=f"ExponentPushToken[batch-token-{i:04d}]", is_active=True)
            for i in range(105)
        ]
        DeviceToken.objects.bulk_create(tokens)

        # Mock successful responses
        mock_resp_100 = MagicMock()
        mock_resp_100.status_code = 200
        mock_resp_100.json.return_value = {"data": [{"status": "ok"} for _ in range(100)]}

        mock_resp_5 = MagicMock()
        mock_resp_5.status_code = 200
        mock_resp_5.json.return_value = {"data": [{"status": "ok"} for _ in range(5)]}

        mock_post.side_effect = [mock_resp_100, mock_resp_5]

        res = ExpoPushClient.send_alert_push_notifications([self.alert])
        self.assertEqual(res['sent'], 105)
        self.assertEqual(res['failed'], 0)
        self.assertEqual(res['deactivated'], 0)
        self.assertEqual(mock_post.call_count, 2)

    @patch('requests.post')
    def test_expo_push_deactivates_unregistered_token(self, mock_post):
        dt = DeviceToken.objects.create(
            token="ExponentPushToken[invalid-stale-token]",
            is_active=True
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{
                "status": "error",
                "message": '"ExponentPushToken[invalid-stale-token]" is not a registered push notification recipient',
                "details": {"error": "DeviceNotRegistered"}
            }]
        }
        mock_post.return_value = mock_resp

        res = ExpoPushClient.send_alert_push_notifications([self.alert], device_tokens=[dt])
        self.assertEqual(res['sent'], 0)
        self.assertEqual(res['failed'], 1)
        self.assertEqual(res['deactivated'], 1)

        dt.refresh_from_db()
        self.assertFalse(dt.is_active)

    @patch('requests.post')
    def test_expo_push_station_preference_filtering(self, mock_post):
        # dt_match subscribes to station1
        dt_match = DeviceToken.objects.create(
            token="ExponentPushToken[match-token]",
            station=self.station1,
            is_active=True
        )
        # dt_diff subscribes to station2
        dt_diff = DeviceToken.objects.create(
            token="ExponentPushToken[other-station-token]",
            station=self.station2,
            is_active=True
        )
        # dt_city subscribes to all stations (station=None)
        dt_city = DeviceToken.objects.create(
            token="ExponentPushToken[city-token]",
            station=None,
            is_active=True
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"status": "ok"}, {"status": "ok"}]}
        mock_post.return_value = mock_resp

        res = ExpoPushClient.send_alert_push_notifications([self.alert])
        self.assertEqual(res['messages_created'], 2)
        # Verify dt_diff was NOT included
        call_payload = mock_post.call_args[1]['json']
        tokens_in_payload = [m['to'] for m in call_payload]
        self.assertIn("ExponentPushToken[match-token]", tokens_in_payload)
        self.assertIn("ExponentPushToken[city-token]", tokens_in_payload)
        self.assertNotIn("ExponentPushToken[other-station-token]", tokens_in_payload)

    @patch('requests.post')
    def test_expo_push_network_error_resilience(self, mock_post):
        import requests
        DeviceToken.objects.create(token="ExponentPushToken[net-test]", is_active=True)
        mock_post.side_effect = requests.exceptions.ConnectionError("Network unavailable")

        res = ExpoPushClient.send_alert_push_notifications([self.alert])
        self.assertEqual(res['sent'], 0)
        self.assertEqual(res['failed'], 1)

