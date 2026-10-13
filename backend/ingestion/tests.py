from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from core.models import MonitoringStation
from ingestion.models import RawMeasurement, CleanMeasurement
from ingestion.services.preprocessor import DataPreprocessor
from ingestion.services.station_seeder import seed_mumbai_stations

class IngestionPipelineTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.station = MonitoringStation.objects.create(
            station_id="OPENAQ_6927",
            name="Colaba, Mumbai - MPCB",
            latitude=18.91,
            longitude=72.82,
            zone_type="COASTAL"
        )
        self.tz = ZoneInfo("Asia/Kolkata")

    def test_preprocessor_validation(self):
        # 1. Valid record
        valid_rec = {
            "pm25": 45.5,
            "pm10": 90.2,
            "no2": 25.0,
            "so2": 15.0,
            "co": 1.2,
            "o3": 35.0,
            "temperature": 28.5,
            "humidity": 65.0,
            "wind_speed": 12.0,
            "wind_direction": 180.0
        }
        cleaned = DataPreprocessor.clean_record(valid_rec)
        self.assertEqual(cleaned["pm25"], 45.5)
        self.assertEqual(cleaned["pm10"], 90.2)
        self.assertTrue(cleaned["is_validated"])

        # 2. Outlier / Invalid / Negative records
        invalid_rec = {
            "pm25": -10.0,      # Negative: should be sanitized to None
            "pm10": 5000.0,     # Beyond 1500 limit: should be sanitized to None
            "co": "corrupted",  # Non-numeric: should be sanitized to None
            "temperature": 100.0# Unphysical Mumbai temp: should be sanitized to None
        }
        cleaned_invalid = DataPreprocessor.clean_record(invalid_rec)
        self.assertIsNone(cleaned_invalid["pm25"])
        self.assertIsNone(cleaned_invalid["pm10"])
        self.assertIsNone(cleaned_invalid["co"])
        self.assertIsNone(cleaned_invalid["temperature"])

    def test_preprocessor_spike_detection(self):
        prev_rec = {"pm25": 50.0, "pm10": 100.0}
        curr_rec = {"pm25": 350.0, "pm10": 120.0}  # PM2.5 jumped by 300 (exceeds 250 spike threshold)
        cleaned = DataPreprocessor.clean_record(curr_rec, prev_record=prev_rec)
        self.assertIsNone(cleaned["pm25"])
        self.assertEqual(cleaned["pm10"], 120.0)

    def test_preprocessor_interpolation(self):
        # 3-hour gap interpolation
        t0 = timezone.now()
        records = [
            {"pm25": 50.0, "recorded_at": t0},
            {"pm25": None, "recorded_at": t0 + timedelta(hours=1)},
            {"pm25": None, "recorded_at": t0 + timedelta(hours=2)},
            {"pm25": 80.0, "recorded_at": t0 + timedelta(hours=3)},
        ]
        interp = DataPreprocessor.interpolate_short_gaps(records, max_gap_hours=3)
        self.assertEqual(interp[1]["pm25"], 60.0)
        self.assertEqual(interp[2]["pm25"], 70.0)
        self.assertTrue(interp[1]["is_imputed"])
        self.assertIn("pm25", interp[1]["imputed_fields"])

    def test_station_seeding(self):
        result = seed_mumbai_stations()
        self.assertGreaterEqual(result["total"], 10)
        self.assertTrue(MonitoringStation.objects.filter(station_id="OPENAQ_6927").exists())
        self.assertTrue(MonitoringStation.objects.filter(station_id="OPENAQ_6945").exists())

    def test_measurement_storage_and_unique_constraint(self):
        now = datetime.now(self.tz)
        rec1, created1 = RawMeasurement.objects.update_or_create(
            station=self.station,
            recorded_at=now,
            defaults={"pm25": 55.0, "pm10": 110.0, "source": "OPENAQ_MEASURED"}
        )
        self.assertTrue(created1)

        # Update the same station and timestamp with newer reading
        rec2, created2 = RawMeasurement.objects.update_or_create(
            station=self.station,
            recorded_at=now,
            defaults={"pm25": 58.0, "pm10": 115.0, "source": "OPENAQ_MEASURED"}
        )
        self.assertFalse(created2) # Should update, not create duplicate
        self.assertEqual(rec2.pm25, 58.0)
        self.assertEqual(RawMeasurement.objects.filter(station=self.station).count(), 1)

    def test_clean_measurement_storage(self):
        now = datetime.now(self.tz)
        raw = RawMeasurement.objects.create(
            station=self.station,
            recorded_at=now,
            pm25=55.0,
            pm10=110.0,
            source="OPENAQ_MEASURED"
        )
        clean = CleanMeasurement.objects.create(
            station=self.station,
            recorded_at=now,
            pm25=55.0,
            pm10=110.0,
            source="OPENAQ_MEASURED",
            raw_measurement=raw
        )
        self.assertEqual(clean.source, "OPENAQ_MEASURED")
        self.assertFalse(clean.is_imputed)

    def test_api_station_list(self):
        response = self.client.get('/api/v1/stations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_api_measurement_list(self):
        now = datetime.now(self.tz)
        RawMeasurement.objects.create(
            station=self.station,
            recorded_at=now,
            pm25=60.0,
            pm10=120.0,
            source="OPENAQ_MEASURED"
        )
        response = self.client.get(f'/api/v1/ingestion/measurements/?station_id={self.station.station_id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['pm25'], 60.0)
        self.assertEqual(response.data[0]['source'], "OPENAQ_MEASURED")
