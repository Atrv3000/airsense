from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from core.models import MonitoringStation
from ingestion.models import RawMeasurement, CleanMeasurement
import os
from unittest.mock import patch, MagicMock
from ingestion.services.preprocessor import DataPreprocessor
from ingestion.services.station_seeder import seed_mumbai_stations
from ingestion.services.cpcb_client import WAQIClient, CPCBClient

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

    def test_openaq_unit_conversion(self):
        from ingestion.services.air_quality_client import AirQualityClient
        # CO in ug/m3 -> mg/m3
        self.assertEqual(AirQualityClient.convert_openaq_value("co", "µg/m³", 1200.0), 1.2)
        self.assertEqual(AirQualityClient.convert_openaq_value("co", "ug/m3", 850.0), 0.85)
        # CO in ppb -> mg/m3
        self.assertEqual(AirQualityClient.convert_openaq_value("co", "ppb", 1000.0), 1.145)
        # NO2 in ppb -> ug/m3 (factor 1.88)
        self.assertEqual(AirQualityClient.convert_openaq_value("no2", "ppb", 10.0), 18.8)
        # SO2 in ppb -> ug/m3 (factor 2.62)
        self.assertEqual(AirQualityClient.convert_openaq_value("so2", "ppb", 10.0), 26.2)
        # PM25 standard
        self.assertEqual(AirQualityClient.convert_openaq_value("pm25", "ug/m3", 42.5), 42.5)
        # Negative value returns None
        self.assertIsNone(AirQualityClient.convert_openaq_value("pm25", "ug/m3", -5.0))

    def test_trigger_ingestion_requires_secret_key(self):
        from django.conf import settings
        # 1. No secret key provided -> 403 Forbidden
        res_no_key = self.client.post('/api/v1/ingestion/trigger/', data={'days': 1})
        self.assertEqual(res_no_key.status_code, status.HTTP_403_FORBIDDEN)

        # 2. Invalid secret key provided -> 403 Forbidden
        res_bad_key = self.client.post('/api/v1/ingestion/trigger/', data={'days': 1, 'secret_key': 'invalid-pass'})
        self.assertEqual(res_bad_key.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Valid secret key provided via X-Ingestion-Key header -> 200 OK
        with patch('ingestion.services.pipeline.DataPipeline.run_full_mumbai_pipeline') as mock_pipeline:
            mock_pipeline.return_value = {"processed": 10}
            res_good = self.client.post(
                '/api/v1/ingestion/trigger/',
                data={'days': 1},
                headers={'X-Ingestion-Key': settings.INGESTION_SECRET_KEY}
            )
            self.assertEqual(res_good.status_code, status.HTTP_200_OK)
            self.assertEqual(res_good.data.get('summary', {}).get('processed'), 10)


    def test_data_quality_report_command(self):
        from io import StringIO
        from django.core.management import call_command
        # Seed CleanMeasurement records with different sources
        now = datetime.now(self.tz)
        raw1 = RawMeasurement.objects.create(
            station=self.station,
            recorded_at=now - timedelta(hours=2),
            pm25=50.0,
            source="OPENAQ_MEASURED"
        )
        CleanMeasurement.objects.create(
            station=self.station,
            recorded_at=now - timedelta(hours=2),
            pm25=50.0,
            source="OPENAQ_MEASURED",
            is_imputed=False,
            raw_measurement=raw1
        )
        raw2 = RawMeasurement.objects.create(
            station=self.station,
            recorded_at=now - timedelta(hours=1),
            pm25=55.0,
            source="OPEN_METEO_MODELLED"
        )
        CleanMeasurement.objects.create(
            station=self.station,
            recorded_at=now - timedelta(hours=1),
            pm25=55.0,
            source="OPEN_METEO_MODELLED",
            is_imputed=True,
            imputed_fields=["pm25"],
            raw_measurement=raw2
        )

        out = StringIO()
        call_command('data_quality_report', stdout=out)
        output = out.getvalue()
        self.assertIn("AIRSENSE MUMBAI - DATA QUALITY REPORT", output)
        self.assertIn("OPENAQ_6927", output)
        self.assertIn("SUMMARY:", output)
        self.assertIn("Total Clean Measurements:", output)


class WAQIClientTestCase(TestCase):
    def setUp(self):
        self.station = MonitoringStation.objects.create(
            station_id="OPENAQ_6927",
            name="Colaba, Mumbai - MPCB",
            latitude=18.91,
            longitude=72.82,
            zone_type="COASTAL"
        )
        self.sample_payload = {
            "status": "ok",
            "data": {
                "aqi": 165,
                "idx": 8039,
                "attributions": [{"name": "CPCB - India Central Pollution Control Board"}],
                "city": {"name": "Colaba, Mumbai, India"},
                "iaqi": {
                    "pm25": {"v": 165},
                    "pm10": {"v": 98},
                    "no2": {"v": 42},
                    "so2": {"v": 15},
                    "co": {"v": 12},
                    "o3": {"v": 28},
                    "t": {"v": 31.5},
                    "h": {"v": 78},
                    "w": {"v": 4.2}
                },
                "time": {"s": "2026-10-15 14:00:00", "tz": "+05:30"}
            }
        }

    def test_token_resolution(self):
        # 1. No token configured
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(WAQIClient.get_token())

        # 2. Hardcoded / default 'demo' token is strictly rejected
        with patch.dict(os.environ, {"WAQI_API_TOKEN": "demo"}, clear=True):
            self.assertIsNone(WAQIClient.get_token())
        with patch.dict(os.environ, {"CPCB_API_TOKEN": "DEMO"}, clear=True):
            self.assertIsNone(WAQIClient.get_token())

        # 3. Valid token accepted
        with patch.dict(os.environ, {"WAQI_API_TOKEN": "mock_valid_token_xyz"}, clear=True):
            self.assertEqual(WAQIClient.get_token(), "mock_valid_token_xyz")
        with patch.dict(os.environ, {"CPCB_API_TOKEN": "cpcb_token_abc"}, clear=True):
            self.assertEqual(WAQIClient.get_token(), "cpcb_token_abc")

    def test_parse_waqi_response_treats_values_as_sub_indices_not_concentrations(self):
        result, iso_time = WAQIClient.parse_waqi_response(self.sample_payload["data"])
        self.assertIsNotNone(iso_time)
        self.assertEqual(result["source"], "WAQI_FEED")
        self.assertEqual(result["overall_aqi"], 165)

        # iaqi values MUST be in sub_indices dictionary, NEVER converted to raw concentrations
        self.assertIn("sub_indices", result)
        self.assertEqual(result["sub_indices"]["pm25"], 165.0)
        self.assertEqual(result["sub_indices"]["pm10"], 98.0)
        self.assertEqual(result["sub_indices"]["no2"], 42.0)
        self.assertEqual(result["sub_indices"]["co"], 12.0)
        # Verify no direct fake mass concentration keys exist
        self.assertNotIn("pm25", result)
        self.assertNotIn("pm10", result)
        self.assertNotIn("co", result)

        # Meteorology is preserved
        self.assertEqual(result["temperature"], 31.5)
        self.assertEqual(result["humidity"], 78.0)
        self.assertEqual(result["wind_speed"], 4.2)

    def test_station_reading_refuses_without_token(self):
        with patch.dict(os.environ, {}, clear=True):
            res, t_str = WAQIClient.fetch_station_reading("OPENAQ_6927")
            self.assertIsNone(res)
            self.assertIsNone(t_str)

    def test_station_reading_refuses_unmapped_station_without_city_fallback(self):
        with patch.dict(os.environ, {"WAQI_API_TOKEN": "valid_token"}):
            with patch("requests.get") as mock_get:
                res, t_str = WAQIClient.fetch_station_reading("UNKNOWN_STATION_9999")
                self.assertIsNone(res)
                self.assertIsNone(t_str)
                # Must NOT call API or fall back to city feed
                mock_get.assert_not_called()

    def test_station_reading_does_not_fall_back_to_city_on_failure(self):
        with patch.dict(os.environ, {"WAQI_API_TOKEN": "valid_token"}):
            with patch("requests.get") as mock_get:
                mock_res = MagicMock()
                mock_res.status_code = 200
                mock_res.json.return_value = {"status": "error", "message": "Unknown station"}
                mock_get.return_value = mock_res

                res, t_str = WAQIClient.fetch_station_reading("OPENAQ_6927")
                self.assertIsNone(res)
                self.assertIsNone(t_str)

                # Ensure it only called the specific station URL, never the citywide fallback
                self.assertEqual(mock_get.call_count, 1)
                called_url = mock_get.call_args[0][0]
                self.assertIn("india/mumbai/colaba", called_url)
                self.assertNotIn("/feed/mumbai/", called_url)

    def test_station_reading_success(self):
        with patch.dict(os.environ, {"WAQI_API_TOKEN": "valid_token"}):
            with patch("requests.get") as mock_get:
                mock_res = MagicMock()
                mock_res.status_code = 200
                mock_res.json.return_value = self.sample_payload
                mock_get.return_value = mock_res

                res, t_str = WAQIClient.fetch_station_reading("OPENAQ_6927")
                self.assertIsNotNone(res)
                self.assertEqual(res["source"], "WAQI_FEED")
                self.assertEqual(res["sub_indices"]["pm25"], 165.0)
                self.assertEqual(res["overall_aqi"], 165)

    def test_fetch_city_reading(self):
        with patch.dict(os.environ, {"WAQI_API_TOKEN": "valid_token"}):
            with patch("requests.get") as mock_get:
                mock_res = MagicMock()
                mock_res.status_code = 200
                city_payload = {
                    "status": "ok",
                    "data": {
                        "aqi": 145,
                        "city": {"name": "Mumbai"},
                        "iaqi": {"pm25": {"v": 145}},
                        "time": {"s": "2026-10-15 14:00:00"}
                    }
                }
                mock_res.json.return_value = city_payload
                mock_get.return_value = mock_res

                res, t_str = WAQIClient.fetch_city_reading("mumbai")
                self.assertIsNotNone(res)
                self.assertTrue(res.get("is_city_aggregate"))
                self.assertEqual(res["source"], "WAQI_FEED")

    def test_backward_compatible_cpcb_alias(self):
        self.assertIs(CPCBClient, WAQIClient)

    def test_database_source_choices(self):
        now = timezone.now()
        # Test WAQI_FEED source in RawMeasurement and CleanMeasurement
        raw_waqi = RawMeasurement.objects.create(
            station=self.station,
            recorded_at=now,
            temperature=30.0,
            source="WAQI_FEED"
        )
        clean_waqi = CleanMeasurement.objects.create(
            station=self.station,
            recorded_at=now,
            temperature=30.0,
            source="WAQI_FEED",
            raw_measurement=raw_waqi
        )
        self.assertEqual(raw_waqi.source, "WAQI_FEED")
        self.assertEqual(clean_waqi.source, "WAQI_FEED")

        # Test CPCB_OFFICIAL source
        t2 = now - timedelta(hours=1)
        clean_cpcb = CleanMeasurement.objects.create(
            station=self.station,
            recorded_at=t2,
            pm25=70.0,
            source="CPCB_OFFICIAL"
        )
        self.assertEqual(clean_cpcb.source, "CPCB_OFFICIAL")
