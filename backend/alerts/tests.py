from django.test import TestCase
from core.models import MonitoringStation
from ingestion.models import RawMeasurement
from aqi_engine.models import AQIRecord
from alerts.models import AlertNotification, UserAlertSubscription
from alerts.services import AlertEngine
from django.utils import timezone

class AlertEngineTestCase(TestCase):
    def setUp(self):
        self.station = MonitoringStation.objects.create(
            station_id="MUM_TEST",
            name="Test Alert Station",
            latitude=19.0,
            longitude=72.8,
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
            prominent_pollutant='PM2.5',
            valid_criteria_met=True
        )

        alerts = AlertEngine.evaluate_and_generate_alerts(threshold_override=200.0)
        self.assertGreaterEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert.station, self.station)
        self.assertEqual(alert.severity, 'WARNING')
        self.assertEqual(alert.category, 'Poor')
        self.assertIn("N95", " ".join(alert.health_recommendations))

    def test_advisory_recommendations(self):
        adv = AlertEngine.get_station_advisory('Severe', 'PM2.5')
        self.assertEqual(adv['severity'], 'EMERGENCY')
        self.assertTrue(any("N95" in tip for tip in adv['recommendations']))
